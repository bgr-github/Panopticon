NAME = "cat"
MAN = "cat - concatenate files and print on the standard output"


def run(args, session):
    if not args:
        return ""  # real cat reads stdin; nothing to model here

    fs = session["fs"]
    cwd = session["cwd"]

    out = []
    for path_input in args:
        if path_input.startswith("-"):
            continue  # ignore flags like -n for now
        target = fs.resolve(cwd, path_input)
        if not fs.exists(target):
            out.append(f"cat: {path_input}: No such file or directory")
        elif fs.is_dir(target):
            out.append(f"cat: {path_input}: Is a directory")
        else:
            out.append(fs.read_file(target).rstrip("\n"))
    return "\n".join(out)
