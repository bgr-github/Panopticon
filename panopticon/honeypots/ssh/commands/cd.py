from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "cd"


def run(ctx: SSHCommandContext) -> list[str]:
    if len(ctx.args) > 1:
        ctx.status = 1
        return ["bash: cd: too many arguments"]

    target = ctx.args[0] if ctx.args else ctx.session.home
    if target == "-":
        if ctx.session.previous_cwd is None:
            ctx.status = 1
            return ["bash: cd: OLDPWD not set"]

        target = ctx.session.previous_cwd

    try:
        directory = ctx.session.fs.require_directory(
            target,
            cwd=ctx.session.cwd,
        )

    except FileNotFoundError:
        ctx.status = 1
        return [f"bash: cd: {target}: No such file or directory"]

    except NotADirectoryError:
        ctx.status = 1
        return [f"bash: cd: {target}: Not a directory"]

    ctx.session.previous_cwd, ctx.session.cwd = ctx.session.cwd, directory

    return [directory] if ctx.args == ["-"] else []
