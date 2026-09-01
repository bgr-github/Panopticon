from redis.asyncio import Redis
from typing import cast
from panopticon.config.settings import settings
from panopticon.events.models import BaseEvent

# Types for Pylance as Redis async doesnt have best Typing
RedisStreamMessage = tuple[str, dict[str, str]]
RedisStreamBatch = list[tuple[str, list[RedisStreamMessage]]]


class RedisClient:

    redis: Redis
    last_id: str = "$"

    def __init__(self) -> None:
        self.redis = Redis.from_url(
            str(settings.redis.dsn),
            db=0,
            decode_responses=True,
            socket_timeout=None,
        )

    async def append_stream(self, event: BaseEvent) -> str:
        """Pushes a single event to Redis stream"""

        message_id = await self.redis.xadd(
            settings.redis.stream_name,
            {
                "event": event.model_dump_json(),
            },
        )

        return str(message_id)

    async def read_batch(self, batch_size: int, wait_time_ms: int) -> list[str]:
        """Retrieve event data from redis stream"""

        event_batch = cast(
            RedisStreamBatch,
            await self.redis.xread(
                streams={settings.redis.stream_name: self.last_id},
                count=batch_size,
                block=wait_time_ms,
            ),
        )

        events: list[str] = []

        # Adds raw event json to event list
        for _, messages in event_batch:
            for message_id, fields in messages:
                events.append(fields["event"])
                self.last_id = message_id

        return events

    async def close(self) -> None:
        """Gracefuly close connection"""

        await self.redis.aclose()
