from dataclasses import dataclass
from collections.abc import Callable
from asyncssh import SSHServerChannel, SSHServerConnection
from panopticon.events.event_handler import EventHandler


@dataclass
class SSHSessionContext:
    """Context manager for each client connection"""

    id: str
    src_ip: str
    src_port: int
    start_time: float
    username: str | None = None


@dataclass
class SSHCommandContext:
    """Context manager for each command in commands/"""

    input: str
    name: str
    args: list[str]
    session: SSHSessionContext
    chan: SSHServerChannel
    conn: SSHServerConnection
    event_handler: EventHandler

    def emit(self, event_type, **payload) -> None:
        """Publish specialist events such as FileDownloaded etc..."""

        self.event_handler.publish_background(
            event_type(
                session_id=self.session.id,
                src_ip=self.session.src_ip,
                src_port=self.session.src_port,
                **payload,
            )
        )


@dataclass
class CommandEntry:
    """Context manager for command modules"""

    name: str
    man: str | None
    fn: Callable[[SSHCommandContext], str]
