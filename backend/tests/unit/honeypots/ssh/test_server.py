import asyncssh
import pytest

from panopticon.events.models import ConnectionClosed, ConnectionOpen, LoginAttempt
from panopticon.honeypots.ssh.server import SSHServer
from panopticon.honeypots.ssh.shell import ShellSession


class FakeEventHandler:
    def __init__(self) -> None:
        self.events = []

    def publish_background(self, event) -> None:
        self.events.append(event)


class FakeConnection:
    def __init__(self, peername: tuple[str, int] = ("203.0.113.10", 49152)) -> None:
        self.peername = peername
        self.extra_info = {}

    def get_extra_info(self, name: str):
        if name == "peername":
            return self.peername

        return None

    def set_extra_info(self, **kwargs) -> None:
        self.extra_info.update(kwargs)


def test_connection_made_creates_session_and_publishes_connection_open() -> None:
    event_handler = FakeEventHandler()
    conn = FakeConnection()
    server = SSHServer(event_handler)

    server.connection_made(conn)

    assert server.session is not None
    assert server.session.src_ip == "203.0.113.10"
    assert server.session.src_port == 49152
    assert conn.extra_info["session"] is server.session
    assert conn.extra_info["event_handler"] is event_handler

    assert len(event_handler.events) == 1
    event = event_handler.events[0]
    assert isinstance(event, ConnectionOpen)
    assert event.session_id == server.session._id
    assert event.src_ip == "203.0.113.10"
    assert event.src_port == 49152


def test_begin_auth_stores_username() -> None:
    server = SSHServer(FakeEventHandler())
    server.connection_made(FakeConnection())

    assert server.begin_auth("admin") is True

    assert server.session is not None
    assert server.session.username == "admin"


def test_password_auth_supported_returns_true() -> None:
    server = SSHServer(FakeEventHandler())

    assert server.password_auth_supported() is True


def test_validate_password_allows_login_and_publishes_login_attempt() -> None:
    event_handler = FakeEventHandler()
    server = SSHServer(event_handler)
    server.connection_made(FakeConnection())

    assert server.validate_password("admin", "password") is True

    event = event_handler.events[-1]
    assert isinstance(event, LoginAttempt)
    assert event.username == "admin"
    assert event.password == "password"
    assert event.success is True


def test_connection_lost_publishes_connection_closed() -> None:
    event_handler = FakeEventHandler()
    server = SSHServer(event_handler)
    server.connection_made(FakeConnection())

    server.connection_lost(None)

    event = event_handler.events[-1]
    assert isinstance(event, ConnectionClosed)
    assert event.duration_seconds >= 0


def test_session_requested_returns_shell_session_when_context_exists() -> None:
    event_handler = FakeEventHandler()
    server = SSHServer(event_handler)
    server.connection_made(FakeConnection())

    shell = server.session_requested()

    assert isinstance(shell, ShellSession)
    assert shell.event_handler is event_handler
    assert shell.session is server.session
    assert shell.conn is server.conn


def test_session_requested_raises_when_session_missing() -> None:
    server = SSHServer(FakeEventHandler())

    with pytest.raises(asyncssh.ChannelOpenError):
        server.session_requested()
