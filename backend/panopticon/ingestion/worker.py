import asyncio
import json
from pydantic import ValidationError
from panopticon.events.models import BaseEvent
from panopticon.config.constants import Module
from panopticon.observability.logging import logger
from panopticon.adapters.redis import RedisClient
from panopticon.adapters.postgres import Database, InvalidEventError


class IngestionWorker:

    redis: RedisClient
    database: Database

    def __init__(self) -> None:
        self.redis = RedisClient()
        self.database = Database()

        logger.info(Module.INGESTION, "Ingestion worker started.")

    def store_in_database(self, event: BaseEvent):
        self.database.store_event(event)

    async def close(self) -> None:
        await self.redis.close()
        self.database.close()


async def main() -> None:
    worker: IngestionWorker = IngestionWorker()

    # Main ingestion loop
    try:
        while True:
            try:
                events = await worker.redis.read_batch(batch_size=100, wait_time_ms=5000)

                # Continue if no events are found
                if not events:
                    continue

                # Loop events if they are
                for raw_event in events:
                    event = worker.database.validate_event(raw_event)
                    if event is not None:
                        worker.database.store_event(event)
                    else:
                        logger.error(Module.INGESTION, "Error validating event")
                        raise InvalidEventError

            except Exception as e:
                logger.exception(Module.INGESTION, "Failed to ingest")
                await asyncio.sleep(1)
    finally:

        # Graceful shutdown
        logger.info(Module.INGESTION, "Worker shutting down...")
        await worker.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(Module.INGESTION, "Unknown error occured.")
    except KeyboardInterrupt:
        logger.info(Module.INGESTION, "Shutting down...")
