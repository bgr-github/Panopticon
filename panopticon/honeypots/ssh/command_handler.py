import importlib
import logging
import pkgutil
import posixpath
import re
import shlex

from asyncssh import SSHServerChannel

from panopticon.events.event_handler import EventHandler
from panopticon.events.models import Command
from panopticon.honeypots.ssh import commands
from panopticon.honeypots.ssh.context import (
    CommandEntry,
    SSHCommandContext,
    SSHSessionContext,
)

logger = logging.getLogger("Command Handler")


def load_commands() -> dict[str, CommandEntry]:
    """Loads all modules in commands/ into a registry"""

    _registry: dict[str, CommandEntry] = {}

    for _, module_name, _ in pkgutil.iter_modules(commands.__path__):
        module = importlib.import_module(f"panopticon.honeypots.ssh.commands.{module_name}")

        run = getattr(module, "run", None)

        if run is None:
            continue

        name: str = getattr(module, "NAME", module_name)
        man: str | None = getattr(module, "MAN", None)

        for alias in getattr(module, "NAMES", (name,)):
            if alias in _registry:
                raise ValueError(f"Duplicate command: {alias}")

            _registry[alias] = CommandEntry(name=alias, man=man, fn=run)

    return _registry


registry: dict[str, CommandEntry] = load_commands()


class CommandHandler:

    chan: SSHServerChannel
    session: SSHSessionContext
    event_handler: EventHandler

    def __init__(self, chan: SSHServerChannel, session: SSHSessionContext, event_handler: EventHandler) -> None:
        """Initialises command handling for a client channel

        Args:
            chan (SSHServerChannel): Channel used by the client
            session (SSHSessionContext): Session state shared by commands
            event_handler (EventHandler): Handler used to publish command events
        """

        self.chan = chan
        self.session = session
        self.event_handler = event_handler

    closed: bool = False
    stderr: str = ""

    def handle_input(self, command: str) -> str:
        """Interpret a bounded shell subset. Never invoke a host executable."""
        self.stderr = ""

        if not command.strip():
            return ""

        self.event_handler.publish(
            Command(
                session_id=self.session.id,
                src_ip=self.session.src_ip,
                src_port=self.session.src_port,
                input=command,
            )
        )

        self.session.history.append(command)
        self.session.history[:] = self.session.history[-100:]

        try:
            lexer: shlex.shlex = shlex.shlex(command, posix=False, punctuation_chars=";&|<>()")
            lexer.whitespace_split = True
            tokens: list[str] = list(lexer)

            if any(token in ("&", "(", ")", "<<") or token.startswith("`") for token in tokens):
                raise ValueError("unsupported shell syntax")

            # Build a list of pipelines joined by ;, && and ||.
            groups: list[tuple[str, list[str]]] = []
            current: list[str] = []
            connector: str = ";"

            for token in tokens:
                if token in (";", "&&", "||"):

                    if not current:
                        raise ValueError("unexpected token")

                    groups.append((connector, current))
                    current, connector = [], token
                else:
                    current.append(token)

            if current:
                groups.append((connector, current))

            elif connector != ";":
                raise ValueError("unexpected end of file")

            output: list[str] = []

            for connector, group in groups:
                if self.closed:
                    break

                if connector == "&&" and self.session.last_status != 0:
                    continue

                if connector == "||" and self.session.last_status == 0:
                    continue

                stages: list[list[str]] = []
                stage: list[str] = []

                for token in group:
                    if token == "|":
                        if not stage:
                            raise ValueError("unexpected token `|' ")

                        stages.append(stage)
                        stage = []
                    else:
                        stage.append(token)

                if not stage:
                    raise ValueError("unexpected end of file")

                stages.append(stage)
                data: str = ""

                for stage in stages:
                    data = self._execute(stage, data + ("\n" if data else ""))

                    if self.closed:
                        break

                if data:
                    output.append(data)

            return "\n".join(output)

        except ValueError as exc:
            self.session.last_status = 2
            self.stderr += f"bash: syntax error: {exc}\n"

            return ""

    def _expand(self, token: str) -> str:
        """Expands quoting, home paths and environment variables in a shell token

        Args:
            token (str): Shell token to expand

        Returns:
            str: Expanded token value
        """

        if token.startswith("'") and token.endswith("'"):
            return token[1:-1]

        quoted: bool = token.startswith('"') and token.endswith('"')

        if quoted:
            token = token[1:-1]

        elif token == "~" or token.startswith("~/"):
            token = self.session.home + token[1:]

        env: dict[str, str] = {**self.session.environment, "PWD": self.session.cwd, "?": str(self.session.last_status)}

        return re.sub(
            r"\$(?:\{([A-Za-z_][A-Za-z_0-9]*|\?)\}|([A-Za-z_][A-Za-z_0-9]*|\?))",
            lambda match: env.get(match[1] or match[2], ""),
            token,
        )

    def _execute(self, tokens: list[str], stdin: str) -> str:
        """Runs one simulated command with virtual input and output redirection

        Args:
            tokens (list[str]): Tokens belonging to the command
            stdin (str): Input supplied by the previous pipeline stage

        Returns:
            str: Command output before the terminal newline
        """

        args: list[str] = []
        destination: str | None = None
        append: bool = False
        index: int = 0

        while index < len(tokens):
            token: str = tokens[index]

            if token in (">", ">>", "<"):
                if index + 1 >= len(tokens) or tokens[index + 1] in (">", ">>", "<"):
                    raise ValueError("unexpected end of file")

                target: str = self._expand(tokens[index + 1])

                if token == "<":
                    try:
                        stdin = self.session.fs.read_file(target, self.session.cwd)
                    except OSError:
                        self.session.last_status = 1
                        self.stderr += f"bash: {target}: No such file or directory\n"
                        return ""
                else:
                    destination, append = target, token == ">>"

                index += 2
                continue

            if token in ("&", "(", ")"):
                raise ValueError("unsupported shell syntax")

            args.append(self._expand(token))
            index += 1

        if not args:
            text: str = ""
            status: int = 0
        else:
            name: str = args[0]
            arguments: list[str] = args[1:]

            if name.startswith(("/bin/", "/usr/bin/")):
                name = posixpath.basename(name)

            context: SSHCommandContext = SSHCommandContext(" ".join(args), name, arguments, self.session, self.event_handler, stdin)
            entry: CommandEntry | None = registry.get(name)
            status = 0
            lines: list[str] = []

            if entry:
                lines = entry.fn(context) or []
                status = context.status
            elif name in ("exit", "logout"):
                try:
                    status = int(arguments[0]) % 256 if arguments else self.session.last_status
                except ValueError:
                    status = 2
                    self.stderr += f"bash: exit: {arguments[0]}: numeric argument required\n"

                self.closed = True
            elif name == "clear":
                lines = ["\x1b[H\x1b[2J\x1b[3J"]
            elif name == "history":
                lines = [f"{i:5}  {line}" for i, line in enumerate(self.session.history, 1)]
            elif name == "export":
                for argument in arguments:
                    key: str
                    separator: str
                    value: str
                    key, separator, value = argument.partition("=")

                    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", key):
                        status = 1
                        self.stderr += f"bash: export: `{argument}': not a valid identifier\n"
                    elif separator:
                        self.session.environment[key] = value
            elif name == "help":
                lines = [
                    "GNU bash, version 5.2.21(1)-release (x86_64-pc-linux-gnu)",
                    "These shell commands are defined internally. Type `help' to see this list.",
                    " cd [dir]    echo [arg ...]    exit [n]    export [name[=value] ...]",
                    " history     pwd              true        false",
                ]
            else:
                status = 127
                self.stderr += f"bash: {name}: command not found\n"

            text = "\n".join(lines)

            if status and lines:
                self.stderr += text + "\n"
                text = ""

        self.session.last_status = status

        if destination is not None:
            try:
                self.session.fs.write_file(destination, text + ("\n" if text else ""), self.session.cwd, append)
            except OSError as exc:
                self.session.last_status = 1
                self.stderr += f"bash: {destination}: {str(exc) or 'Permission denied'}\n"

            return ""

        return text
