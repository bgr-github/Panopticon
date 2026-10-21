import asyncio
import logging
import sqlite3
import time
from collections.abc import AsyncIterator

from starlette.requests import Request

from panopticon.api.models import EventFilters
from panopticon.api.repository import EventReader
from panopticon.events.models import BaseEvent

logger: logging.Logger = logging.getLogger("API Stream")


async def stream_events(
    request: Request,
    reader: EventReader,
    position: int,
    filters: EventFilters,
    poll_interval: float,
    heartbeat_interval: float,
) -> AsyncIterator[str]:
    """Streams committed events with bounded reads, keepalives and disconnect handling

    Args:
        request (Request): Client request used to detect disconnects
        reader (EventReader): Shared-database query implementation
        position (int): Exclusive starting insertion position
        filters (EventFilters): Filters applied to subsequent event batches
        poll_interval (float): Seconds between database polls when caught up
        heartbeat_interval (float): Maximum quiet interval before a keepalive comment

    Yields:
        str: SSE frames containing event IDs and JSON payloads or keepalive comments
    """

    last_sent: float = time.monotonic()
    yield "retry: 2000\n: connected\n\n"

    while not await request.is_disconnected():
        try:
            batch: list[tuple[int, BaseEvent]] = await asyncio.to_thread(reader.stream_batch, position, filters)

        except sqlite3.Error:
            logger.exception("Live event database query failed")
            yield 'event: stream_error\ndata: {"detail":"Event database unavailable"}\n\n'
            return

        for position, event in batch:
            if await request.is_disconnected():
                return

            yield f"id: {event.id}\nevent: event\ndata: {event.model_dump_json()}\n\n"
            last_sent = time.monotonic()

        if time.monotonic() - last_sent >= heartbeat_interval:
            yield ": keepalive\n\n"
            last_sent = time.monotonic()

        if len(batch) < 100:
            await asyncio.sleep(poll_interval)
