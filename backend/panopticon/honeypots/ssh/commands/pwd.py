from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import get_cwd
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "pwd"
MAN = "pwd - print name of current working directory"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return get_cwd(session)
