from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "ifconfig"
MAN = "ifconfig - configure a network interface"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    return "\r\n".join(
        [
            "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500",
            "        inet 10.0.2.15  netmask 255.255.255.0  broadcast 10.0.2.255",
            "lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536",
            "        inet 127.0.0.1  netmask 255.0.0.0",
        ]
    )
