from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "curl"
MAN = "curl - transfer a URL"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    url = next((arg for arg in args if not arg.startswith("-")), None)
    if not url:
        return "curl: try 'curl --help' for more information"

    if "-I" in args or "--head" in args:
        return "HTTP/1.1 200 OK\r\nServer: nginx/1.18.0\r\nContent-Length: 4096"

    return "#!/bin/sh\r\necho starting update\r\n"
