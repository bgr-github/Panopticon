from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "netstat"
MAN = "netstat - print network connections"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return "\r\n".join(
        [
            "Active Internet connections (servers and established)",
            "Proto Recv-Q Send-Q Local Address           Foreign Address         State",
            "tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN",
            "tcp        0      0 127.0.0.1:5432          0.0.0.0:*               LISTEN",
            "tcp        0      0 127.0.0.1:6379          0.0.0.0:*               LISTEN",
        ]
    )
