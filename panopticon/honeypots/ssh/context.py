from collections.abc import Callable
from dataclasses import dataclass, field

from panopticon.events.event_handler import EventHandler
from panopticon.honeypots.ssh.filesystem import FakeFileSystem
from panopticon.honeypots.ssh.persona import HOSTNAME


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
    hostname: str = HOSTNAME
    previous_cwd: str | None = None
    environment: dict[str, str] = field(default_factory=dict)
    last_status: int = 0
    history: list[str] = field(default_factory=list)

    def initialise_user(self, username: str) -> None:
        # Usernames are untrusted: keep path/control characters out of the persona.
        import re

        self.username = re.sub(r"[^a-zA-Z0-9_.-]", "_", username)[:64] or "ubuntu"
        if self.username in (".", ".."):
            self.username = "ubuntu"
        self.home = self.fs.add_user(self.username)
        self.cwd = self.home
        self.environment = {
            "USER": self.username, "LOGNAME": self.username, "HOME": self.home,
            "SHELL": "/bin/bash", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
        }

    @property
    def prompt(self) -> str:
        path = self.cwd
        if path == self.home or path.startswith(self.home + "/"):
            path = "~" + path[len(self.home):]
        suffix = "#" if self.username == "root" else "$"
        return f"{self.username or 'admin'}@{self.hostname}:{path}{suffix} "


@dataclass
class SSHCommandContext:
    """Context manager for each command in commands/"""

    input: str
    name: str
    args: list[str]
    session: SSHSessionContext
    event_handler: EventHandler
    stdin: str = ""
    status: int = 0


@dataclass
class CommandEntry:
    """Context manager for command modules"""

    name: str
    man: str | None
    fn: Callable[[SSHCommandContext], list[str]]
