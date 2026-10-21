import asyncio
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import asyncssh
import pytest

from panopticon.honeypots.ssh import server as ssh_server


@pytest.mark.asyncio
async def test_service_shutdown_persists_active_connection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Checks service startup and persistence of disconnect events during shutdown

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
        monkeypatch (pytest.MonkeyPatch): Fixture used to isolate service configuration
    """

    key_path: Path = tmp_path / "host_key"
    database_path: Path = tmp_path / "events.sqlite3"
    host_key: asyncssh.SSHKey = asyncssh.generate_private_key("ssh-ed25519")
    host_key.write_private_key(key_path)
    ready: asyncio.Event = asyncio.Event()
    listener: asyncssh.SSHAcceptor | None = None

    monkeypatch.setattr(ssh_server.settings.ssh, "host", "127.0.0.1")
    monkeypatch.setattr(ssh_server.settings.ssh, "host_key_path", [key_path])
    monkeypatch.setattr(ssh_server.settings.database, "path", database_path)

    async def create_listener(
        server_factory: Callable[[], ssh_server.HoneypotServer],
        host: str,
        port: int,
        server_host_keys: list[Path],
        server_version: str,
        max_line_length: int,
        login_timeout: int,
    ) -> asyncssh.SSHAcceptor:
        """Starts the real SSH listener on an available test port

        Args:
            server_factory (Callable[[], HoneypotServer]): Service connection factory
            host (str): Local address supplied by the service
            port (int): Configured port, replaced with an available test port
            server_host_keys (list[Path]): Temporary host key paths
            server_version (str): Server identity supplied by the service
            max_line_length (int): Configured terminal input limit
            login_timeout (int): Configured authentication timeout

        Returns:
            SSHAcceptor: Listening SSH server
        """

        nonlocal listener

        listener = await asyncssh.create_server(
            server_factory,
            host=host,
            port=0,
            server_host_keys=server_host_keys,
            server_version=server_version,
            max_line_length=max_line_length,
            login_timeout=login_timeout,
        )
        ready.set()

        return listener

    monkeypatch.setattr(ssh_server, "create_server", create_listener)
    service: asyncio.Task[None] = asyncio.create_task(ssh_server.main())
    startup: asyncio.Task[bool] = asyncio.create_task(ready.wait())

    try:
        await asyncio.wait((startup, service), timeout=5, return_when=asyncio.FIRST_COMPLETED)

        if service.done():
            await service

        assert ready.is_set()
        assert listener is not None

        async with asyncssh.connect(
            "127.0.0.1",
            port=listener.get_port(),
            username="test-user",
            password="dummy-password",
            preferred_auth="password",
            client_keys=[],
            known_hosts=None,
            config=None,
            connect_timeout=5,
        ) as connection:
            service.cancel()

            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(service, timeout=5)

            await asyncio.wait_for(connection.wait_closed(), timeout=5)

    finally:
        startup.cancel()

        if not service.done():
            service.cancel()

        await asyncio.gather(startup, service, return_exceptions=True)

    with closing(sqlite3.connect(database_path)) as database:
        rows: list[tuple[str, str]] = database.execute(
            "SELECT event_type, session_id FROM events ORDER BY rowid"
        ).fetchall()

    assert [row[0] for row in rows] == ["connection_open", "login_attempt", "connection_closed"]
    assert len({row[1] for row in rows}) == 1
