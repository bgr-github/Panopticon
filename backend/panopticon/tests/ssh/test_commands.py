from unittest.mock import Mock

from panopticon.events.event_handler import EventHandler
from panopticon.honeypots.ssh.command_handler import CommandHandler
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.shell import ShellSession

session = SSHSessionContext(
    id="test-session",
    src_ip="127.0.0.1",
    src_port=12345,
    start_time=0.0,
)


def test_echo_returns_words_on_one_line():
    channel = Mock()
    events = Mock(spec=EventHandler)
    handler = CommandHandler(channel, session, events)

    response = handler.handle_input("echo hello world")

    assert response == "hello world"


def test_unknown_command_returns_correctly():
    channel = Mock()
    events = Mock(spec=EventHandler)
    handler = CommandHandler(channel, session, events)

    value = handler.handle_input("TestCommand")

    assert value == "bash: TestCommand: command not found"
