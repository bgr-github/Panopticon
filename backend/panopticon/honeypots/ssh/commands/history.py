from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "history"
MAN = "history - display command history"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return "\r\n".join(
        [
            "    1  ls -la",
            "    2  cat /etc/passwd",
            "    3  cd /tmp",
            "    4  wget http://example.com/update.sh",
        ]
    )
