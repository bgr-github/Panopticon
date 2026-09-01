from dataclasses import dataclass


@dataclass
class SSHSessionContext:
    """Context manager for each client"""

    id: str
    src_ip: str
    src_port: int
    start_time: float
    username: str | None = None
