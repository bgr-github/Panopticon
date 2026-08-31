from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import is_dir, is_file, list_dir, resolve_path
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "ls"
MAN = "ls - list directory contents"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    paths = [arg for arg in args if not arg.startswith("-")]
    target = resolve_path(session, paths[0] if paths else ".")

    if is_file(target):
        return target.rsplit("/", 1)[-1]

    if not is_dir(target):
        return f"ls: cannot access '{paths[0] if paths else target}': No such file or directory"

    entries = list_dir(target)
    if "-la" in args or "-al" in args or "-l" in args:
        lines = ["total 24"]
        lines.extend(f"drwxr-xr-x  2 root root 4096 Aug 31 09:00 {entry}" for entry in entries)
        return "\r\n".join(lines)

    return "  ".join(entries)
