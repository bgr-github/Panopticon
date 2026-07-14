NAME = "pwd"
MAN = "pwd - print name of current/working directory"


def run(args, session):
    return session["cwd"]
