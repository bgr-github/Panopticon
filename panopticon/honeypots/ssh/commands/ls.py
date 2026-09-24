from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "ls"


def run(ctx: SSHCommandContext) -> list[str]:
    if len(ctx.args) > 1:
        return ["ls: only one directory argument is supported"]

    target = ctx.args[0] if ctx.args else "."

    try:
        names = ctx.session.fs.list_directory(
            target,
            cwd=ctx.session.cwd,
        )
    except FileNotFoundError:
        return [f"ls: cannot access '{target}': No such file or directory"]
    except NotADirectoryError:
        return [f"ls: cannot access '{target}': Not a directory"]

    # Match basic ls behaviour by hiding dotfiles.
    return [name for name in names if not name.startswith(".")]
