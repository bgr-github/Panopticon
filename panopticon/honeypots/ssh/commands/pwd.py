from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "pwd"
MAN = "pwd - print working directory"


def run(ctx: SSHCommandContext) -> list[str]:
    """Returns the session working directory

    Args:
        ctx (SSHCommandContext): Context containing command arguments and session state

    Returns:
        list[str]: Lines of command output
    """

    return [ctx.session.cwd]
