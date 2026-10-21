import mimetypes
import posixpath
from typing import Literal
from urllib.parse import SplitResult, unquote, urlsplit

from panopticon.events.models import FileDownloaded, FileUploaded
from panopticon.honeypots.ssh.context import SSHCommandContext


def parse_url(url: str) -> SplitResult:
    """Validates a remote transfer URL without opening a network connection

    Args:
        url (str): Remote URL supplied by the client

    Returns:
        SplitResult: Parsed HTTP, HTTPS or FTP URL
    """

    parsed: SplitResult = urlsplit(url)

    if parsed.scheme.lower() not in ("http", "https", "ftp") or not parsed.hostname:
        raise ValueError("expected an HTTP, HTTPS or FTP URL")

    # Accessing port also validates malformed or out-of-range port values.
    parsed.port

    return parsed


def record_transfer(
    ctx: SSHCommandContext,
    url: str,
    local_path: str | None,
    upload: bool = False,
    method: Literal["GET", "PUT", "POST"] = "GET",
) -> list[str]:
    """Publishes metadata for a simulated transfer without moving file contents

    Args:
        ctx (SSHCommandContext): Command arguments, session and event publisher
        url (str): Remote source or destination URL
        local_path (str | None): Virtual source or destination path, or None for stdout
        upload (bool): Whether the command sends a virtual file to the remote URL
        method (Literal["GET", "PUT", "POST"]): Method used by the requested transfer

    Returns:
        list[str]: Message explaining that the attempt was recorded without network access
    """

    parsed: SplitResult = parse_url(url)
    remote_filename: str = posixpath.basename(unquote(parsed.path)) or "index.html"
    resolved_path: str | None = None
    filename: str = remote_filename
    size_bytes: int | None = None

    if local_path is not None:
        resolved_path = posixpath.normpath(posixpath.join(ctx.session.cwd, local_path))
        filename = posixpath.basename(resolved_path)

    if upload and resolved_path is not None:
        try:
            content: str = ctx.session.fs.read_file(resolved_path)
            size_bytes = len(content.encode("utf-8"))

        except OSError:
            # Failed source-file lookups are still useful transfer-attempt telemetry.
            pass

    filetype: str = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    event: FileUploaded | FileDownloaded

    if upload:
        event = FileUploaded(
            session_id=ctx.session.id,
            src_ip=ctx.session.src_ip,
            src_port=ctx.session.src_port,
            url=url,
            filename=filename,
            filetype=filetype,
            command=ctx.input,
            method=method,
            local_path=resolved_path,
            size_bytes=size_bytes,
        )

    else:
        event = FileDownloaded(
            session_id=ctx.session.id,
            src_ip=ctx.session.src_ip,
            src_port=ctx.session.src_port,
            url=url,
            filename=filename,
            filetype=filetype,
            command=ctx.input,
            method=method,
            local_path=resolved_path,
        )

    ctx.event_handler.publish(event)

    direction: str = "upload" if upload else "download"

    return [f"{ctx.name}: network access disabled ({direction} attempt recorded)"]
