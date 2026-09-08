import psycopg
import json
from datetime import datetime
from typing import LiteralString, Any, cast
from psycopg.rows import DictRow, dict_row
from pydantic import ValidationError
from panopticon.config.settings import settings
from panopticon.config.constants import Module, COMMON_FIELDS
from panopticon.events.models import BaseEvent, EventType
from panopticon.observability.logging import logger


def get_event_data_from_row(row: DictRow) -> dict[str, Any]:
    """Convert a PostgreSQL DictRow into pydantic event"""

    payload = row["payload"] if isinstance(row["payload"], dict) else {}

    return {
        "id": row["event_id"],
        "session_id": row["session_id"],
        "event_type": row["event_type"],
        "src_ip": str(row["src_ip"]),
        "src_port": row["src_port"],
        "timestamp": row["timestamp"],
        **payload,
    }


def construct_event(event_data: dict[str, Any]) -> BaseEvent | None:
    try:
        return BaseEvent.model_validate(event_data)
    except ValidationError as e:
        logger.warning(Module.DATABASE, f"Error validating event field: {e}")
        return None


class Database:

    conn: psycopg.Connection[DictRow]

    def __init__(self):
        self.conn = psycopg.connect(settings.database.dsn, row_factory=dict_row)  # type: ignore
        logger.info(Module.DATABASE, "Database initialised.")

    def get_event(self, event_id: str) -> BaseEvent | None:
        """
        Fetches a single event by its ID

        Args:
            event_id: ID of the event

        Returns:
            A BaseEvent object
        """

        rows: list[DictRow] = self.execute("SELECT * FROM events WHERE event_id = %s", (event_id,))

        if not rows:
            return None

        event_data: dict[str, Any] = get_event_data_from_row(rows[0])

        return construct_event(event_data)

    def get_session(self, session_id: str) -> list[BaseEvent] | None:
        """Get a list of events belonging to a session in ascending order

        Args:
            session_id (str): Session ID

        Returns:
            list[BaseEvent] | None:
        """

        sql: LiteralString = """
            SELECT * FROM events
            WHERE session_id = %s
            ORDER BY timestamp ASC
        """

        rows: list[DictRow] = self.execute(sql, (session_id,))

        if not rows:
            return None

        events: list[BaseEvent] = []

        for row in rows:
            event_data = get_event_data_from_row(row)

            try:
                events.append(BaseEvent.model_validate(event_data))
            except ValidationError as e:
                logger.error(Module.DATABASE, f"Error validating event during get_recent_events(): {e}")

        return events

    def get_recent_events(
        self,
        limit: int = 10,
        event_type: EventType | None = None,
        src_ip: str | None = None,
        src_port: int | None = None,
        session_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[BaseEvent]:
        """Gets all recent events with specified filters

        Args:
            limit (int, optional): Maximum number of events returned. Defaults to 10.
            event_type (EventType | None, optional): Type of event, derived from EventTime. Defaults to None.
            src_ip (str | None, optional): IP of attacker. Defaults to None.
            src_port (int | None, optional): Port of attacker. Defaults to None.
            session_id (str | None, optional): Connection session ID. Defaults to None.
            start_time (datetime | None, optional): Time filter start. Defaults to None.
            end_time (datetime | None, optional): Time filter end. Defaults to None.

        Returns:
            list[BaseEvent]
        """

        sql: str = """
            SELECT * FROM events
        """

        filters: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            filters.append("event_type = %s")
            params.append(event_type.value)

        if src_ip is not None:
            filters.append("src_ip = %s")
            params.append(src_ip)

        if src_port is not None:
            filters.append("src_port = %s")
            params.append(src_port)

        if session_id is not None:
            filters.append("session_id = %s")
            params.append(session_id)

        if start_time is not None:
            filters.append("timestamp >= %s")
            params.append(start_time)

        if end_time is not None:
            filters.append("timestamp <= %s")
            params.append(end_time)

        if filters:
            sql += " WHERE " + " AND ".join(filters)

        sql += """
            ORDER BY timestamp DESC
            LIMIT %s
        """

        params.append(limit)

        # Ensure type is compatible with execute
        rows = self.execute(sql, tuple(params))
        events: list[BaseEvent] = []

        for row in rows:
            event_data = get_event_data_from_row(row)

            try:
                events.append(BaseEvent.model_validate(event_data))
            except ValidationError as e:
                logger.error(Module.DATABASE, f"Error validating event during get_recent_events(): {e}")

        return events

    def execute(self, sql: LiteralString | str, params: tuple | None = None) -> list[DictRow]:

        # Ensure SQL is always LiteralString type
        if isinstance(sql, str):
            sql = cast(LiteralString, sql)

        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def store_event(self, event: BaseEvent) -> None:
        """
        Stores an event in database

        Args:
            event: Event to store

        Returns:
            None
        """

        sql = """
            INSERT INTO events (
                event_id,
                session_id,
                event_type,
                src_ip,
                src_port,
                timestamp,
                payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
        """

        event_data: dict[str, str] = event.model_dump(mode="json")

        payload = {key: value for key, value in event_data.items() if key not in COMMON_FIELDS}

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        event.id,
                        event.session_id,
                        event.event_type,
                        event.src_ip,
                        event.src_port,
                        event.timestamp,
                        json.dumps(payload),
                    ),
                )

            self.conn.commit()

        except psycopg.DatabaseError:
            self.conn.rollback()
            logger.exception(Module.INGESTION, "Failed to insert into database.")
            raise

    def close(self) -> None:
        """
        Close the connection

        Returns: None
        """

        self.conn.close()
