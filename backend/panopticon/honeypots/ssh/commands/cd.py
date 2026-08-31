from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import is_dir, resolve_path, set_cwd
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "cd"
MAN = "cd - change the shell working directory"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    target = resolve_path(session, args[0] if args else "~")

    if not is_dir(target):
        return f"cd: {args[0] if args else target}: No such file or directory"

    set_cwd(session, target)
    return ""
