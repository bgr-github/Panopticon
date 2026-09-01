from panopticon.honeypots.ssh.context import SSHCommandContext
from panopticon.events.models import FileDownload

NAME = "wget"
MAN = "wget - non-interactive network downloader"


def run(ctx: SSHCommandContext) -> str:
    ctx.emit(
        event_type=FileDownload,
        tool="wget",
        url=ctx.args[0] if ctx.args else None,
        destination=None,
        input=ctx.input,
    )
    return ""
