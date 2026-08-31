from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import HOSTNAME
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "hostname"
MAN = "hostname - show or set the system's host name"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return HOSTNAME
