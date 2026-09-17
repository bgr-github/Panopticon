from asyncssh import SSHServerChannel, SSHServerSession


class ShellSession(SSHServerSession):

    def __init__(self) -> None:
        pass

    def connection_made(self, chan: SSHServerChannel) -> None:
        """Callback made as soon as client starts a shell session.

        Args:
            chan (SSHServerChannel): Client's channel
        """

    def shell_requested(self) -> bool:
        """Callback made to verify whether the client is authorised to use the shell.

        Returns:
            bool: Whether the client can use the shell.
        """

        return True

    def session_started(self) -> None:
        """Callback made as soon as the session is started. Sends initial data to the user. e.g. a server banner"""

    def data_received(self, data: str, datatype: int | None) -> None:
        """Callback made whenever the client sends data to the server.

        Args:
            data (str): The data sent over
            datatype (Optional[int]): _description_
        """
