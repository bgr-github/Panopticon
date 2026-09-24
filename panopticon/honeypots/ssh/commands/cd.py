from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "cd"


def run(ctx: SSHCommandContext) -> list[str]:
    if len(ctx.args) > 1:
        return ["bash: cd: too many arguments"]

    target = ctx.args[0] if ctx.args else ctx.session.home

    try:
        directory = ctx.session.fs.require_directory(
            target,
            cwd=ctx.session.cwd,
        )
    except FileNotFoundError:
        return [f"bash: cd: {target}: No such file or directory"]
    except NotADirectoryError:
        return [f"bash: cd: {target}: Not a directory"]

    ctx.session.cwd = directory
    return []
