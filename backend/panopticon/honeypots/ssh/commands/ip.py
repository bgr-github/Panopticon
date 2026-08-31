from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "ip"
MAN = "ip - show/manipulate routing, network devices, interfaces and tunnels"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    if args[:1] in (["addr"], ["a"]):
        return "\r\n".join(
            [
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 state UNKNOWN",
                "    inet 127.0.0.1/8 scope host lo",
                "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP",
                "    inet 10.0.2.15/24 brd 10.0.2.255 scope global eth0",
            ]
        )

    return "Usage: ip [ addr | route | link ]"
