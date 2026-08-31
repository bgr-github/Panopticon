from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.commands._common import current_user
from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "id"
MAN = "id - print user and group information"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    user = current_user(session)
    if user == "root":
        return "uid=0(root) gid=0(root) groups=0(root)"

    return f"uid=1000({user}) gid=1000({user}) groups=1000({user}),27(sudo),33(www-data)"
