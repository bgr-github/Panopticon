from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import get_cwd, current_user
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "env"
MAN = "env - print the environment"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    user = current_user(session)
    return "\r\n".join(
        [
            f"USER={user}",
            f"LOGNAME={user}",
            "HOME=/root",
            "SHELL=/bin/bash",
            f"PWD={get_cwd(session)}",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG=C.UTF-8",
        ]
    )
