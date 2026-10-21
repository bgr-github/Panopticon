from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "cat"


def run(ctx: SSHCommandContext) -> list[str]:
    if not ctx.args:
        return ctx.stdin.splitlines()

    output = []

    for target in ctx.args:
        try:
            output.extend(ctx.session.fs.read_file(target, ctx.session.cwd).splitlines())
        except OSError as exc:
            ctx.status = 1
            reason = (
                "Is a directory"
                if isinstance(exc, IsADirectoryError)
                else ("Not a directory" if isinstance(exc, NotADirectoryError) else "No such file or directory")
            )
            output.append(f"cat: {target}: {reason}")
    return output
