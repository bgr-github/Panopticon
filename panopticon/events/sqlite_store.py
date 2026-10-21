import sqlite3
from contextlib import closing
from datetime import timezone
from pathlib import Path

from panopticon.events.models import BaseEvent


class SQLiteEventStore:
    """Persists complete event payloads with indexed fields for historical queries."""

    path: Path
    timeout: float

    def __init__(self, path: Path, timeout: float = 5.0) -> None:
        """Initialises SQLite storage configuration without opening the database

        Args:
            path (Path): Location of the SQLite database file
            timeout (float): Seconds to wait for a database write lock
        """

        self.path = path
        self.timeout = timeout

    def initialise(self) -> None:
        """Creates the database, event table and indexes, and enables WAL journalling

        Raises:
            RuntimeError: Database schema version is newer than this implementation
            sqlite3.Error: Database cannot be opened or initialised
        """

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with closing(self._connect()) as connection:
            version: int = connection.execute("PRAGMA user_version").fetchone()[0]

            if version > 1:
                raise RuntimeError(f"Unsupported event database schema version: {version}")

            connection.execute("PRAGMA journal_mode = WAL")

            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY NOT NULL,
                        timestamp TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        src_ip TEXT NOT NULL,
                        src_port INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        payload TEXT NOT NULL
                    )
                    """
                )
                connection.execute("CREATE INDEX IF NOT EXISTS events_timestamp ON events(timestamp, id)")
                connection.execute("CREATE INDEX IF NOT EXISTS events_session ON events(session_id, timestamp)")
                connection.execute("CREATE INDEX IF NOT EXISTS events_source ON events(src_ip, timestamp)")
                connection.execute("CREATE INDEX IF NOT EXISTS events_type ON events(event_type, timestamp)")
                connection.execute("PRAGMA user_version = 1")

    def save(self, event: BaseEvent) -> None:
        """Commits an event and preserves its complete JSON payload

        Args:
            event (BaseEvent): Event to persist; an existing ID is left unchanged

        Raises:
            sqlite3.Error: Event could not be committed
            ValueError: Event timestamp does not include a timezone
        """

        if event.timestamp.tzinfo is None:
            raise ValueError("Event timestamps must include a timezone")

        timestamp: str = event.timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds")
        payload: str = event.model_dump_json()

        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO events (id, timestamp, session_id, src_ip, src_port, event_type, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    str(event.id),
                    timestamp,
                    event.session_id,
                    event.src_ip,
                    event.src_port,
                    event.event_type.value,
                    payload,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        """Opens an operation-scoped connection with full commit synchronisation

        Returns:
            sqlite3.Connection: Connection owned and closed by the calling operation
        """

        connection: sqlite3.Connection = sqlite3.connect(self.path, timeout=self.timeout)

        try:
            connection.execute("PRAGMA synchronous = FULL")

        except sqlite3.Error:
            connection.close()
            raise

        return connection
