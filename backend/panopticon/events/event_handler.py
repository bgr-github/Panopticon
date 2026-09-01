import asyncio
from panopticon.events.models import BaseEvent
from panopticon.config.constants import Module
from panopticon.observability.logging import logger
from panopticon.adapters.redis import RedisClient


class EventHandler:

    redis: RedisClient

    def __init__(self) -> None:
        self.redis: RedisClient = RedisClient()

    async def publish(self, event: BaseEvent) -> str:
        """Asynchronously pushes the event to the redis stream"""

        return await self.redis.append_stream(event)

    def publish_background(self, event: BaseEvent) -> None:
        """Pushes the event to the redis stream in the background"""

        task = asyncio.create_task(self.publish(event))
        task.add_done_callback(self._publish_callback)

    def _publish_callback(self, task: asyncio.Task[str | None]) -> None:
        """Callback to catch any results which failed to publish"""

        try:
            task.result()
        except Exception as e:
            logger.exception(Module.EVENT_HANDLER, "Error publishing task")

    async def close(self) -> None:
        """Gracefully close redis connection"""

        await self.redis.close()
