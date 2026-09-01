import psycopg
import json
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

    def validate_event(self, event_json: str) -> BaseEvent | None:
        """Compares the json string to Pydantic model to ensure json integrity"""

        try:
            return BaseEvent.model_validate_json(event_json)
        except ValidationError:
            return None

    def close(self) -> None:
        """Gracefully close connection"""

        self.conn.close()
