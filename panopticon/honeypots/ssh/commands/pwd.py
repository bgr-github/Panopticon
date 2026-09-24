from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "pwd"
MAN = "pwd - print working directory"


def run(ctx: SSHCommandContext) -> list[str]:
    return [ctx.session.cwd]
