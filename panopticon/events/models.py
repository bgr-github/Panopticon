from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


# Enums
class EventType(StrEnum):
    connection_open = "connection_open"
    connection_closed = "connection_closed"
    login_attempt = "login_attempt"
    command = "command"
    file_download = "file_download"
    file_upload = "file_upload"


# Event Types
class BaseEvent(BaseModel):
    """Every event on any type of honeypot will have these fields"""

    model_config = ConfigDict(extra="allow")

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str
    src_ip: str
    src_port: int
    event_type: EventType


class ConnectionOpen(BaseEvent):
    event_type: EventType = EventType.connection_open


class ConnectionClosed(BaseEvent):
    event_type: EventType = EventType.connection_closed
    duration_seconds: float


class LoginAttempt(BaseEvent):
    event_type: EventType = EventType.login_attempt
    username: str
    password: str
    success: bool


class Command(BaseEvent):
    event_type: EventType = EventType.command
    input: str


class FileTransfer(BaseEvent):
    """Metadata for a simulated file transfer attempt, viewed from the honeypot."""

    url: str
    filename: str
    filetype: str
    command: str
    method: Literal["GET", "PUT", "POST"]
    local_path: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    status: Literal["attempted"] = "attempted"
    simulated: Literal[True] = True


class FileDownloaded(FileTransfer):
    event_type: Literal[EventType.file_download] = EventType.file_download  # type: ignore


class FileUploaded(FileTransfer):
    event_type: Literal[EventType.file_upload] = EventType.file_upload  # type: ignore


# Preserve the event names used before transfer commands were implemented.
FileDownload = FileDownloaded
FileUpload = FileUploaded
