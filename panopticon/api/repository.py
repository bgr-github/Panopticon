import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from panopticon.api.models import (
    EventFilters, EventPage, EventQuery, SessionPage, SessionQuery, SessionSummary,
    Summary, Timeline, TimelinePoint, TimelineQuery, TopQuery, TopValue,
)
from panopticon.events.models import BaseEvent, EventType

type TopDimension = Literal["src_ip", "username", "password", "command"]
type SQLValue = str | int


class CursorNotFound(LookupError):
    """Requested history or stream resume position is no longer available."""


class EventReader(Protocol):
    """Read contract shared by REST routes and the SSE service."""

    def health(self) -> None:
        """Checks that the event table is available"""
        ...

    def events(self, query: EventQuery) -> EventPage:
        """Reads a page of events

        Args:
            query (EventQuery): Validated filters and cursor

        Returns:
            EventPage: History page with a live-stream handoff cursor
        """
        ...

    def event(self, event_id: UUID) -> BaseEvent | None:
        """Looks up an event

        Args:
            event_id (UUID): Stored event ID

        Returns:
            BaseEvent | None: Matching event when present
        """
        ...

    def sessions(self, query: SessionQuery) -> SessionPage:
        """Reads grouped connection summaries

        Args:
            query (SessionQuery): Session filters and pagination

        Returns:
            SessionPage: Matching session summaries
        """
        ...

    def session(self, session_id: str) -> SessionSummary | None:
        """Looks up a session summary

        Args:
            session_id (str): Connection identifier

        Returns:
            SessionSummary | None: Matching summary when present
        """
        ...

    def summary(self, filters: EventFilters) -> Summary:
        """Counts dashboard activity

        Args:
            filters (EventFilters): Activity filters

        Returns:
            Summary: Totals for matching events
        """
        ...

    def timeline(self, query: TimelineQuery) -> Timeline:
        """Groups activity into bounded time buckets

        Args:
            query (TimelineQuery): Time range, interval and event filters

        Returns:
            Timeline: Counts including empty time buckets
        """
        ...

    def top(self, dimension: TopDimension, query: TopQuery) -> list[TopValue]:
        """Ranks matching activity

        Args:
            dimension (TopDimension): Source, credential or command dimension
            query (TopQuery): Filters and result limit

        Returns:
            list[TopValue]: Values ordered by descending frequency
        """
        ...

    def stream_position(self, after_id: UUID | None) -> int:
        """Resolves a resume ID or the current committed position

        Args:
            after_id (UUID | None): Last received event, or None for live-only delivery

        Returns:
            int: Internal committed insertion position
        """
        ...

    def stream_batch(self, position: int, filters: EventFilters) -> list[tuple[int, BaseEvent]]:
        """Reads committed events after an insertion position

        Args:
            position (int): Last scanned insertion position
            filters (EventFilters): Live event filters

        Returns:
            list[tuple[int, BaseEvent]]: Ordered positions and events
        """
        ...


class SQLiteEventReader:
    """Queries the shared database using short-lived, read-only connections."""

    path: Path
    timeout: float

    def __init__(self, path: Path, timeout: float = 5.0) -> None:
        """Configures the database reader

        Args:
            path (Path): Shared SQLite database path
            timeout (float): Maximum database lock wait in seconds
        """

        self.path = path
        self.timeout = timeout

    def _connect(self) -> sqlite3.Connection:
        """Opens a read-only connection with named result columns

        Returns:
            sqlite3.Connection: Connection closed by the calling operation
        """

        connection: sqlite3.Connection = sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=self.timeout,
        )
        connection.row_factory = sqlite3.Row

        return connection

    def _where(self, filters: EventFilters) -> tuple[str, list[SQLValue]]:
        """Builds parameterised predicates for the validated filter model

        Args:
            filters (EventFilters): Filters supplied by a route

        Returns:
            tuple[str, list[SQLValue]]: SQL predicates and bound parameters
        """

        clauses: list[str] = ["1 = 1"]
        parameters: list[SQLValue] = []

        for column in ("event_type", "src_ip", "src_port", "session_id"):
            value: object = getattr(filters, column)

            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value if isinstance(value, int) else str(value))

        for column, operator, bound in (
            ("timestamp", ">=", filters.start_time), ("timestamp", "<", filters.end_time),
        ):
            if bound is not None:
                clauses.append(f"{column} {operator} ?")
                parameters.append(bound.astimezone(timezone.utc).isoformat(timespec="microseconds"))

        return " AND ".join(clauses), parameters

    def health(self) -> None:
        """Checks that the expected database schema can be queried"""

        with closing(self._connect()) as connection:
            connection.execute("SELECT id, payload FROM events LIMIT 1").fetchone()

    def events(self, query: EventQuery) -> EventPage:
        """Reads history and a stream handoff ID from one database snapshot

        Args:
            query (EventQuery): Validated event filters, page size and history cursor

        Returns:
            EventPage: Newest-first history with cursor pagination
        """

        where: str
        parameters: list[SQLValue]
        where, parameters = self._where(query)

        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            latest: sqlite3.Row | None = connection.execute("SELECT id FROM events ORDER BY rowid DESC LIMIT 1").fetchone()

            if query.before_id is not None:
                cursor: sqlite3.Row | None = connection.execute(
                    "SELECT timestamp, id FROM events WHERE id = ?", (str(query.before_id),),
                ).fetchone()

                if cursor is None:
                    raise CursorNotFound("History cursor not found")

                where += " AND (timestamp, id) < (?, ?)"
                parameters.extend((cursor["timestamp"], cursor["id"]))

            rows: list[sqlite3.Row] = connection.execute(
                f"SELECT payload FROM events WHERE {where} ORDER BY timestamp DESC, id DESC LIMIT ?",
                [*parameters, query.limit + 1],
            ).fetchall()

        items: list[BaseEvent] = [BaseEvent.model_validate_json(row["payload"]) for row in rows[:query.limit]]

        return EventPage(
            items=items,
            next_cursor=items[-1].id if len(rows) > query.limit else None,
            stream_cursor=UUID(latest["id"]) if latest else "0",
        )

    def event(self, event_id: UUID) -> BaseEvent | None:
        """Reads a complete event payload by UUID

        Args:
            event_id (UUID): Event identifier

        Returns:
            BaseEvent | None: Matching event when present
        """

        with closing(self._connect()) as connection:
            row: sqlite3.Row | None = connection.execute("SELECT payload FROM events WHERE id = ?", (str(event_id),)).fetchone()

        return BaseEvent.model_validate_json(row["payload"]) if row else None

    def _sessions(self) -> str:
        """Defines session aggregation over the complete recorded connection history

        Returns:
            str: Fixed SQL expression used by session queries
        """

        return """
            SELECT session_id, MIN(src_ip) AS src_ip, MIN(src_port) AS src_port,
                   MIN(timestamp) AS first_seen, MAX(timestamp) AS last_seen,
                   COUNT(*) AS event_count,
                   SUM(event_type = 'login_attempt') AS login_attempts,
                   SUM(event_type = 'command') AS commands,
                   MAX(CASE WHEN event_type = 'login_attempt' THEN json_extract(payload, '$.username') END) AS username,
                   MAX(CASE WHEN event_type = 'connection_closed' THEN json_extract(payload, '$.duration_seconds') END) AS duration_seconds,
                   (MAX(event_type = 'connection_open') AND NOT MAX(event_type = 'connection_closed')) AS active
            FROM events GROUP BY session_id
        """

    def sessions(self, query: SessionQuery) -> SessionPage:
        """Reads paginated session summaries with source and lifecycle filters

        Args:
            query (SessionQuery): Session filters and page bounds

        Returns:
            SessionPage: Matching complete-history summaries
        """

        where: str = "1 = 1"
        parameters: list[SQLValue] = []

        if query.src_ip is not None:
            where += " AND src_ip = ?"
            parameters.append(str(query.src_ip))

        if query.status is not None:
            where += " AND active = ?"
            parameters.append(int(query.status == "active"))

        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            total: int = connection.execute(
                f"SELECT COUNT(*) FROM ({self._sessions()}) WHERE {where}", parameters,
            ).fetchone()[0]
            rows: list[sqlite3.Row] = connection.execute(
                f"SELECT * FROM ({self._sessions()}) WHERE {where} ORDER BY last_seen DESC, session_id DESC LIMIT ? OFFSET ?",
                [*parameters, query.limit, query.offset],
            ).fetchall()

        return SessionPage(
            items=[SessionSummary.model_validate(dict(row)) for row in rows],
            total=total, limit=query.limit, offset=query.offset,
        )

    def session(self, session_id: str) -> SessionSummary | None:
        """Reads the complete recorded lifecycle of a single session

        Args:
            session_id (str): Connection identifier

        Returns:
            SessionSummary | None: Matching summary when present
        """

        with closing(self._connect()) as connection:
            row: sqlite3.Row | None = connection.execute(
                f"SELECT * FROM ({self._sessions()}) WHERE session_id = ?", (session_id,),
            ).fetchone()

        return SessionSummary.model_validate(dict(row)) if row else None

    def summary(self, filters: EventFilters) -> Summary:
        """Computes dashboard totals from one consistent read snapshot

        Args:
            filters (EventFilters): Event filters for the summary

        Returns:
            Summary: Aggregate counts without loading complete event payloads
        """

        where: str
        parameters: list[SQLValue]
        where, parameters = self._where(filters)

        with closing(self._connect()) as connection:
            connection.execute("BEGIN")
            totals: sqlite3.Row = connection.execute(
                f"SELECT COUNT(*) AS total_events, COUNT(DISTINCT session_id) AS total_sessions, COUNT(DISTINCT src_ip) AS unique_sources FROM events WHERE {where}",
                parameters,
            ).fetchone()
            counts: dict[str, int] = {
                row["event_type"]: row["count"] for row in connection.execute(
                    f"SELECT event_type, COUNT(*) AS count FROM events WHERE {where} GROUP BY event_type", parameters,
                )
            }

        return Summary(
            **dict(totals), login_attempts=counts.get("login_attempt", 0), commands=counts.get("command", 0),
            uploads=counts.get("file_upload", 0), downloads=counts.get("file_download", 0),
            events_by_type={event_type.value: counts.get(event_type.value, 0) for event_type in EventType},
        )

    def timeline(self, query: TimelineQuery) -> Timeline:
        """Counts events in UTC buckets and fills empty intervals

        Args:
            query (TimelineQuery): Interval, optional time bounds and event filters

        Returns:
            Timeline: At most one thousand activity buckets
        """

        end: datetime = query.end_time or datetime.now(timezone.utc)
        start: datetime = query.start_time or end - timedelta(days=1)
        seconds: int = {"minute": 60, "hour": 3600, "day": 86400}[query.interval]
        first: int = int(start.timestamp()) // seconds * seconds
        bucket_count: int = int((end.timestamp() - first - 0.000001) // seconds) + 1

        if start >= end or bucket_count > 1000:
            raise ValueError("Choose a positive time range with at most 1000 buckets")

        filters: TimelineQuery = query.model_copy(update={"start_time": start, "end_time": end})
        where: str
        parameters: list[SQLValue]
        where, parameters = self._where(filters)

        with closing(self._connect()) as connection:
            counts: dict[int, int] = {
                int(row["bucket"]): row["count"] for row in connection.execute(
                    f"SELECT CAST(strftime('%s', timestamp) AS INTEGER) / {seconds} * {seconds} AS bucket, COUNT(*) AS count FROM events WHERE {where} GROUP BY bucket",
                    parameters,
                )
            }

        return Timeline(
            interval=query.interval, start_time=start, end_time=end,
            items=[TimelinePoint(timestamp=datetime.fromtimestamp(first + index * seconds, timezone.utc), count=counts.get(first + index * seconds, 0)) for index in range(bucket_count)],
        )

    def top(self, dimension: TopDimension, query: TopQuery) -> list[TopValue]:
        """Ranks sources, attempted credentials or commands using fixed SQL expressions

        Args:
            dimension (TopDimension): Allowed ranking dimension
            query (TopQuery): Filters and maximum ranking length

        Returns:
            list[TopValue]: Values ordered by count with deterministic tie breaking
        """

        columns: dict[TopDimension, tuple[str, str | None]] = {
            "src_ip": ("src_ip", None),
            "username": ("json_extract(payload, '$.username')", "login_attempt"),
            "password": ("json_extract(payload, '$.password')", "login_attempt"),
            "command": ("json_extract(payload, '$.input')", "command"),
        }
        expression: str
        event_type: str | None
        expression, event_type = columns[dimension]
        where: str
        parameters: list[SQLValue]
        where, parameters = self._where(query)

        if event_type is not None:
            where += " AND event_type = ?"
            parameters.append(event_type)

        with closing(self._connect()) as connection:
            rows: list[sqlite3.Row] = connection.execute(
                f"SELECT {expression} AS value, COUNT(*) AS count FROM events WHERE {where} AND {expression} IS NOT NULL GROUP BY value ORDER BY count DESC, value ASC LIMIT ?",
                [*parameters, query.limit],
            ).fetchall()

        return [TopValue.model_validate(dict(row)) for row in rows]

    def stream_position(self, after_id: UUID | None) -> int:
        """Resolves a durable event ID to its committed SQLite insertion position

        Args:
            after_id (UUID | None): Resume event or None to start from the current tail

        Returns:
            int: Exclusive starting position for subsequent stream reads
        """

        with closing(self._connect()) as connection:
            if after_id is None:
                return connection.execute("SELECT COALESCE(MAX(rowid), 0) FROM events").fetchone()[0]

            row: sqlite3.Row | None = connection.execute("SELECT rowid FROM events WHERE id = ?", (str(after_id),)).fetchone()

        if row is None:
            raise CursorNotFound("Stream cursor not found; reload event history")

        return row[0]

    def stream_batch(self, position: int, filters: EventFilters) -> list[tuple[int, BaseEvent]]:
        """Reads a bounded insertion-ordered batch without holding a long-lived transaction

        Args:
            position (int): Last delivered insertion position
            filters (EventFilters): Live event filters

        Returns:
            list[tuple[int, BaseEvent]]: Up to one hundred committed matching events
        """

        where: str
        parameters: list[SQLValue]
        where, parameters = self._where(filters)

        with closing(self._connect()) as connection:
            rows: list[sqlite3.Row] = connection.execute(
                f"SELECT rowid AS position, payload FROM events WHERE rowid > ? AND {where} ORDER BY rowid LIMIT 100",
                [position, *parameters],
            ).fetchall()

        return [(row["position"], BaseEvent.model_validate_json(row["payload"])) for row in rows]
