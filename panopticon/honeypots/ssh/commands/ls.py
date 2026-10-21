from panopticon.honeypots.ssh.context import SSHCommandContext
from panopticon.honeypots.ssh.filesystem import FakeDirectory

NAME = "ls"


def run(ctx: SSHCommandContext) -> list[str]:
    flags, targets, output = set(), [], []

    for arg in ctx.args:
        if arg.startswith("--color"):
            continue
        if arg.startswith("-"):
            flags.update(arg[1:])
        else:
            targets.append(arg)

    for target in targets or ["."]:
        try:
            path = ctx.session.fs.resolve(target, ctx.session.cwd)
            directory = isinstance(ctx.session.fs.entries[path], FakeDirectory) and "d" not in flags
            names = ctx.session.fs.list_directory(path) if directory else [target]

            if directory and "a" in flags:
                names = [".", "..", *names]

            if directory and not flags.intersection("aA"):
                names = [name for name in names if not name.startswith(".")]

            if "l" in flags and directory:
                output.append(f"total {4 * len(names)}")

            for name in names:
                item_path = ctx.session.fs.resolve(name, path) if directory else path
                item = ctx.session.fs.entries[item_path]
                is_dir = isinstance(item, FakeDirectory)

                if "l" in flags:
                    permissions = "drwxr-xr-x" if is_dir else "-rw-r--r--"
                    size = 4096 if is_dir else len(item.content.encode())
                    in_home = item_path == ctx.session.home or item_path.startswith(ctx.session.home + "/")
                    owner = (ctx.session.username or "admin") if in_home else "root"
                    output.append(f"{permissions} {2 if is_dir else 1} {owner} {owner} {size:>5} Apr 25  2024 {name}")
                else:
                    output.append(name + ("/" if "F" in flags and is_dir else ""))

        except OSError as exc:
            ctx.status = 2
            reason = "Not a directory" if isinstance(exc, NotADirectoryError) else "No such file or directory"
            output.append(f"ls: cannot access '{target}': {reason}")

    return output
