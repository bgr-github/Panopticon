import psycopg
import json
from typing import LiteralString, Any
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

    def get_recent_events(self, limit: int = 10, event_type: EventType | None = None) -> list[BaseEvent]:
        """
        Fetches recent events from database

        Args:
            limit: Maximum number of events to return.
            event_type: Type of event to filter for. Derived from EventType

        Returns:
            List of BaseEvents
        """

        if event_type is None:
            rows = self.execute(
                """
                SELECT * FROM events
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
        else:
            rows = self.execute(
                """
                SELECT * FROM events WHERE event_type = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (event_type.value, limit),
            )

        events: list[BaseEvent] = []

        # Validate the data with pydantic to return BaseEvent list
        for row in rows:
            event_data = get_event_data_from_row(row)
            event = construct_event(event_data)

            if event is not None:
                events.append(event)

        return events

    def execute(self, query: LiteralString, params: tuple | None = None) -> list[DictRow]:
        """
        Executes an SQL query

        Args:
            query: SQL query
            params: SQL params

        Returns:
            List of DictRows
        """

        with self.conn.cursor() as cursor:
            cursor.execute(query, params)
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
