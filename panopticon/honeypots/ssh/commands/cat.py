from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "cat"


def run(ctx: SSHCommandContext) -> list[str]:
    if len(ctx.args) != 1:
        return ["cat: exactly one file argument is required"]

    target = ctx.args[0]

    try:
        content = ctx.session.fs.read_file(
            target,
            cwd=ctx.session.cwd,
        )
    except FileNotFoundError:
        return [f"cat: {target}: No such file or directory"]
    except NotADirectoryError:
        return [f"cat: {target}: Not a directory"]
    except IsADirectoryError:
        return [f"cat: {target}: Is a directory"]

    return content.splitlines()
