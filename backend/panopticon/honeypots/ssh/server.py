import asyncio
import asyncssh
import time
from typing import Optional
from asyncssh.constants import OPEN_CONNECT_FAILED
from uuid import uuid4
from panopticon.config.settings import settings
from panopticon.config.constants import Module
from panopticon.observability import logger
from panopticon.events.event_handler import EventHandler
from panopticon.events.models import ConnectionOpen, ConnectionClosed, LoginAttempt
from panopticon.honeypots.ssh.shell import ShellSession
from panopticon.honeypots.ssh.context import SSHSessionContext


class SSHServer(asyncssh.SSHServer):

    event_handler: EventHandler
    session: SSHSessionContext | None
    conn: asyncssh.SSHServerConnection

    def __init__(self, event_handler: EventHandler):
        self.event_handler = event_handler
        self.session = None

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        """Called as soon as a connection is made to the server, before any auth"""

        self.conn = conn
        peername = conn.get_extra_info("peername")

        self.session = SSHSessionContext(
            id=uuid4().hex[:8],
            src_ip=peername[0],
            src_port=peername[1],
            start_time=time.monotonic(),
        )

        # Bind the session to the connection for that client
        conn.set_extra_info(session=self.session)
        conn.set_extra_info(event_handler=self.event_handler)

        self.start_time = time.monotonic()

        self.event_handler.publish_background(
            ConnectionOpen(
                session_id=self.session.id,
                src_ip=self.session.src_ip,
                src_port=self.session.src_port,
            )
        )

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called as soon as connection is dropped"""

        if self.session:
            self.event_handler.publish_background(
                ConnectionClosed(
                    session_id=self.session.id,
                    src_ip=self.session.src_ip,
                    src_port=self.session.src_port,
                    duration_seconds=round(time.monotonic() - self.start_time, 3),
                )
            )
        else:
            logger.warning(Module.SSH, "connection_lost() callback error: could not publish event.")

    def begin_auth(self, username: str) -> bool:
        """Whether this client requires authentication or not."""

        if self.session:
            self.session.username = username

        return True

    def password_auth_supported(self) -> bool:
        """Whether user must authetnicate"""

        return True

    def validate_password(self, username: str, password: str) -> bool:
        """If auth is supported, handle password validation"""

        # Always allow attacker to log in for now
        success: bool = True

        if self.session:
            self.event_handler.publish_background(
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
            logger.warning(Module.SSH, "validate_password() callback error: could not publish event.")

        return success

    def session_requested(self) -> ShellSession:
        """Called when the client requests a shell session, creates a custom asyncSSH shell object"""

        if self.session is None:
            logger.error(Module.SSH, "Session requested without session set.")
            raise asyncssh.ChannelOpenError(OPEN_CONNECT_FAILED, "Session has not been initialised")

        return ShellSession(event_handler=self.event_handler, session=self.session, conn=self.conn)


async def main() -> None:
    event_handler: EventHandler = EventHandler()
    server: asyncssh.SSHAcceptor | None = None

    try:
        server = await asyncssh.create_server(
            server_factory=lambda: SSHServer(event_handler),
            host=settings.ssh.host,
            port=settings.ssh.port,
            server_host_keys=settings.ssh.host_key_path,
        )
        logger.info(Module.SSH, f"Server listening on {settings.ssh.host}:{settings.ssh.port}...")

        await asyncio.Future()

    except asyncio.CancelledError:
        raise

    except asyncssh.Error as e:
        logger.exception(Module.SSH, "Error starting server")

    # On shutdown
    finally:
        if server is not None:
            server.close()
            await server.wait_closed()
        await event_handler.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Goodbye")
