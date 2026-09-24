import asyncio
from unittest.mock import Mock

import asyncssh
import pytest
import pytest_asyncio
from panopticon.events.event_handler import EventHandler
from panopticon.events.models import Command, LoginAttempt
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
