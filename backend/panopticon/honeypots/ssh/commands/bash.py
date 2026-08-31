from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "bash"
MAN = "bash - GNU Bourne-Again SHell"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return "bash: cannot set terminal process group: Inappropriate ioctl for device\r\nbash: no job control in this shell"
