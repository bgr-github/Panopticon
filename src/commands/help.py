NAME = "help"
MAN = "Shows help command"


def run(args, session):
    commands = session.get("commands", [])
    if not commands:
        return "No commands available."

    lines = ["Available Commands: "]
    lines.extend(f" {name}" for name in commands)
    return "\n".join(lines)
