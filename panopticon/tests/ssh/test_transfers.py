from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from panopticon.events.event_handler import EventHandler
from panopticon.events.models import Command, EventType, FileDownload, FileDownloaded, FileUpload, FileUploaded
from panopticon.honeypots.ssh.command_handler import CommandHandler
from panopticon.honeypots.ssh.context import SSHSessionContext


@pytest.fixture
def handler() -> CommandHandler:
    """Creates an isolated command handler for transfer tests

    Returns:
        CommandHandler: Handler with a virtual filesystem and mock event publisher
    """

    session: SSHSessionContext = SSHSessionContext(
        id="transfer-session",
        src_ip="192.0.2.10",
        src_port=12345,
        start_time=0.0,
    )
    channel: Mock = Mock()
    events: Mock = Mock(spec=EventHandler)
    session.fs.write_file("readme.txt", "Welcome to the server.\n", session.cwd)

    return CommandHandler(channel, session, events)


@pytest.mark.parametrize(
    ("command", "event_type", "filename", "local_path", "method"),
    [
        ("wget https://example.test/payload.sh", EventType.file_download, "payload.sh", "/home/admin/payload.sh", "GET"),
        ("wget -qO /var/log/payload https://example.test/a", EventType.file_download, "payload", "/var/log/payload", "GET"),
        ("wget -O 'file name.txt' https://example.test/a", EventType.file_download, "file name.txt", "/home/admin/file name.txt", "GET"),
        ("wget -P /var/log https://example.test/file%20name.txt", EventType.file_download, "file name.txt", "/var/log/file name.txt", "GET"),
        ("wget -O - https://example.test/a", EventType.file_download, "a", None, "GET"),
        ("curl -fsSL https://example.test/a", EventType.file_download, "a", None, "GET"),
        ("curl -O https://example.test/a", EventType.file_download, "a", "/home/admin/a", "GET"),
        ("curl --output=payload https://example.test/a", EventType.file_download, "payload", "/home/admin/payload", "GET"),
        ("curl -T readme.txt https://example.test/upload", EventType.file_upload, "readme.txt", "/home/admin/readme.txt", "PUT"),
        ("curl --upload-file=readme.txt https://example.test/upload", EventType.file_upload, "readme.txt", "/home/admin/readme.txt", "PUT"),
        ("curl --data-binary @readme.txt https://example.test/upload", EventType.file_upload, "readme.txt", "/home/admin/readme.txt", "POST"),
        ("curl -F 'file=@readme.txt;type=text/plain' https://example.test/upload", EventType.file_upload, "readme.txt", "/home/admin/readme.txt", "POST"),
    ],
)
def test_transfer_metadata(
    handler: CommandHandler,
    command: str,
    event_type: EventType,
    filename: str,
    local_path: str | None,
    method: str,
) -> None:
    """Checks the direction, paths and session metadata of recorded transfer attempts

    Args:
        handler (CommandHandler): Isolated command handler fixture
        command (str): Transfer command supplied by the client
        event_type (EventType): Expected upload or download event type
        filename (str): Expected local or remote filename
        local_path (str | None): Expected normalised virtual path
        method (str): Expected transfer method
    """

    response: str = handler.handle_input(command)
    events: list[object] = [call.args[0] for call in handler.event_handler.publish.call_args_list]

    assert len(events) == 2
    assert isinstance(events[0], Command)
    assert isinstance(events[1], (FileUploaded, FileDownloaded))

    event: FileUploaded | FileDownloaded = events[1]

    assert event.event_type == event_type
    assert event.filename == filename
    assert event.local_path == local_path
    assert event.method == method
    assert event.session_id == handler.session.id
    assert event.src_ip == handler.session.src_ip
    assert event.src_port == handler.session.src_port
    assert event.command == command
    assert event.status == "attempted"
    assert event.simulated is True
    assert "attempt recorded" in response

    if isinstance(event, FileUploaded):
        assert event.size_bytes == len("Welcome to the server.\n".encode())
        assert event.filetype == "text/plain"


@pytest.mark.parametrize(
    "command",
    [
        "wget",
        "wget -O",
        "wget file:///etc/passwd",
        "wget https://example.test:99999/a",
        "curl --upload-file",
        "curl -T - https://example.test/upload",
        "curl --data secret https://example.test/upload",
        "curl -T a -T b https://example.test/upload",
        "curl https://example.test/a https://example.test/b",
        "curl --unknown https://example.test/a",
        "curl 'unterminated",
    ],
)
def test_invalid_transfer_only_records_command(handler: CommandHandler, command: str) -> None:
    """Checks that invalid requests do not produce misleading transfer events

    Args:
        handler (CommandHandler): Isolated command handler fixture
        command (str): Invalid transfer command
    """

    response: str = handler.handle_input(command)

    assert response or handler.stderr
    handler.event_handler.publish.assert_called_once()
    assert isinstance(handler.event_handler.publish.call_args.args[0], Command)


def test_transfer_attempts_do_not_move_files(handler: CommandHandler) -> None:
    """Checks that simulated transfers leave files intact and make no HTTP requests

    Args:
        handler (CommandHandler): Isolated command handler fixture
    """

    original: dict[str, object] = dict(handler.session.fs.entries)

    with patch("urllib.request.urlopen", side_effect=AssertionError("Unexpected HTTP request")), patch(
        "socket.create_connection", side_effect=AssertionError("Unexpected network connection")
    ):
        handler.handle_input("wget https://example.test/payload")
        handler.handle_input("curl -T readme.txt https://example.test/upload")

    assert handler.session.fs.entries == original


def test_missing_upload_file_is_still_an_attempt(handler: CommandHandler) -> None:
    """Checks that an unavailable virtual source is recorded with an unknown size

    Args:
        handler (CommandHandler): Isolated command handler fixture
    """

    handler.handle_input("curl -T missing.bin https://example.test/upload")
    event: FileUploaded = handler.event_handler.publish.call_args.args[0]

    assert isinstance(event, FileUploaded)
    assert event.size_bytes is None
    assert event.filetype == "application/octet-stream"
    assert event.status == "attempted"


def test_wget_multiple_urls(handler: CommandHandler) -> None:
    """Checks that wget publishes one transfer event for each requested URL

    Args:
        handler (CommandHandler): Isolated command handler fixture
    """

    handler.handle_input("wget https://example.test/a https://example.test/b")
    events: list[object] = [call.args[0] for call in handler.event_handler.publish.call_args_list]

    assert len(events) == 3
    assert isinstance(events[1], FileDownloaded)
    assert isinstance(events[2], FileDownloaded)
    assert events[1].url == "https://example.test/a"
    assert events[2].url == "https://example.test/b"


def test_transfer_models_have_fixed_event_types(handler: CommandHandler) -> None:
    """Checks compatibility aliases and prevents transfer events being labelled as commands

    Args:
        handler (CommandHandler): Isolated command handler fixture
    """

    handler.handle_input("wget https://example.test/a")
    event: FileDownloaded = handler.event_handler.publish.call_args.args[0]
    data: dict[str, object] = event.model_dump()
    data["event_type"] = EventType.command

    assert FileDownload is FileDownloaded
    assert FileUpload is FileUploaded
    assert '"event_type":"file_download"' in event.model_dump_json()

    with pytest.raises(ValidationError):
        FileDownloaded.model_validate(data)
