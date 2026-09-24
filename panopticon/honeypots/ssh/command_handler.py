import importlib
import logging
import pkgutil

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

        _registry[name] = CommandEntry(name=name, man=man, fn=run)

    return _registry


registry: dict[str, CommandEntry] = load_commands()


class CommandHandler:

    chan: SSHServerChannel
    session: SSHSessionContext
    event_handler: EventHandler

    def __init__(self, chan: SSHServerChannel, session: SSHSessionContext, event_handler: EventHandler) -> None:
        self.chan = chan
        self.session = session
        self.event_handler = event_handler

    def handle_input(self, command: str) -> str:
        """Parses input passed into the command handler

        Args:
            command (str): Client input from shell

        Returns:
            str: Returns a command response
        """

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
            event_handler=self.event_handler,
        )

        output: list[str] = []
        entry: CommandEntry | None = registry.get(name, None)

        if entry is None:
            if name == "help":
                output = ["Available Commands:"]
                output.extend(f"  {command_name}" for command_name in sorted(registry))
            elif name == "exit":
                output = ["exit_gracefully"]
            else:
                output = [f"bash: {name}: command not found"]

        self.event_handler.publish(
            Command(
                session_id=self.session.id,
                src_ip=self.session.src_ip,
                src_port=self.session.src_port,
                input=command,
            )
        )

        if entry is not None:
            output = entry.fn(context) or []

        if output == ["exit_gracefully"]:
            self.chan.close()

        # terminal friendly line output
        return "\r\n".join(output)
