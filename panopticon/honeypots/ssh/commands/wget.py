import posixpath
from urllib.parse import unquote

from panopticon.honeypots.ssh.context import SSHCommandContext
from panopticon.honeypots.ssh.transfers import parse_url, record_transfer

NAME: str = "wget"
MAN: str = "wget - The non-interactive network downloader."


def run(ctx: SSHCommandContext) -> list[str]:
    """Records a simulated wget download and its requested destination

    Args:
        ctx (SSHCommandContext): Command arguments, session and event publisher

    Returns:
        list[str]: Transfer-attempt message or an argument error
    """

    urls: list[str] = []
    output: str | None = None
    directory: str = "."
    index: int = 0
    positional: bool = False
    argument: str

    try:
        while index < len(ctx.args):
            argument = ctx.args[index]
            index += 1

            if argument == "--" and not positional:
                positional = True

            elif not positional and argument in ("-O", "--output-document", "-P", "--directory-prefix"):
                if index >= len(ctx.args):
                    raise ValueError(f"option {argument} requires an argument")

                if argument in ("-O", "--output-document"):
                    output = ctx.args[index]

                else:
                    directory = ctx.args[index]

                index += 1

            elif not positional and argument.startswith(("--output-document=", "--directory-prefix=")):
                if argument.startswith("--output-document="):
                    output = argument.split("=", 1)[1]

                else:
                    directory = argument.split("=", 1)[1]

            elif not positional and argument.startswith("-") and not argument.startswith("--") and "O" in argument[1:]:
                prefix: str = argument[1:argument.index("O")]

                if not set(prefix) <= set("qcNv"):
                    raise ValueError(f"unsupported option {argument}")

                output = argument[argument.index("O") + 1:]

                if not output:
                    if index >= len(ctx.args):
                        raise ValueError(f"option {argument} requires an argument")

                    output = ctx.args[index]
                    index += 1

            elif not positional and argument.startswith("-P"):
                directory = argument[2:]

            elif not positional and argument in ("--quiet", "--continue", "--no-verbose", "--no-check-certificate"):
                continue

            elif not positional and argument.startswith("-") and set(argument[1:]) <= set("qcNv"):
                continue

            elif not positional and argument.startswith("-"):
                raise ValueError(f"unsupported option {argument}")

            else:
                parse_url(argument)
                urls.append(argument)

        if not urls:
            raise ValueError("missing URL")

        if output == "":
            raise ValueError("empty output filename")

    except ValueError as exc:
        return [f"wget: {exc}"]

    responses: list[str] = []

    for url in urls:
        filename: str = posixpath.basename(unquote(parse_url(url).path)) or "index.html"
        destination: str | None = None if output == "-" else (
            output if output is not None else posixpath.join(directory, filename)
        )
        responses.extend(record_transfer(ctx, url, destination))

    return responses
