from panopticon.events.models import Command
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.shell import ShellSession


class FakeEventHandler:
    def __init__(self) -> None:
        self.events = []

    def publish_background(self, event) -> None:
        self.events.append(event)


class FakeChannel:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.closed = False

    def write(self, data: str) -> None:
        self.writes.append(data)

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def make_shell() -> tuple[ShellSession, FakeEventHandler, FakeChannel, FakeConnection]:
    event_handler = FakeEventHandler()
    context = SSHSessionContext(
        _id="session-1",
        src_ip="203.0.113.10",
        src_port=49152,
        start_time=1.0,
    )
    conn = FakeConnection()
    chan = FakeChannel()
    shell = ShellSession(event_handler=event_handler, session=context, conn=conn)
    shell.connection_made(chan)

    return shell, event_handler, chan, conn


def test_connection_made_stores_channel() -> None:
    shell, _, chan, _ = make_shell()

    assert shell.chan is chan


def test_shell_requested_returns_true() -> None:
    shell, _, _, _ = make_shell()

    assert shell.shell_requested() is True


def test_session_started_writes_banner_and_prompt() -> None:
    shell, _, chan, _ = make_shell()

    shell.session_started()

    assert chan.writes == ["WELCOME BANNER\n$> "]


def test_empty_input_writes_prompt_without_publishing_command() -> None:
    shell, event_handler, chan, _ = make_shell()

    shell.data_received("\n", None)

    assert event_handler.events == []
    assert chan.writes == ["$> "]


def test_command_input_publishes_command_event_and_writes_prompt() -> None:
    shell, event_handler, chan, _ = make_shell()

    shell.data_received("uname -a\n", None)

    assert len(event_handler.events) == 1
    event = event_handler.events[0]
    assert isinstance(event, Command)
    assert event.session_id == "session-1"
    assert event.src_ip == "203.0.113.10"
    assert event.src_port == 49152
    assert event.input == "uname -a"
    assert "Linux web-prod-01" in chan.writes[0]
    assert chan.writes[-1] == "$> "


def test_exit_publishes_command_and_closes_channel_and_connection() -> None:
    shell, event_handler, chan, conn = make_shell()

    shell.data_received("exit\n", None)

    assert len(event_handler.events) == 1
    assert event_handler.events[0].input == "exit"
    assert chan.closed is True
    assert conn.closed is True
