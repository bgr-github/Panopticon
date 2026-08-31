from panopticon.honeypots.ssh.command_handler import CommandHandler, registry
from panopticon.honeypots.ssh.context import SSHSessionContext


class FakeChannel:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def make_handler() -> tuple[CommandHandler, SSHSessionContext, FakeChannel, FakeConnection]:
    session = SSHSessionContext(
        _id="session-1",
        src_ip="203.0.113.10",
        src_port=49152,
        start_time=1.0,
        username="admin",
    )
    conn = FakeConnection()
    chan = FakeChannel()
    handler = CommandHandler(conn, session)
    handler.chan = chan

    return handler, session, chan, conn


def test_registry_loads_command_modules() -> None:
    assert "exit" in registry
    assert "whoami" in registry
    assert "ls" in registry
    assert "cat" in registry


def test_help_lists_available_commands() -> None:
    handler, _, _, _ = make_handler()

    output = handler.handle_input("help")

    assert "Available Commands:" in output
    assert "exit" in output
    assert "whoami" in output


def test_unknown_command_returns_command_not_found() -> None:
    handler, _, _, _ = make_handler()

    assert handler.handle_input("notreal").strip() == "notreal: command not found"


def test_whoami_uses_session_username() -> None:
    handler, _, _, _ = make_handler()

    assert handler.handle_input("whoami").strip() == "admin"


def test_pwd_cd_and_ls_share_session_cwd() -> None:
    handler, session, _, _ = make_handler()

    assert handler.handle_input("pwd").strip() == "/root"
    assert handler.handle_input("cd /etc") == ""
    assert getattr(session, "cwd") == "/etc"
    assert "passwd" in handler.handle_input("ls")


def test_cat_reads_fake_files() -> None:
    handler, _, _, _ = make_handler()

    output = handler.handle_input("cat /etc/passwd")

    assert "root:x:0:0:root" in output
    assert "ubuntu:x:1000:1000" in output


def test_exit_command_closes_channel_and_connection() -> None:
    handler, _, chan, conn = make_handler()

    assert handler.handle_input("exit") == ""
    assert chan.closed is True
    assert conn.closed is True
