from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, IPvAnyAddress, model_validator

from panopticon.events.models import BaseEvent, EventType

type StreamCursor = UUID | Literal["0"]


class EventFilters(BaseModel):
    """Validated filters shared by event history, statistics and streaming."""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType | None = None
    src_ip: IPvAnyAddress | None = None
    src_port: int | None = Field(default=None, ge=0, le=65535)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        """Checks that a supplied time range has a positive duration

        Returns:
            Self: Validated filter model
        """

        if self.start_time is not None and self.end_time is not None and self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")

        return self


class EventQuery(EventFilters):
    limit: int = Field(default=50, ge=1, le=500)
    before_id: UUID | None = None


class StreamQuery(EventFilters):
    after_id: StreamCursor | None = None


class TimelineQuery(EventFilters):
    interval: Literal["minute", "hour", "day"] = "hour"


class TopQuery(EventFilters):
    limit: int = Field(default=10, ge=1, le=50)


class SessionQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0, le=100000)
    src_ip: IPvAnyAddress | None = None
    status: Literal["active", "closed"] | None = None


class EventPage(BaseModel):
    items: list[BaseEvent]
    next_cursor: UUID | None
    stream_cursor: StreamCursor


class SessionSummary(BaseModel):
    session_id: str
    src_ip: str
    src_port: int
    first_seen: datetime
    last_seen: datetime
    event_count: int
    login_attempts: int
    commands: int
    username: str | None
    duration_seconds: float | None
    active: bool


class SessionPage(BaseModel):
    items: list[SessionSummary]
    total: int
    limit: int
    offset: int


class Summary(BaseModel):
    total_events: int
    total_sessions: int
    unique_sources: int
    login_attempts: int
    commands: int
    uploads: int
    downloads: int
    events_by_type: dict[str, int]


class TimelinePoint(BaseModel):
    timestamp: datetime
    count: int


class Timeline(BaseModel):
    interval: Literal["minute", "hour", "day"]
    start_time: datetime
    end_time: datetime
    items: list[TimelinePoint]


class TopValue(BaseModel):
    value: str
    count: int


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ready"] = "ready"
