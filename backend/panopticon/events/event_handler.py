import asyncio
from redis.asyncio import Redis
from panopticon.events.models import BaseEvent
from panopticon.config.settings import settings
from panopticon.observability.logging import logger


class EventHandler:

    redis: Redis

    def __init__(self):
        self.redis = Redis.from_url(str(settings.redis.dsn), db=0, decode_responses=True)

    async def publish(self, event: BaseEvent) -> str:
        """Asynchronously pushes the event to the redis stream"""

        message_id = await self.redis.xadd(
            settings.redis.stream_name,
            {
                "event": event.model_dump_json(),
            },
        )

        logger.debug("Event Handler", f"Event Published: {event.model_dump_json()}")

        return message_id.decode() if isinstance(message_id, bytes) else str(message_id)

    def publish_background(self, event: BaseEvent) -> None:
        """Pushes the event to the redis stream in the background"""

        task = asyncio.create_task(self.publish(event))
        task.add_done_callback(self._publish_callback)

    def _publish_callback(self, task: asyncio.Task[str]) -> None:
        """Callback to catch any results which failed to publish"""

        try:
            task.result()
        except Exception as e:
            logger.error("Event Handler", f"Failed to publish event: {e}")
