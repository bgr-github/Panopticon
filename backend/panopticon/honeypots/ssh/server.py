import asyncio

from asyncssh import SSHServer, SSHServerConnection
from panopticon.honeypots.ssh.shell import ShellSession


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
    pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
