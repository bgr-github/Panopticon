import logging

from asyncssh import SSHServerChannel, SSHServerSession

from panopticon.events.event_handler import EventHandler
from panopticon.honeypots.ssh.command_handler import CommandHandler
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.persona import MOTD

logger = logging.getLogger("SSH")
MAX_INPUT = 16384


class ShellSession(SSHServerSession):
    """A simulated shell with PTY, exec, EOF and stream framing support."""

    def __init__(self, event_handler: EventHandler, session: SSHSessionContext) -> None:
        self.session = session
        self.event_handler = event_handler
        self.buffer = ""
        self.interactive = False
        self.exec_command: str | None = None
        self.finished = False

    def connection_made(self, chan: SSHServerChannel) -> None:
        self.chan = chan
        self.handler = CommandHandler(chan, self.session, self.event_handler)

    def pty_requested(self, term_type, term_size, term_modes) -> bool:
        self.interactive = True
        self.session.environment["TERM"] = term_type
        return True

    def shell_requested(self) -> bool:
        return True

    def exec_requested(self, command: str) -> bool:
        self.exec_command = command
        return True

    def session_started(self) -> None:
        if self.exec_command is not None:
            self._run(self.exec_command)
            self._finish()
        elif self.interactive:
            self.chan.write(MOTD)
            self._prompt_input()

    def data_received(self, data: str, datatype: int | None) -> None:
        if self.finished:
            return
        self.buffer += data
        while "\n" in self.buffer:
            command, self.buffer = self.buffer.split("\n", 1)
            if len(command) > MAX_INPUT:
                self._overflow()
                return
            self._run(command.rstrip("\r"))
            if self.finished:
                return
            self._prompt_input()
        if len(self.buffer) > MAX_INPUT:
            self._overflow()

    def eof_received(self) -> bool:
        if self.buffer and not self.finished:
            self._run(self.buffer)
            self.buffer = ""
        self._finish()
        return False

    def signal_received(self, signal: str) -> None:
        if signal == "INT" and not self.finished:
            self.buffer = ""
            self.session.last_status = 130
            self.chan.write("\n")
            self._prompt_input()
        elif signal in ("TERM", "HUP"):
            self.session.last_status = 128 + (15 if signal == "TERM" else 1)
            self._finish()

    def _run(self, command: str) -> None:
        if len(command) > MAX_INPUT:
            self._overflow()
            return
        try:
            output = self.handler.handle_input(command)
            if output:
                self.chan.write(output + "\n")
            if self.handler.stderr:
                self.chan.write_stderr(self.handler.stderr)
            if self.handler.closed:
                self._finish()
        except Exception:
            logger.exception("Command handler failed")
            self.session.last_status = 1
            self.chan.write_stderr("bash: internal error\n")

    def _overflow(self) -> None:
        self.chan.write_stderr("bash: input line too long\n")
        self.session.last_status = 2
        self.buffer = ""
        self._finish()

    def _finish(self) -> None:
        if not self.finished:
            self.finished = True
            self.chan.exit(self.session.last_status)

    def _prompt_input(self) -> None:
        if self.interactive and not self.finished:
            self.chan.write(self.session.prompt)
