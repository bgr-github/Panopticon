from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# Enums
class EventType(str, Enum):
    connection_open = "connection_open"
    connection_closed = "connection_closed"
    login_attempt = "login_attempt"
    command = "command"


# Event Types
class BaseEvent(BaseModel):
    """Every event on any type of honeypot will have these fields"""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.now)
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
