import psycopg
import json
from uuid import UUID
from psycopg.rows import dict_row
from pydantic import ValidationError
from panopticon.config.settings import settings
from panopticon.config.constants import Module, COMMON_FIELDS
from panopticon.events.models import BaseEvent
from panopticon.observability.logging import logger


class InvalidEventError(Exception):
    pass


class Database:

    conn: psycopg.Connection

    def __init__(self) -> None:
        self.conn = psycopg.connect(settings.database.dsn)

    def store_event(self, event: BaseEvent) -> None:
        """Store a single event in the events table."""

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

        except psycopg.DatabaseError as e:
            self.conn.rollback()
            logger.exception(Module.INGESTION, "Failed to insert into database.")
            raise

    def get_event_by_id(self, event_id: str) -> BaseEvent | None:
        """Gets one event by its ID"""

        sql: str = """
            SELECT
                event_id,
                session_id,
                event_type,
                src_ip,
                src_port,timestamp,
                payload
            FROM events WHERE event_id = %s
                    """

        with self.conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, (event_id,))
            row = cursor.fetchone()

        if row is None:
            return None

        event_data: dict[str, str] = self.get_event_data(row)

        try:
            return BaseEvent.model_validate(event_data)
        except ValidationError:
            return None

    def get_active_sessions(self) -> list[UUID]:
        """Gets all active sessions"""

        sql: str = """
            SELECT DISTINCT session_id
            FROM events
        """

        with self.conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

        return [row["session_id"] for row in rows]

    def get_recent_events(self, limit: int = 10) -> list[BaseEvent]:
        """Get most recent events, ordered by timestamp descending"""

        sql: str = """
            SELECT
                event_id,
                session_id,
                event_type,
                src_ip,
                src_port,
                timestamp,
                payload
            FROM events
            ORDER BY timestamp DESC
            LIMIT %s
        """

        with self.conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()

        events: list[BaseEvent] = []

        for row in rows:
            event_data: dict[str, str] = self.get_event_data(row)

            try:
                event = BaseEvent.model_validate(event_data)
                events.append(event)
            except ValidationError:
                continue

        return events

    def get_event_data(self, row: dict[str, str]) -> dict:
        """Extracts event data from a database row"""

        return {
            "id": row["event_id"],
            "session_id": row["session_id"],
            "event_type": row["event_type"],
            "src_ip": str(row["src_ip"]),
            "src_port": row["src_port"],
            "timestamp": row["timestamp"],
            "payload": row["payload"] or {},
        }

    def get_event_count(self) -> int:
        """Returns the total number of events in the database in a given timeframe"""

        sql: str

        sql = "SELECT COUNT(*) FROM events"

        with self.conn.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchone()

            if result is None:
                return 0

            else:
                count = result[0]

        return count

    def validate_event(self, event_json: str) -> BaseEvent | None:
        """Compares the json string to Pydantic model to ensure json integrity"""

        try:
            return BaseEvent.model_validate_json(event_json)
        except ValidationError:
            return None

    def close(self) -> None:
        """Gracefully close connection"""

        self.conn.close()
