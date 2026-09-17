import asyncio
from asyncssh import SSHServer, SSHServerConnection
from typing import Optional


class HoneypotServer(SSHServer):

    def __init__(self) -> None:
        pass

    def connection_made(self, conn: SSHServerConnection) -> None:
        pass

    def connection_lost(self, exc: Optional[Exception]) -> None:
        pass

    def begin_auth(self, username: str) -> bool:
        return True

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        return True

    def session_requested(self) -> bool:
        return True


async def main() -> None:
    pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
