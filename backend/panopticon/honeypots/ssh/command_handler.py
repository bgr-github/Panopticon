import importlib
import pkgutil
import panopticon.honeypots.ssh.commands as commands
from collections.abc import Callable
from typing import List, TypedDict
from asyncssh import SSHServerChannel, SSHServerConnection
from panopticon.honeypots.ssh.context import SSHSessionContext


class CommandEntry(TypedDict):
    name: str
    man: str | None
    fn: Callable[..., str]


def load_commands() -> dict[str, CommandEntry]:
    _registry: dict[str, CommandEntry] = {}

    for _, module_name, _ in pkgutil.iter_modules(commands.__path__):
        module = importlib.import_module(f"panopticon.honeypots.ssh.commands.{module_name}")

        if not hasattr(module, "run"):
            continue

        if hasattr(module, "NAME"):
            name = module.NAME
        else:
            name = module_name

        _registry[name] = {
            "name": name,
            "man": getattr(module, "MAN", None),
            "fn": module.run,
        }

    return _registry


registry: dict[str, CommandEntry] = load_commands()


class CommandHandler:

    chan: SSHServerChannel
    conn: SSHServerConnection
    session: SSHSessionContext

    def __init__(self, conn: SSHServerConnection, session: SSHSessionContext) -> None:
        self.conn = conn
        self.session = session

    def handle_input(self, command: str) -> str:
        """Parses user input from ShellSession().data_received()"""

        parts = command.split()

        # Empty input
        if not parts:
            return ""

        name: str = parts[0]
        args: List[str] = parts[1:]

        # Help command here as I need registry
        if name == "help":
            output = ["Available Commands:"]
            output.extend(f"  {command_name}" for command_name in sorted(registry))
            return "\r\n".join(output) + "\r\n"
        else:
            entry: CommandEntry | None = registry.get(name, None)

            if entry is None:
                output = f"{name}: command not found"
            else:
                output = entry["fn"](args, self.session, self.chan, self.conn) or ""

        if output and not output.endswith(("\n", "\r")):
            output += "\r\n"

        return output
