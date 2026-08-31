from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import KERNEL
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "uname"
MAN = "uname - print system information"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    if "-a" in args or "--all" in args:
        return KERNEL

    return "Linux"
