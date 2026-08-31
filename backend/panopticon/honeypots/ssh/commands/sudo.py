from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import HOSTNAME, current_user
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "sudo"
MAN = "sudo - execute a command as another user"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    user = current_user(session)
    if not args:
        return "usage: sudo -h | -K | -k | -V"

    if user == "root":
        return ""

    return f"{user} is not in the sudoers file.  This incident will be reported to {HOSTNAME}."
