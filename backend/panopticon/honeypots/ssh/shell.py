import logging

from asyncssh import SSHServerChannel, SSHServerSession
from panopticon.events.event_handler import EventHandler
from panopticon.honeypots.ssh.command_handler import CommandHandler
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.functions import fix_endline

logger = logging.getLogger("SSH")


class ShellSession(SSHServerSession):

    session: SSHSessionContext
    event_handler: EventHandler
    chan: SSHServerChannel
    handler: CommandHandler

    def __init__(self, event_handler: EventHandler, session: SSHSessionContext) -> None:
        self.session = session
        self.event_handler = event_handler

    def connection_made(self, chan: SSHServerChannel) -> None:
        """Callback made as soon as client starts a shell session.

        Args:
            chan (SSHServerChannel): Client's channel
        """

        self.chan = chan
        self.handler = CommandHandler(chan, self.session, self.event_handler)

    def shell_requested(self) -> bool:
        """Callback made to verify whether the client is authorised to use the shell.

        Returns:
            bool: Whether the client can use the shell.
        """

        return True

    def session_started(self) -> None:
        """Callback made as soon as the session is started. Sends initial data to the user. e.g. a server banner"""

        self.chan.write("\033[2J\033[H")  # Clears screen and moves cursor to top
        self.chan.write("Welcome to the Linux server.\n")  # TODO: Emulate a Linux server
        self._prompt_input()

    def data_received(self, data: str, datatype: int | None) -> None:
        """Callback made whenever the client sends data to the server.

        Args:
            data (str): The data sent over
            datatype (Optional[int])
        """

        command: str = data.strip()

        # Display prompt even with empty input
        if not command:
            self._prompt_input()
            return

        output: str = ""

        try:
            output = self.handler.handle_input(command)

            if output:
                if output == "exit":
                    self.chan.close()
                else:
                    self.chan.write(fix_endline(output))

        except Exception as e:
            logger.error(f"Shell error: {e}")

        self._prompt_input()

    def _prompt_input(self) -> None:
        """Sends initial terminal characters to client."""

        self.chan.write("$> ")
