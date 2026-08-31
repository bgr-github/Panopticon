from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import FILES, is_dir, resolve_path
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "cat"
MAN = "cat - concatenate files and print on the standard output"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    if not args:
        return ""

    output: list[str] = []
    for arg in args:
        path = resolve_path(session, arg)
        if is_dir(path):
            output.append(f"cat: {arg}: Is a directory")
        elif path in FILES:
            output.append(FILES[path].rstrip("\n"))
        else:
            output.append(f"cat: {arg}: No such file or directory")

    return "\r\n".join(output)
