from asyncssh import SSHServerSession, SSHServerChannel
from typing import Optional


class ShellSession(SSHServerSession):

    def __init__(self) -> None:
        pass

    def connection_made(self, chan: SSHServerChannel) -> None:
        pass

    def shell_requested(self) -> bool:
        return True

    def session_started(self) -> None:
        pass

    def data_received(self, data: str, datatype: Optional[int]) -> None:
        pass
