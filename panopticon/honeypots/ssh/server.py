import asyncio
import logging
import sys
import time
from uuid import uuid4

from asyncssh import Error, SSHAcceptor, SSHServer, SSHServerConnection, create_server

from panopticon.config.settings import settings
from panopticon.events.event_handler import EventHandler
from panopticon.events.models import ConnectionClosed, ConnectionOpen, LoginAttempt
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.shell import ShellSession
from panopticon.observability.logger import configure_logging

logger = logging.getLogger("SSH")


class HoneypotServer(SSHServer):

    conn: SSHServerConnection
    event_handler: EventHandler
    session: SSHSessionContext

    def __init__(self, event_handler: EventHandler) -> None:
        self.event_handler = event_handler

    def connection_made(self, conn: SSHServerConnection) -> None:
        """Callback made when a client tries to initially connect to the server.

        Args:
            conn (SSHServerConnection): User's connection object
        """

        self.conn = conn

        self.session = SSHSessionContext(
            id=uuid4().hex[:8],
            src_ip=conn.get_extra_info("peername")[0],
            src_port=conn.get_extra_info("peername")[1],
            start_time=time.monotonic(),
        )

        self.event_handler.publish(
            ConnectionOpen(
                session_id=self.session.id,
                src_ip=self.session.src_ip,
                src_port=self.session.src_port,
            )
        )

    def connection_lost(self, exc: Exception | None) -> None:
        """Callback made when the client connection drops.

        Args:
            exc (Optional[Exception]): None if connection closes cleanly.
        """

        if self.session:
            self.event_handler.publish(
                ConnectionClosed(
                    session_id=self.session.id,
                    src_ip=self.session.src_ip,
                    src_port=self.session.src_port,
                    duration_seconds=round(time.monotonic() - self.session.start_time, 3),
                )
            )
        else:
            logger.warning(f"Connection to client not closed gracefully: {exc}")

    def begin_auth(self, username: str) -> bool:
        """Callback made when the client begins the authorisation process.

        Args:
            username (str): Username the client is trying to connect to the server with.

        Returns:
            bool: Whether the client is successful or not.
        """

        self.session.username = username

        return True

    def password_auth_supported(self) -> bool:
        """Callback function to decide whether the client must authenticate or not.

        Returns:
            bool: Whether the client can proceed to authentication.
        """

        return True

    def validate_password(self, username: str, password: str) -> bool:
        """Callback made to validate the chosen password by the client, if they are allowed to authenticate.

        Args:
            username (str): Client username
            password (str): Client password

        Returns:
            bool: Whether the client is validated or not.
        """

        success: bool = True

        if self.session:
            self.event_handler.publish(
                LoginAttempt(
                    session_id=self.session.id,
                    src_ip=self.session.src_ip,
                    src_port=self.session.src_port,
                    username=username,
                    password=password,
                    success=success,
                )
            )
        else:
            logger.warning(f"Validation without session. Session ID: {self.session.id}")

        return success

    def session_requested(self) -> ShellSession:
        """Callback made when the client is authenticate and a shell is requested.

        Returns:
            ShellSession: Client's session as an object.
        """

        return ShellSession(self.event_handler, self.session)


async def main() -> None:
    server: SSHAcceptor | None = None

    try:
        server = await create_server(
            server_factory=lambda: HoneypotServer(EventHandler()),
            host=settings.ssh.host,
            port=settings.ssh.port,
            server_host_keys=settings.ssh.host_key_path,
        )

        logger.info(f"Server listening on {settings.ssh.host}:{settings.ssh.port}...")

        await asyncio.Future()
    except asyncio.CancelledError:
        raise
    except Error as e:
        logger.error(e)
    except FileNotFoundError:
        logger.error("Please provide SSH host keys.")
        sys.exit(1)

    finally:
        if server is not None:
            server.close()


if __name__ == "__main__":
    try:
        configure_logging("SSH")
        logging.getLogger("asyncssh").setLevel(logging.ERROR)
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
