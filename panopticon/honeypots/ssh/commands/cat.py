from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "cat"


def run(ctx: SSHCommandContext) -> list[str]:
    """Reads virtual files or piped input

    Args:
        ctx (SSHCommandContext): Context containing command arguments and session state

    Returns:
        list[str]: Lines of command output
    """

    if not ctx.args:
        return ctx.stdin.splitlines()

    output: list[str] = []

    for target in ctx.args:
        try:
            output.extend(ctx.session.fs.read_file(target, ctx.session.cwd).splitlines())
        except OSError as exc:
            ctx.status = 1
            reason: str = (
                "Is a directory"
                if isinstance(exc, IsADirectoryError)
                else ("Not a directory" if isinstance(exc, NotADirectoryError) else "No such file or directory")
            )
            output.append(f"cat: {target}: {reason}")

    return output
