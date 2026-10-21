from unittest.mock import Mock

import pytest

from panopticon.honeypots.ssh.command_handler import CommandHandler
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.shell import ShellSession, MAX_INPUT


@pytest.fixture
def handler() -> CommandHandler:
    """Creates a command handler with an isolated Ubuntu session

    Returns:
        CommandHandler: Handler using mock channel and event publisher
    """

    session = SSHSessionContext("test", "127.0.0.1", 2222, 0)
    session.initialise_user("ubuntu")
    return CommandHandler(Mock(), session, Mock())


@pytest.mark.parametrize(("command", "expected"), [
    ('echo "hello world"', "hello world"),
    ("echo '$HOME'", "$HOME"),
    ("echo $HOME", "/home/ubuntu"),
    ("whoami", "ubuntu"),
    ("id -u", "1000"),
    ("uname -s", "Linux"),
    ("false && echo no || echo yes", "yes"),
    ("true || echo no; echo yes", "yes"),
    ("cd /etc; pwd; cd -", "/etc\n/home/ubuntu"),
    ("echo hello > /tmp/result; cat /tmp/result", "hello"),
    ("echo first > /tmp/result; echo second >> /tmp/result; cat /tmp/result", "first\nsecond"),
    ("echo hello | wc -l", "1"),
    ("cat /etc/os-release | grep VERSION_ID", 'VERSION_ID="24.04"'),
    ("echo exit_gracefully", "exit_gracefully"),
])
def test_shell_behaviour(handler: CommandHandler, command: str, expected: str) -> None:
    """Checks simulated shell output for the supplied command

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
        command (str): Command line to process
        expected (str): Expected standard output
    """

    assert handler.handle_input(command) == expected
    assert handler.stderr == ""
    assert not handler.closed


def test_raw_command_logged_once(handler: CommandHandler) -> None:
    """Checks that the original command is published exactly once

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
    """

    command = "  whoami; uname -s  "
    handler.handle_input(command)
    handler.event_handler.publish.assert_called_once()
    assert handler.event_handler.publish.call_args.args[0].input == command


def test_error_status_and_no_host_execution(handler: CommandHandler) -> None:
    """Checks failure status handling and rejection of command substitution

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
    """

    assert handler.handle_input("not-a-real-command || echo $?") == "127"
    assert "command not found" in handler.stderr
    assert handler.handle_input("echo $(whoami)") == ""
    assert handler.session.last_status == 2


def test_listing_and_root_persona(handler: CommandHandler) -> None:
    """Checks Ubuntu files and the root account identity

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
    """

    assert ".bashrc" in handler.handle_input("ls -la")
    assert "Ubuntu 24.04" in handler.handle_input("cat /etc/os-release")
    handler.session.initialise_user("root")
    assert handler.session.prompt == "root@web-01:~# "
    assert handler.handle_input("pwd; id -u") == "/root\n0"


def test_filesystem_isolation(handler: CommandHandler) -> None:
    """Checks that virtual files are isolated between connections

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
    """

    handler.handle_input("echo marker > /tmp/private")
    other = SSHSessionContext("other", "127.0.0.1", 2223, 0)
    with pytest.raises(FileNotFoundError):
        other.fs.read_file("/tmp/private")


def test_fragmented_input_and_multiple_lines(handler: CommandHandler) -> None:
    """Checks input buffering across fragmented and combined command lines

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
    """

    shell = ShellSession(handler.event_handler, handler.session)
    channel = Mock()
    shell.connection_made(channel)
    shell.data_received("ec", None)
    channel.write.assert_not_called()
    shell.data_received("ho first\npwd\n", None)
    assert [call.args[0] for call in channel.write.call_args_list] == [
        "first\n", "/home/ubuntu\n"]


def test_input_limit_and_exit_stop_processing(handler: CommandHandler) -> None:
    """Checks that oversized input closes the shell and stops further processing

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
    """

    shell = ShellSession(handler.event_handler, handler.session)
    channel = Mock()
    shell.connection_made(channel)
    shell.data_received("x" * (MAX_INPUT + 1), None)
    channel.exit.assert_called_once_with(2)
    shell.data_received("whoami\n", None)
    channel.write.assert_not_called()


def test_eof_runs_final_fragment(handler: CommandHandler) -> None:
    """Checks that end of input processes an unterminated command line

    Args:
        handler (CommandHandler): Handler fixture with an isolated Ubuntu session
    """

    shell = ShellSession(handler.event_handler, handler.session)
    channel = Mock()
    shell.connection_made(channel)
    shell.data_received("whoami", None)
    shell.eof_received()
    channel.write.assert_called_once_with("ubuntu\n")
    channel.exit.assert_called_once_with(0)
