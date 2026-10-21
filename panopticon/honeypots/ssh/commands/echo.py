from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "echo"
MAN = "echo - display a line of text"


def run(ctx: SSHCommandContext) -> list[str]:
    """Returns the supplied arguments on one line

    Args:
        ctx (SSHCommandContext): Context containing command arguments and session state

    Returns:
        list[str]: Lines of command output
    """

    return [" ".join(ctx.args)]
