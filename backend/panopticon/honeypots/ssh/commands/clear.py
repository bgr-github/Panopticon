from asyncssh import SSHServerChannel, SSHServerConnection
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "clear"
MAN = "clear - clear the terminal screen"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return "\033[H\033[2J\033[3J"
