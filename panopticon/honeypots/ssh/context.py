from collections.abc import Callable
from dataclasses import dataclass, field

from panopticon.events.event_handler import EventHandler
from panopticon.honeypots.ssh.filesystem import FakeFileSystem


@dataclass
class SSHSessionContext:
    """Context manager for each client connection"""

    id: str
    src_ip: str
    src_port: int
    start_time: float
    username: str | None = None

    # Filesystem
    cwd: str = "/home/admin"
    home: str = "/home/admin"
    fs: FakeFileSystem = field(default_factory=FakeFileSystem)


@dataclass
class SSHCommandContext:
    """Context manager for each command in commands/"""

    input: str
    name: str
    args: list[str]
    session: SSHSessionContext
    event_handler: EventHandler


@dataclass
class CommandEntry:
    """Context manager for command modules"""

    name: str
    man: str | None
    fn: Callable[[SSHCommandContext], list[str]]
