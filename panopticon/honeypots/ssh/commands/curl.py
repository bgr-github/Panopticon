import posixpath
from typing import Literal
from urllib.parse import unquote

from panopticon.honeypots.ssh.context import SSHCommandContext
from panopticon.honeypots.ssh.transfers import parse_url, record_transfer

NAME: str = "curl"
MAN: str = "curl - transfer a URL"


def run(ctx: SSHCommandContext) -> list[str]:
    """Records a simulated curl download or file upload

    Args:
        ctx (SSHCommandContext): Command arguments, session and event publisher

    Returns:
        list[str]: Transfer-attempt message or an argument error
    """

    url: str | None = None
    output: str | None = None
    source: str | None = None
    remote_name: bool = False
    method: Literal["GET", "PUT", "POST"] = "GET"
    index: int = 0
    positional: bool = False
    argument: str
    option: str
    value: str

    try:
        while index < len(ctx.args):
            argument = ctx.args[index]
            index += 1

            if argument == "--" and not positional:
                positional = True
                continue

            if not positional and argument.startswith("--") and "=" in argument:
                option, value = argument.split("=", 1)

            elif not positional and argument in ("-o", "--output", "-T", "--upload-file", "-d", "--data", "--data-binary", "-F", "--form", "--url"):
                if index >= len(ctx.args):
                    raise ValueError(f"option {argument} requires an argument")

                option, value = argument, ctx.args[index]
                index += 1

            elif not positional and argument.startswith(("-o", "-T", "-d", "-F")):
                option, value = argument[:2], argument[2:]

            elif not positional and argument in ("--silent", "--show-error", "--fail", "--location", "--insecure"):
                continue

            elif not positional and argument == "--remote-name":
                remote_name = True
                continue

            elif not positional and argument.startswith("-") and set(argument[1:]) <= set("fsSLkO"):
                remote_name = remote_name or "O" in argument
                continue

            elif not positional and argument.startswith("-"):
                raise ValueError(f"unsupported option {argument}")

            else:
                option, value = "--url", argument

            if option in ("-o", "--output"):
                output = value

            elif option in ("-T", "--upload-file"):
                if source is not None:
                    raise ValueError("only one upload file per invocation is supported")

                source, method = value, "PUT"

            elif option in ("-d", "--data", "--data-binary", "-F", "--form"):
                if source is not None:
                    raise ValueError("only one upload file per invocation is supported")

                if option in ("-F", "--form"):
                    value = value.partition("=")[2].split(";", 1)[0]

                if not value.startswith("@"):
                    raise ValueError("only file-backed upload data is supported")

                source, method = value[1:], "POST"

            elif option == "--url":
                if url is not None:
                    raise ValueError("only one URL per invocation is supported")

                parse_url(value)
                url = value

            else:
                raise ValueError(f"unsupported option {option}")

        if url is None:
            raise ValueError("missing URL")

        if source in ("", "-") or output == "":
            raise ValueError("expected a non-empty virtual filename")

    except ValueError as exc:
        return [f"curl: {exc}"]

    if source is not None:
        return record_transfer(ctx, url, source, upload=True, method=method)

    if remote_name and output is None:
        output = posixpath.basename(unquote(parse_url(url).path))

        if not output:
            return ["curl: remote filename has no length"]

    return record_transfer(ctx, url, None if output == "-" else output)
