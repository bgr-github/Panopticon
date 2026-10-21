import asyncio
import logging

from panopticon.events.models import BaseEvent
from panopticon.events.store import EventStore

logger: logging.Logger = logging.getLogger("Event Collector")


class EventHandler:

    store: EventStore
    _queue: asyncio.Queue[BaseEvent | None]
    _worker: asyncio.Task[None] | None
    _accepting: bool

    def __init__(self, store: EventStore, capacity: int = 1000) -> None:
        """Initialises a bounded event collector with an injected storage implementation

        Args:
            store (EventStore): Storage used by the background writer
            capacity (int): Maximum number of events waiting to be written
        """

        if capacity < 1:
            raise ValueError("Event queue capacity must be at least one")

        self.store = store
        self._queue = asyncio.Queue(maxsize=capacity)
        self._worker = None
        self._accepting = False

    async def start(self) -> None:
        """Initialises storage and starts the writer before events can be published"""

        if self._worker is not None:
            raise RuntimeError("Event collector has already been started")

        await asyncio.to_thread(self.store.initialise)

        self._worker = asyncio.create_task(self._write_events(), name="event-writer")
        self._accepting = True

    def publish(self, event: BaseEvent) -> None:
        """Queues a snapshot of an event without blocking the SSH event loop

        Args:
            event (BaseEvent): Event to be committed by the background writer

        Raises:
            RuntimeError: Collector is not accepting events
            asyncio.QueueFull: Pending event capacity has been reached
            Exception: Background storage operation failed
        """

        if not self._accepting or self._worker is None:
            raise RuntimeError("Event collector is not accepting events")

        if self._worker.done():
            self._worker.result()
            raise RuntimeError("Event collector writer has stopped")

        try:
            self._queue.put_nowait(event.model_copy(deep=True))

        except asyncio.QueueFull:
            logger.error("Event queue is full; event %s was not accepted", event.id)
            raise

    async def flush(self) -> None:
        """Waits for queued events to commit and propagates writer failures

        Raises:
            RuntimeError: Collector has not been started
            Exception: Storage failed while writing an event
        """

        if self._worker is None:
            raise RuntimeError("Event collector has not been started")

        pending: asyncio.Task[None] = asyncio.create_task(self._queue.join())

        try:
            await asyncio.wait((pending, self._worker), return_when=asyncio.FIRST_COMPLETED)

            if self._worker.done():
                await self._worker

            else:
                await pending

        finally:
            if not pending.done():
                pending.cancel()

            await asyncio.gather(pending, return_exceptions=True)

    async def wait(self) -> None:
        """Monitors the writer so a storage failure can stop the listening service

        Raises:
            RuntimeError: Collector has not been started
            Exception: Background storage operation failed
        """

        if self._worker is None:
            raise RuntimeError("Event collector has not been started")

        await asyncio.shield(self._worker)

    async def close(self) -> None:
        """Stops accepting events and drains the writer before returning

        Raises:
            Exception: Storage failed before all accepted events were committed
        """

        self._accepting = False

        if self._worker is None:
            return

        await self.flush()

        if not self._worker.done():
            self._queue.put_nowait(None)

        await self._worker

    async def _write_events(self) -> None:
        """Commits events sequentially in a worker thread and reports storage failures"""

        while True:
            event: BaseEvent | None = await self._queue.get()

            try:
                if event is None:
                    return

                await asyncio.to_thread(self.store.save, event)

            except Exception:
                logger.exception("Event writer failed; queued events may not have been persisted")
                raise

            finally:
                self._queue.task_done()
