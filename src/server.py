import asyncio
import asyncssh
import argparse
import logging
import sys
import uuid
import time
from pathlib import Path
from logger import log_event, setup_logging
from config import load_profile, ConfigError
from command_handler import CommandHandler

BASE_DIR = Path(__file__).resolve().parent.parent


async def handle_client(process):
    """
    Handles authenticated client session

    Reads commands from the SSH connection line by line and logs each one
    it will then dispatch to the CommandHandler until the client exits.
    """

    session = process.get_extra_info("session")
    profile = process.get_extra_info("profile")

    username = session.get("username") or process.get_extra_info("username")
    session["username"] = username

    hostname = profile["host"]["hostname"]

    process.stdout.write(profile.get("banner", "") + "\n")

    handle = CommandHandler(process)

    try:
        process.stdout.write(f"{username}@{hostname} $>")
        async for command in process.stdin:
            command = command.rstrip("\n")

            if command:
                log_event(
                    "user_input",
                    input=command,
                    _id=session["id"],
                    src_ip=session["src_ip"],
                    src_port=session["src_port"],
                )

                if command == "exit":
                    process.stdout.write("Goodbye!\n")
                    break
                handle.command(command)
            process.stdout.write(f"{username}@{hostname} $>")
        process.exit(0)
    except asyncssh.BreakReceived:
        pass


class PanopticonServer(asyncssh.SSHServer):
    def __init__(self, profile):
        self.profile = profile

    def connection_made(self, connection):
        """
        Called as soon as the client connects to the server before any authentication.

        Creates the session for that user and starts their session timer.
        """

        self.session = {}
        self.session["id"] = uuid.uuid4().hex[:12]
        self.session["src_ip"] = connection.get_extra_info("peername")[0]
        self.session["src_port"] = connection.get_extra_info("peername")[1]

        # Binds the session and profile to the connection and allows us to use it in handle_client()
        connection.set_extra_info(session=self.session)
        connection.set_extra_info(profile=self.profile)

        self.start_time = time.monotonic()

        log_event(
            "connection_open",
            _id=self.session["id"],
            src_ip=self.session["src_ip"],
            src_port=self.session["src_port"],
        )

    def connection_lost(self, exception):
        """Function called when connection closes"""

        if not hasattr(self, "session"):
            return

        log_event(
            "connection_close",
            _id=self.session["id"],
            duration=round(time.monotonic() - self.start_time, 3),
            error=str(exception) if exception else None,
        )

    def begin_auth(self, username):
        """Decide whether this user must authenticate. False skips auth entirely."""

        account = self._find_account(username)
        if account is None:
            return True  # unknown user: require auth (then fail in validate)
        return account["password"] != ""

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        """Validate a login attempt against the profile's account"""
        result = False
        account = self._find_account(username)

        if account is not None:
            expected_password = account["password"]
            if expected_password == "":
                # Empty configuration password means account needs no password
                result = not password
            else:
                result = password == expected_password

        if result:
            self.session["username"] = username

        log_event("login_attempt", _id=self.session["id"], username=username, password=password, success=result)
        return result

    def _find_account(self, username):
        """Return the account dict for username, or None if no such account."""
        for account in self.profile["accounts"]:
            if account["username"] == username:
                return account
        return None


async def main(args):
    setup_logging()
    profile = load_profile(args.profile)
    await asyncssh.create_server(
        lambda: PanopticonServer(profile),
        args.host,
        args.port,
        server_host_keys=[args.key],
        process_factory=lambda process: handle_client(process),
    )
    print("Panopticon SSH server is running on {}:{}".format(args.host, args.port))
    await asyncio.Future()


def parse_args():
    parser = argparse.ArgumentParser(description="Panopticon SSH honeypot")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind to.")
    parser.add_argument("--port", type=int, default=2222, help="Port to listen on.")
    parser.add_argument("--key", type=Path, default=BASE_DIR / "keys/ssh_host_key", help="Path to SSH host key.")
    parser.add_argument("--profile", type=Path, default=BASE_DIR / "config.yaml", help="Path to the persona profile.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(args))
    except ConfigError as error:
        sys.exit(f"Config error: {error}")
    except (OSError, asyncssh.Error) as error:
        sys.exit(f"Error starting server: {error}")
    except (asyncio.exceptions.CancelledError, KeyboardInterrupt):
        print("Server shutting down...")
