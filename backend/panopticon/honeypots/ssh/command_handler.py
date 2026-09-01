import importlib
import pkgutil
from collections.abc import Callable
from typing import cast, Any
import panopticon.honeypots.ssh.commands as commands
from asyncssh import SSHServerChannel, SSHServerConnection
from panopticon.honeypots.ssh.context import SSHSessionContext, SSHCommandContext, CommandEntry
from panopticon.events.event_handler import EventHandler
from panopticon.events.models import Command


def load_commands() -> dict[str, CommandEntry]:
    _registry: dict[str, CommandEntry] = {}

    for _, module_name, _ in pkgutil.iter_modules(commands.__path__):
        module = importlib.import_module(f"panopticon.honeypots.ssh.commands.{module_name}")

        run = getattr(module, "run", None)
        if run is None:
            continue

        name: str = getattr(module, "NAME", module_name)
        man: str | None = getattr(module, "MAN", None)

        _registry[name] = CommandEntry(name=name, man=man, fn=run)

    return _registry


registry: dict[str, CommandEntry] = load_commands()


class CommandHandler:

    chan: SSHServerChannel
    conn: SSHServerConnection
    session: SSHSessionContext
    event_handler: EventHandler

    def __init__(self, conn: SSHServerConnection, session: SSHSessionContext, event_handler: EventHandler) -> None:
        self.conn = conn
        self.session = session
        self.event_handler = event_handler

    def handle_input(self, command: str) -> str:
        """Parses user input from ShellSession().data_received()"""

        parts = command.split()

        # Empty input
        if not parts:
            return ""

        name: str = parts[0]
        args: list[str] = parts[1:]

        context: SSHCommandContext = SSHCommandContext(
            input=command,
            name=name,
            args=args,
            session=self.session,
            chan=self.chan,
            conn=self.conn,
            event_handler=self.event_handler,
        )

        # Help command here as I need registry
        if name == "help":
            output = ["Available Commands:"]
            output.extend(f"  {command_name}" for command_name in sorted(registry))
            return "\r\n".join(output)

        else:
            entry: CommandEntry | None = registry.get(name, None)

            if entry is None:
                output = f"{name}: command not found"
                self.event_handler.publish_background(
                    Command(
                        session_id=self.session.id,
                        src_ip=self.session.src_ip,
                        src_port=self.session.src_port,
                        input=command,
                    )
                )
            else:
                output = entry.fn(context) or ""

        if output and not output.endswith(("\n", "\r")):
            output += "\r\n"

        return output
