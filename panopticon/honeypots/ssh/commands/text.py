"""Bounded text filters; input and output remain virtual."""
from panopticon.honeypots.ssh.context import SSHCommandContext

NAMES = ("head", "tail", "wc", "grep")


def run(ctx: SSHCommandContext) -> list[str]:
    """Filters or counts virtual file contents and piped input

    Args:
        ctx (SSHCommandContext): Context containing command arguments and session state

    Returns:
        list[str]: Lines of command output
    """

    args: list[str] = list(ctx.args)
    count: int = 10

    if ctx.name in ("head", "tail") and args[:1] == ["-n"]:
        try:
            count = max(0, min(int(args[1]), 65536))
        except (ValueError, IndexError):
            ctx.status = 1
            return [f"{ctx.name}: invalid number of lines"]

        args = args[2:]

    flags: set[str] = set()

    while args and args[0].startswith("-"):
        flags.update(args.pop(0)[1:])

    pattern: str = args.pop(0) if ctx.name == "grep" and args else ""
    data: str = ctx.stdin

    if args:
        try:
            data = "".join(ctx.session.fs.read_file(path, ctx.session.cwd) for path in args)
        except OSError:
            ctx.status = 1
            return [f"{ctx.name}: {args[0]}: No such file or directory"]

    lines: list[str] = data.splitlines()

    if ctx.name == "head":
        return lines[:count]

    if ctx.name == "tail":
        return lines[-count:] if count else []

    if ctx.name == "wc":
        return [str(data.count("\n"))] if "l" in flags else [
            f"{data.count(chr(10))} {len(data.split())} {len(data.encode())}",
        ]
    # Literal matching avoids attacker-controlled regular expression execution.
    matches: list[str] = [line for line in lines if
               ((pattern.lower() in line.lower()) if "i" in flags else (pattern in line)) != ("v" in flags)]
    ctx.status = int(not matches)
    return [] if "q" in flags else matches
