import asyncio
import time
from typing import cast
from redis.asyncio import Redis
from panopticon.config.settings import settings
from panopticon.observability.logging import logger

# please ignore.
# ugly local types as pylance keeps crying
RedisStreamMessage = tuple[str, dict[str, str]]
RedisStreamBatch = list[tuple[str, list[RedisStreamMessage]]]


class IngestionWorker:

    redis: Redis
    last_id: str

    def __init__(self) -> None:
        self.redis = Redis.from_url(str(settings.redis.dsn), db=0, decode_responses=True)
        self.last_id = "0"

        # object pushes to both postgresql and server-side events

    async def read_batch(self) -> list[str]:
        """Read events from the Redis stream"""

        # Pylance keeps flagging a warning if type isnt cast to the ugly local tpye above
        event_batch = cast(
            RedisStreamBatch,
            await self.redis.xread(
                streams={settings.redis.stream_name: self.last_id},
                count=10,  # TODO: Blocks of 10 events, change to 100 during prod
                block=1000,  # TODO: Every 1 second, change to 5 during prod
            ),
        )

        events: list[str] = []

        for _, messages in event_batch:
            for message_id, fields in messages:
                self.last_id = message_id
                events.append(fields["event"])

        return events


async def main() -> None:
    worker: IngestionWorker = IngestionWorker()
    logger.info("Ingestion", "Ingestion worker started.")

    while True:
        try:
            events = await worker.read_batch()

            if not events:
                continue

            logger.debug("Ingestion", f"Read {len(events)} from redis")
        except Exception as e:
            logger.error("Ingestion", f"Ingestion error: {e}")
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Ingestion", "Error running ingestion service")
