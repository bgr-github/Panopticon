from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from panopticon.api.dependencies import get_database
from panopticon.adapters.postgres import Database
from panopticon.events.models import BaseEvent, EventType

router = APIRouter(
    prefix="/events",
    tags=["events"],
)


@router.get("", response_model=list[BaseEvent])
def get_recent_events(
    event_type: EventType | None = None,
    limit: int = 10,
    src_ip: str | None = None,
    src_port: int | None = None,
    session_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    database: Database = Depends(get_database),
) -> list[BaseEvent]:
    """Returns recent events

    Args:
        event_type (EventType | None, optional): Type of event derived from EventType. Defaults to None.
        limit (int, optional): Max number of results. Defaults to 10.
        src_ip (str | None, optional): Attacker IP. Defaults to None.
        src_port (int | None, optional): Attacker port. Defaults to None.
        session_id (str | None, optional): Get by session ID. Defaults to None.
        start_time (datetime | None, optional): Start time of events. Defaults to None.
        end_time (datetime | None, optional): End time of events. Defaults to None.
        database (Database, optional): Database connection. Defaults to Depends(get_database).

    Returns:
        list[BaseEvent]
    """

    return database.get_recent_events(
        limit=limit,
        event_type=event_type,
        src_ip=src_ip,
        src_port=src_port,
        session_id=session_id,
        start_time=start_time,
        end_time=end_time,
    )


@router.get("/{event_id}")
def get_event(
    event_id: str,
    database: Database = Depends(get_database),
) -> BaseEvent:
    """Get a single event

    Args:
        event_id (str): Event ID to filter for
        database (Database, optional): Database connection. Defaults to Depends(get_database).

    Raises:
        HTTPException: Raises in the event a result is not found

    Returns:
        BaseEvent
    """

    event: BaseEvent | None = database.get_event(event_id)

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


@router.get("/session/{session_id}")
def get_session(
    session_id: str,
    database: Database = Depends(get_database),
) -> list[BaseEvent]:
    """Returns a list of events belonging to a session

    Args:
        session_id (str): Session ID
        database (Database, optional): Database connection. Defaults to Depends(get_database).

    Returns:
        list[BaseEvent]
    """

    return database.get_session(session_id) or []
