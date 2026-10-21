import asyncio
from unittest.mock import Mock

import asyncssh
import pytest
import pytest_asyncio
from panopticon.events.event_handler import EventHandler
from panopticon.events.models import Command, LoginAttempt
from panopticon.honeypots.ssh.server import HoneypotServer
from panopticon.honeypots.ssh.persona import SSH_VERSION


@pytest_asyncio.fixture
async def ssh_client():
    events = Mock(spec=EventHandler)
    host_key = asyncssh.generate_private_key("ssh-ed25519")

    async with asyncssh.create_server(
        lambda: HoneypotServer(events),
        host="127.0.0.1",
        port=0,
        server_host_keys=[host_key],
        server_version=SSH_VERSION,
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
    return await asyncio.wait_for(shell.stdout.readuntil("$ "), timeout=5)


@pytest.mark.asyncio
async def test_login_opens_shell(ssh_client):
    connection, events = ssh_client

    async with connection.create_process(term_type="xterm") as shell:
        response = await read_prompt(shell)

        assert "Welcome to Ubuntu 24.04 LTS" in response
        assert response.endswith("test-user@web-01:~$ ")

        login_events = [
            call.args[0] for call in events.publish.call_args_list if isinstance(call.args[0], LoginAttempt)
        ]

        assert len(login_events) == 1
        assert login_events[0].username == "test-user"
        assert login_events[0].success is True


@pytest.mark.asyncio
async def test_exec_has_output_status_and_event(ssh_client):
    connection, events = ssh_client
    result = await asyncio.wait_for(connection.run("uname -s; whoami"), 5)
    assert result.stdout == "Linux\ntest-user\n"
    assert result.stderr == ""
    assert result.exit_status == 0
    assert "OpenSSH_9.6p1" in connection.get_extra_info("server_version")
    commands = [call.args[0].input for call in events.publish.call_args_list
                if isinstance(call.args[0], Command)]
    assert commands == ["uname -s; whoami"]


@pytest.mark.asyncio
async def test_exec_failure_and_exit_status(ssh_client):
    connection, _ = ssh_client
    result = await asyncio.wait_for(connection.run("missing-command"), 5)
    assert result.stdout == ""
    assert result.exit_status == 127
    assert "command not found" in result.stderr
    result = await asyncio.wait_for(connection.run("exit 7"), 5)
    assert result.exit_status == 7


@pytest.mark.asyncio
async def test_non_pty_shell_and_eof(ssh_client):
    connection, events = ssh_client
    async with connection.create_process() as shell:
        shell.stdin.write("echo one\npwd\nwhoami")
        shell.stdin.write_eof()
        result = await asyncio.wait_for(shell.wait(), 5)
    assert result.stdout == "one\n/home/test-user\ntest-user\n"
    assert result.exit_status == 0
    commands = [call.args[0].input for call in events.publish.call_args_list
                if isinstance(call.args[0], Command)]
    assert commands == ["echo one", "pwd", "whoami"]


@pytest.mark.asyncio
async def test_channel_working_directories_are_independent(ssh_client):
    connection, _ = ssh_client
    await asyncio.wait_for(connection.run("cd /tmp"), 5)
    result = await asyncio.wait_for(connection.run("pwd"), 5)
    assert result.stdout == "/home/test-user\n"


@pytest.mark.asyncio
async def test_interactive_commands_and_exit(ssh_client):
    connection, _ = ssh_client
    async with connection.create_process(term_type="xterm") as shell:
        await read_prompt(shell)
        shell.stdin.write("cd /etc\n")
        response = await read_prompt(shell)
        assert response.endswith("test-user@web-01:/etc$ ")
        shell.stdin.write("exit\n")
        result = await asyncio.wait_for(shell.wait(), 5)
        assert result.exit_status == 0
