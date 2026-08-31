from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import current_user
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "whoami"
MAN = "whoami - print effective user name"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return current_user(session)
