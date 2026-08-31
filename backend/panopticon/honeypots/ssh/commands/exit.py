from asyncssh import SSHServerChannel, SSHServerConnection
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "exit"
MAN = "exits the system"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    chan.close()
    conn.close()
    return ""
