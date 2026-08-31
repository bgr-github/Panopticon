from asyncssh import SSHServerChannel, SSHServerConnection

from panopticon.honeypots.ssh.context import SSHSessionContext

NAME = "wget"
MAN = "wget - non-interactive network downloader"


def run(args, session: SSHSessionContext, chan: SSHServerChannel, conn: SSHServerConnection) -> str:
    url = next((arg for arg in args if not arg.startswith("-")), None)
    if not url:
        return "wget: missing URL"

    filename = url.rstrip("/").rsplit("/", 1)[-1] or "index.html"
    return "\r\n".join(
        [
            f"--2026-08-31 09:00:00--  {url}",
            "Resolving host... connected.",
            "HTTP request sent, awaiting response... 200 OK",
            f"Saving to: '{filename}'",
            "",
            f"'{filename}' saved [4096/4096]",
        ]
    )
