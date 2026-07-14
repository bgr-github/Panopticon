"""cd - change the current working directory."""

NAME = "cd"
MAN = "cd - change the shell working directory"


def run(args, session):
    fs = session["fs"]
    cwd = session["cwd"]

    # Bare `cd` goes to the user's home directory.
    if not args:
        target_input = f"/home/{session.get('username', 'guest')}"
    else:
        target_input = args[0]

    target = fs.resolve(cwd, target_input)

    if not fs.exists(target):
        return f"bash: cd: {target_input}: No such file or directory"
    if not fs.is_dir(target):
        return f"bash: cd: {target_input}: Not a directory"

    session["cwd"] = target
    return ""
