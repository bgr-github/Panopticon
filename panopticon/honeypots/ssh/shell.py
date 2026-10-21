import logging
from collections.abc import Mapping

from asyncssh import SSHServerChannel, SSHServerSession

from panopticon.events.event_handler import EventHandler
from panopticon.honeypots.ssh.command_handler import CommandHandler
from panopticon.honeypots.ssh.context import SSHSessionContext
from panopticon.honeypots.ssh.persona import MOTD

logger = logging.getLogger("SSH")
MAX_INPUT = 16384


class ShellSession(SSHServerSession):
    """A simulated shell with PTY, exec, EOF and stream framing support."""

    session: SSHSessionContext
    event_handler: EventHandler
    chan: SSHServerChannel
    handler: CommandHandler
    buffer: str
    interactive: bool
    exec_command: str | None
    finished: bool

    def __init__(self, event_handler: EventHandler, session: SSHSessionContext) -> None:
        """Initialises the simulated shell and input buffer

        Args:
            event_handler (EventHandler): Handler used to publish command events
            session (SSHSessionContext): Session state used by the shell
        """

        self.session = session
        self.event_handler = event_handler
        self.buffer = ""
        self.interactive = False
        self.exec_command: str | None = None
        self.finished = False

    def connection_made(self, chan: SSHServerChannel) -> None:
        """Callback made when the client channel is opened

        Args:
            chan (SSHServerChannel): Client channel used for shell input and output
        """

        self.chan = chan
        self.handler = CommandHandler(chan, self.session, self.event_handler)

    def pty_requested(
        self,
        term_type: str,
        term_size: tuple[int, int, int, int],
        term_modes: Mapping[int, int],
    ) -> bool:
        """Callback made when the client requests a pseudo-terminal

        Args:
            term_type (str): Terminal type supplied by the client
            term_size (tuple[int, int, int, int]): Terminal width, height and pixel dimensions
            term_modes (Mapping[int, int]): Terminal mode values supplied by the client

        Returns:
            bool: True to accept the terminal request
        """

        self.interactive = True
        self.session.environment["TERM"] = term_type
        return True

    def shell_requested(self) -> bool:
        """Callback made when the client requests a shell

        Returns:
            bool: True to accept the shell request
        """

        return True

    def exec_requested(self, command: str) -> bool:
        """Callback made when the client requests execution of a command

        Args:
            command (str): Command to run when the session starts

        Returns:
            bool: True to accept the command request
        """

        self.exec_command = command
        return True

    def session_started(self) -> None:
        """Starts the requested command or displays the interactive login banner"""

        if self.exec_command is not None:
            self._run(self.exec_command)
            self._finish()
        elif self.interactive:
            self.chan.write(MOTD)
            self._prompt_input()

    def data_received(self, data: str, datatype: int | None) -> None:
        """Buffers client input and processes complete command lines

        Args:
            data (str): Input received from the client
            datatype (int | None): SSH extended data type, or None for normal input
        """

        if self.finished:
            return

        self.buffer += data

        while "\n" in self.buffer:
            command: str
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
        """Processes remaining buffered input and closes the shell

        Returns:
            bool: False to close the channel after end of input
        """

        if self.buffer and not self.finished:
            self._run(self.buffer)
            self.buffer = ""

        self._finish()
        return False

    def signal_received(self, signal: str) -> None:
        """Handles client signals by interrupting or closing the shell

        Args:
            signal (str): SSH signal name without the SIG prefix
        """

        if signal == "INT" and not self.finished:
            self.buffer = ""
            self.session.last_status = 130
            self.chan.write("\n")
            self._prompt_input()
        elif signal in ("TERM", "HUP"):
            self.session.last_status = 128 + (15 if signal == "TERM" else 1)
            self._finish()

    def _run(self, command: str) -> None:
        """Processes a command and sends its output and errors to the client

        Args:
            command (str): Complete command line to process
        """

        if len(command) > MAX_INPUT:
            self._overflow()
            return

        try:
            output: str = self.handler.handle_input(command)

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
        """Reports oversized input and closes the shell with an error status"""

        self.chan.write_stderr("bash: input line too long\n")
        self.session.last_status = 2
        self.buffer = ""
        self._finish()

    def _finish(self) -> None:
        """Closes the shell using the last command exit status"""

        if not self.finished:
            self.finished = True
            self.chan.exit(self.session.last_status)

    def _prompt_input(self) -> None:
        """Displays the current prompt when the shell is interactive"""

        if self.interactive and not self.finished:
            self.chan.write(self.session.prompt)
