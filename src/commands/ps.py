NAME = "ps"
MAN = "ps - report a snapshot of the current processes"

# A fixed fake process table for the persona. Every row must be plausible for
# an Ubuntu web server: the columns are
# (user, pid, cpu, mem, vsz, rss, tty, stat, start, time, command).
# Keep this consistent with the persona — an Ubuntu box should show systemd,
# sshd, and a web server, not services that wouldn't be here.
_PROCESSES = [
    ("root", "1", "0.0", "0.1", "168140", "11968", "?", "Ss", "Nov14", "0:02", "/sbin/init"),
    ("root", "2", "0.0", "0.0", "0", "0", "?", "S", "Nov14", "0:00", "[kthreadd]"),
    ("root", "415", "0.0", "0.2", "104852", "17280", "?", "Ss", "Nov14", "0:01", "/lib/systemd/systemd-journald"),
    ("root", "612", "0.0", "0.1", "15852", "6144", "?", "Ss", "Nov14", "0:00", "/usr/sbin/sshd -D"),
    ("www-data", "894", "0.0", "0.3", "215432", "24960", "?", "S", "Nov14", "0:03", "nginx: worker process"),
    (
        "root",
        "893",
        "0.0",
        "0.1",
        "215012",
        "12800",
        "?",
        "Ss",
        "Nov14",
        "0:00",
        "nginx: master process /usr/sbin/nginx",
    ),
    ("mysql", "1021", "0.0", "4.8", "1792544", "392192", "?", "Ssl", "Nov14", "1:24", "/usr/sbin/mysqld"),
    ("systemd+", "701", "0.0", "0.1", "16256", "7168", "?", "Ss", "Nov14", "0:00", "/lib/systemd/systemd-resolved"),
]


def run(args, session):
    username = session.get("username", "guest")
    joined = "".join(a for a in args if a.startswith("-") or a.isalpha())
    full = any(c in joined for c in ("a", "e")) or "aux" in "".join(args)

    if full:
        return _full_listing(username)
    return _short_listing(username)


def _short_listing(username):
    # Bare `ps`: only the user's own shell-associated processes.
    header = "    PID TTY          TIME CMD"
    rows = [
        "   2451 pts/0    00:00:00 bash",
        "   2467 pts/0    00:00:00 ps",
    ]
    return "\n".join([header] + rows)


def _full_listing(username):
    header = "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND"
    lines = [header]
    for user, pid, cpu, mem, vsz, rss, tty, stat, start, time, cmd in _PROCESSES:
        lines.append(
            f"{user:<8} {pid:>5} {cpu:>4} {mem:>4} {vsz:>6} {rss:>5} " f"{tty:<8} {stat:<4} {start:<5} {time:>4} {cmd}"
        )
    # The attacker's own session, so the snapshot includes "them".
    lines.append(
        f"{username:<8} {'2451':>5} {'0.0':>4} {'0.0':>4} {'8912':>6} {'5376':>5} "
        f"{'pts/0':<8} {'Ss':<4} {'12:19':<5} {'0:00':>4} -bash"
    )
    lines.append(
        f"{username:<8} {'2467':>5} {'0.0':>4} {'0.0':>4} {'10096':>6} {'3200':>5} "
        f"{'pts/0':<8} {'R+':<4} {'12:19':<5} {'0:00':>4} ps aux"
    )
    return "\n".join(lines)
