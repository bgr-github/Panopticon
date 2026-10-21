import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from panopticon.api.models import (
    EventFilters, EventPage, EventQuery, Health, SessionPage, SessionQuery, SessionSummary,
    StreamCursor, StreamQuery, Summary, Timeline, TimelineQuery, TopQuery, TopValue,
)
from panopticon.api.repository import CursorNotFound, EventReader, SQLiteEventReader, TopDimension
from panopticon.api.stream import stream_events
from panopticon.config.settings import Settings, settings
from panopticon.events.models import BaseEvent
from panopticon.events.sqlite_store import SQLiteEventStore

logger: logging.Logger = logging.getLogger("API")


def create_app(config: Settings | None = None, reader: EventReader | None = None) -> FastAPI:
    """Creates the API with injected configuration and event-query dependencies

    Args:
        config (Settings | None): Service settings, or the configured application defaults
        reader (EventReader | None): Query implementation, or the shared SQLite reader

    Returns:
        FastAPI: Independently runnable REST and SSE application
    """

    configuration: Settings = config or settings
    event_reader: EventReader = reader or SQLiteEventReader(configuration.database.path, configuration.database.timeout)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Initialises the shared schema and checks readiness before serving requests

        Args:
            application (FastAPI): Application entering its serving lifespan

        Yields:
            None: Control while the service is running
        """

        if reader is None:
            store: SQLiteEventStore = SQLiteEventStore(configuration.database.path, configuration.database.timeout)
            await asyncio.to_thread(store.initialise)

        await asyncio.to_thread(event_reader.health)
        yield

    application: FastAPI = FastAPI(title="Panopticon API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware, allow_origins=configuration.api.cors_origins,
        allow_methods=["GET"], allow_headers=["Last-Event-ID"],
    )

    def get_reader() -> EventReader:
        """Provides the application-scoped query dependency

        Returns:
            EventReader: Configured read implementation
        """

        return event_reader

    @application.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc: sqlite3.Error) -> JSONResponse:
        """Reports unavailable storage without disclosing database paths or SQL

        Args:
            request (Request): Request whose database query failed
            exc (sqlite3.Error): Underlying database error

        Returns:
            JSONResponse: Retryable service-unavailable response
        """

        logger.error("Database request failed", exc_info=exc)

        return JSONResponse(status_code=503, content={"detail": "Event database unavailable"}, headers={"Retry-After": "2"})

    @application.exception_handler(CursorNotFound)
    async def missing_cursor(request: Request, exc: CursorNotFound) -> JSONResponse:
        """Reports unknown event-history or stream cursors

        Args:
            request (Request): Request with an unavailable cursor
            exc (CursorNotFound): Cursor lookup failure

        Returns:
            JSONResponse: Not-found response explaining how to refresh the cursor
        """

        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.get("/health", response_model=Health, tags=["Service"])
    def health(repository: Annotated[EventReader, Depends(get_reader)]) -> Health:
        """Checks database readiness without requiring SSH to be running

        Args:
            repository (EventReader): Injected query implementation

        Returns:
            Health: Current database readiness
        """

        repository.health()

        return Health()

    @application.get("/events", response_model=EventPage, tags=["Events"])
    def events(query: Annotated[EventQuery, Query()], repository: Annotated[EventReader, Depends(get_reader)]) -> EventPage:
        """Lists newest-first events with filters and cursor pagination

        Args:
            query (EventQuery): History filters, page limit and optional before_id
            repository (EventReader): Injected query implementation

        Returns:
            EventPage: Events, next history cursor and snapshot stream cursor
        """

        return repository.events(query)

    @application.get("/events/stream", tags=["Events"], response_class=StreamingResponse, responses={200: {"content": {"text/event-stream": {}}}})
    async def event_stream(
        request: Request,
        query: Annotated[StreamQuery, Query()],
        repository: Annotated[EventReader, Depends(get_reader)],
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        """Streams new commits or resumes after the last received event ID

        Args:
            request (Request): Client connection and disconnect state
            query (StreamQuery): Live filters and optional initial after_id cursor
            repository (EventReader): Injected query implementation
            last_event_id (str | None): Browser reconnect cursor, preferred over after_id

        Returns:
            StreamingResponse: SSE events with IDs, retry hints and keepalive comments
        """

        cursor: StreamCursor | None = query.after_id

        if last_event_id is not None:
            try:
                cursor = "0" if last_event_id == "0" else UUID(last_event_id)

            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Last-Event-ID must be an event UUID or 0") from exc

        position: int = 0 if cursor == "0" else await asyncio.to_thread(repository.stream_position, cursor)
        filters: EventFilters = EventFilters.model_validate(query.model_dump(exclude={"after_id"}))

        return StreamingResponse(
            stream_events(request, repository, position, filters, configuration.api.poll_interval, configuration.api.heartbeat_interval),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.get("/events/{event_id}", response_model=BaseEvent, tags=["Events"])
    def event(event_id: UUID, repository: Annotated[EventReader, Depends(get_reader)]) -> BaseEvent:
        """Retrieves the full stored payload of a single event

        Args:
            event_id (UUID): Event identifier
            repository (EventReader): Injected query implementation

        Returns:
            BaseEvent: Full event including type-specific fields
        """

        result: BaseEvent | None = repository.event(event_id)

        if result is None:
            raise HTTPException(status_code=404, detail="Event not found")

        return result

    @application.get("/sessions", response_model=SessionPage, tags=["Sessions"])
    def sessions(query: Annotated[SessionQuery, Query()], repository: Annotated[EventReader, Depends(get_reader)]) -> SessionPage:
        """Lists session summaries with source and lifecycle filters

        Args:
            query (SessionQuery): Session filters, limit and offset
            repository (EventReader): Injected query implementation

        Returns:
            SessionPage: Summaries with complete recorded lifecycle counts
        """

        return repository.sessions(query)

    @application.get("/sessions/{session_id}", response_model=SessionSummary, tags=["Sessions"])
    def session(session_id: str, repository: Annotated[EventReader, Depends(get_reader)]) -> SessionSummary:
        """Retrieves a session summary; use /events?session_id=... for its timeline

        Args:
            session_id (str): Connection identifier
            repository (EventReader): Injected query implementation

        Returns:
            SessionSummary: Complete recorded session summary
        """

        result: SessionSummary | None = repository.session(session_id)

        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")

        return result

    @application.get("/stats/summary", response_model=Summary, tags=["Statistics"])
    def summary(query: Annotated[EventFilters, Query()], repository: Annotated[EventReader, Depends(get_reader)]) -> Summary:
        """Returns dashboard counts for the selected event filters

        Args:
            query (EventFilters): Time, source, session and event-type filters
            repository (EventReader): Injected query implementation

        Returns:
            Summary: Event, session, source and activity counts
        """

        return repository.summary(query)

    @application.get("/stats/timeline", response_model=Timeline, tags=["Statistics"])
    def timeline(query: Annotated[TimelineQuery, Query()], repository: Annotated[EventReader, Depends(get_reader)]) -> Timeline:
        """Returns UTC activity buckets, defaulting to the last twenty-four hours

        Args:
            query (TimelineQuery): Event filters, time bounds and minute/hour/day interval
            repository (EventReader): Injected query implementation

        Returns:
            Timeline: At most one thousand buckets including zero-count intervals
        """

        try:
            return repository.timeline(query)

        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.get("/stats/top/{dimension}", response_model=list[TopValue], tags=["Statistics"])
    def top(dimension: TopDimension, query: Annotated[TopQuery, Query()], repository: Annotated[EventReader, Depends(get_reader)]) -> list[TopValue]:
        """Ranks source IPs, usernames, passwords or commands by frequency

        Args:
            dimension (TopDimension): Allowed ranking category
            query (TopQuery): Event filters and maximum result count
            repository (EventReader): Injected query implementation

        Returns:
            list[TopValue]: Matching values ordered by descending count
        """

        return repository.top(dimension, query)

    return application


app: FastAPI = create_app()
