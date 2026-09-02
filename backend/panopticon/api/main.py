from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Generator
from uuid import UUID
from panopticon.events.models import BaseEvent
from panopticon.adapters.postgres import Database
from panopticon.adapters.redis import RedisClient

app = FastAPI(title="Panopticon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_database() -> Generator[Database, None, None]:
    """Generator for dependency injection"""

    database = Database()
    try:
        yield database
    finally:
        database.close()


@app.get("/events/stream")
async def stream_events(request: Request):
    redis = RedisClient()

    async def event_generator():
        try:
            async for event in redis.stream_events():
                if await request.is_disconnected():
                    break

                yield f"data: {event}\n\n"
        finally:
            await redis.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/events/{event_id}", response_model=BaseEvent)
def get_event(
    event_id: UUID,
    database: Database = Depends(get_database),
) -> BaseEvent:

    event: BaseEvent | None = database.get_event_by_id(str(event_id))

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return event
