import asyncio
import psycopg
import json
from typing import cast
from redis.asyncio import Redis
from panopticon.config.settings import settings
from panopticon.config.constants import COMMON_FIELDS
from panopticon.observability.logging import logger

# please ignore.
# ugly local types as pylance keeps crying
RedisStreamMessage = tuple[str, dict[str, str]]
RedisStreamBatch = list[tuple[str, list[RedisStreamMessage]]]


class IngestionWorker:

    redis: Redis
    last_id: str

    def __init__(self) -> None:
        self.redis = Redis.from_url(
            str(settings.redis.dsn),
            db=0,
            decode_responses=True,
            socket_timeout=None,
        )
        self.db = psycopg.connect(settings.database.dsn)
        self.last_id = "$"

    async def read_batch(self) -> list[str]:
        """Read events from the Redis stream"""

        # Pylance keeps flagging a warning if type isnt cast to the ugly local tpye above
        event_batch = cast(
            RedisStreamBatch,
            await self.redis.xread(
                streams={settings.redis.stream_name: self.last_id},
                count=10,  # 10 events
                block=5000,  # check every 5 seconds
            ),
        )

        events: list[str] = []

        # Adds raw event json to event list
        for _, messages in event_batch:
            for message_id, fields in messages:
                self.last_id = message_id
                events.append(fields["event"])

        return events

    def store_db(self, event: str) -> None:
        sql: str = (
            """INSERT INTO events (event_id, session_id, event_type, src_ip, src_port, timestamp, payload) VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        )

        current_event: dict = json.loads(event)
        payload: dict = {key: value for key, value in current_event.items() if key not in COMMON_FIELDS}

        with self.db.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    current_event["id"],
                    current_event["session_id"],
                    current_event["event_type"],
                    current_event["src_ip"],
                    current_event["src_port"],
                    current_event["timestamp"],
                    json.dumps(payload),
                ),
            )

        self.db.commit()


async def main() -> None:
    worker: IngestionWorker = IngestionWorker()
    logger.info("Ingestion", "Ingestion worker started.")

    # Main ingestion loop
    while True:
        try:
            events = await worker.read_batch()

            if not events:
                continue

            for event in events:
                worker.store_db(event)

            logger.debug("Ingestion", f"Read {len(events)} from redis")
        except Exception as e:
            logger.error("Ingestion", f"Ingestion error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Ingestion", "Error running ingestion service")
