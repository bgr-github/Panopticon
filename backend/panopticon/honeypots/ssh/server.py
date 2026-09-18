import asyncio
import logging

from asyncssh import Error, SSHAcceptor, SSHServer, SSHServerConnection, create_server
from panopticon.config.settings import settings
from panopticon.honeypots.ssh.shell import ShellSession
from panopticon.observability.logger import configure_logging

logger = logging.getLogger("SSH")


class HoneypotServer(SSHServer):

    def __init__(self) -> None:
        pass

    def connection_made(self, conn: SSHServerConnection) -> None:
        """Callback made when a client tries to initially connect to the server.

        Args:
            conn (SSHServerConnection): User's connection object
        """

    def connection_lost(self, exc: Exception | None) -> None:
        """Callback made when the client connection drops.

        Args:
            exc (Optional[Exception]): None if connection closes cleanly.
        """

    def begin_auth(self, username: str) -> bool:
        """Callback made when the client begins the authorisation process.

        Args:
            username (str): Username the client is trying to connect to the server with.

        Returns:
            bool: Whether the client is successful or not.
        """
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

        return True

    def session_requested(self) -> ShellSession:
        """Callback made when the client is authenticate and a shell is requested.

        Returns:
            ShellSession: Client's session as an object.
        """

        return ShellSession()


async def main() -> None:
    server: SSHAcceptor | None = None

    try:
        await create_server(
            server_factory=lambda: HoneypotServer(),
            host=settings.ssh.host,
            port=settings.ssh.port,
            server_host_keys=settings.ssh.host_key_path,
        )

        logger.info(f"Server listening on f{settings.ssh.host}:{settings.ssh.port}...")

        await asyncio.Future()
    except asyncio.CancelledError:
        raise
    except Error as e:
        logger.error(e)
    except FileNotFoundError:
        logger.error("Please provide SSH host keys.")


if __name__ == "__main__":
    try:
        configure_logging("SSH")
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
