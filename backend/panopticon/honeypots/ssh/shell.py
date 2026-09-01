import asyncssh
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.command_handler import CommandHandler
from panopticon.events.event_handler import EventHandler
from panopticon.observability.logging import logger
from panopticon.config.constants import Module


class ShellSession(asyncssh.SSHServerSession):

    session: SSHSessionContext
    event_handler: EventHandler
    chan: asyncssh.SSHServerChannel
    conn: asyncssh.SSHServerConnection
    handler: CommandHandler

    def __init__(
        self, event_handler: EventHandler, session: SSHSessionContext, conn: asyncssh.SSHServerConnection
    ) -> None:
        self.session = session
        self.event_handler = event_handler
        self.conn = conn

        self.handler = CommandHandler(conn, session, event_handler)

    def connection_made(self, chan: asyncssh.SSHServerChannel) -> None:
        """Called as soon as a connection is made to the shell session"""

        self.chan = chan  # Current server channels as SSH connections can have several channels per connection
        self.handler.chan = chan

    def shell_requested(self) -> bool:
        """Whether the client can use shell or not"""

        return True

    def session_started(self) -> None:
        """Called when client shell session begins"""

        self.chan.write("WELCOME BANNER\n$> ")  # TODO: Make realistic

    def data_received(self, data: str, datatype: object) -> None:
        """Called when data is received by the client"""

        command: str = data.strip()

        # Show prompt even with empty inputs
        if not command:
            self.chan.write("$> ")
            return

        output: str = ""

        try:
            output = self.handler.handle_input(command)
            if output:
                self.chan.write(output)

        except Exception as e:
            logger.exception(Module.SSH, "Shell error")

        self.chan.write("$> ")
