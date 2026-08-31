from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "ps"
MAN = "ps - report a snapshot of current processes"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return "\r\n".join(
        [
            "  PID TTY          TIME CMD",
            "    1 ?        00:00:03 systemd",
            "  642 ?        00:00:00 sshd",
            " 1048 pts/0    00:00:00 bash",
            " 1071 pts/0    00:00:00 ps",
        ]
    )
