from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from panopticon.events.models import (
    Command,
    ConnectionClosed,
    ConnectionOpen,
    EventType,
    LoginAttempt,
)


def test_connection_open_sets_defaults() -> None:
    event = ConnectionOpen(session_id="session-1", src_ip="127.0.0.1", src_port=54321)

    assert isinstance(event.id, UUID)
    assert isinstance(event.timestamp, datetime)
    assert event.event_type == EventType.connection_open
    assert event.session_id == "session-1"
    assert event.src_ip == "127.0.0.1"
    assert event.src_port == 54321


def test_connection_closed_requires_duration() -> None:
    with pytest.raises(ValidationError):
        ConnectionClosed(session_id="session-1", src_ip="127.0.0.1", src_port=54321)


def test_connection_closed_stores_duration() -> None:
    event = ConnectionClosed(
        session_id="session-1",
        src_ip="127.0.0.1",
        src_port=54321,
        duration_seconds=1.25,
    )

    assert event.event_type == EventType.connection_closed
    assert event.duration_seconds == 1.25


def test_login_attempt_stores_credentials_and_result() -> None:
    event = LoginAttempt(
        session_id="session-1",
        src_ip="127.0.0.1",
        src_port=54321,
        username="admin",
        password="password",
        success=True,
    )

    assert event.event_type == EventType.login_attempt
    assert event.username == "admin"
    assert event.password == "password"
    assert event.success is True


def test_command_stores_input() -> None:
    event = Command(
        session_id="session-1",
        src_ip="127.0.0.1",
        src_port=54321,
        input="uname -a",
    )

    assert event.event_type == EventType.command
    assert event.input == "uname -a"


def test_event_serializes_to_json() -> None:
    event = ConnectionOpen(session_id="session-1", src_ip="127.0.0.1", src_port=54321)

    event_json = event.model_dump_json()

    assert '"session_id":"session-1"' in event_json
    assert '"src_ip":"127.0.0.1"' in event_json
    assert '"src_port":54321' in event_json
    assert '"event_type":"connection_open"' in event_json
