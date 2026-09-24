from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "echo"
MAN = "echo - display a line of text"


def run(ctx: SSHCommandContext) -> list[str]:
    return ctx.args
