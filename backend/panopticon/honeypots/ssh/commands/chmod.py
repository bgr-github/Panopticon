from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "chmod"
MAN = "chmod - change file mode bits"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    if len(args) < 2:
        return "chmod: missing operand"

    return ""
