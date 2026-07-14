NAME = "clear"
MAN = "clear - clear the terminal screen"


def run(args, session):
    return "\033[H\033[2J\033[3J"
