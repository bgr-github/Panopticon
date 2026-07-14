NAME = "ls"
MAN = "ls - list directory contents"


def run(args, session):
    fs = session["fs"]
    cwd = session["cwd"]

    flags = [a for a in args if a.startswith("-")]
    operands = [a for a in args if not a.startswith("-")]
    show_hidden = any("a" in f for f in flags)

    path_input = operands[0] if operands else "."
    target = fs.resolve(cwd, path_input)

    names = fs.list_dir(target)
    if names is None:
        if fs.exists(target):
            return path_input
        return f"ls: cannot access '{path_input}': No such file or directory"

    if not show_hidden:
        names = [n for n in names if not n.startswith(".")]
    return "  ".join(names)
