"""Read-only reconnaissance commands for the fixed Ubuntu persona."""
from datetime import datetime, timezone

from panopticon.honeypots.ssh.context import SSHCommandContext, SSHSessionContext
from panopticon.honeypots.ssh.persona import KERNEL, KERNEL_BUILD

NAMES = (
    "whoami",
    "id",
    "uname",
    "hostname",
    "lsb_release",
    "env",
    "printenv",
    "date",
    "uptime",
    "who",
    "ps",
    "free",
    "arch",
    "true",
    "false",
)


def run(ctx: SSHCommandContext) -> list[str]:
    """Returns simulated Ubuntu system information for the requested command

    Args:
        ctx (SSHCommandContext): Context containing command arguments and session state

    Returns:
        list[str]: Lines of command output
    """

    name: str = ctx.name
    args: list[str] = ctx.args
    session: SSHSessionContext = ctx.session
    user: str = session.username or "admin"
    uid: int = 0 if user == "root" else 1000

    if name == "whoami":
        return [user]

    if name == "id":
        if args in (["-u"], ["-g"]):
            return [str(uid)]

        if args == ["-un"]:
            return [user]

        return [f"uid={uid}({user}) gid={uid}({user}) groups={uid}({user})"]

    if name == "arch":
        return ["x86_64"]

    if name == "uname":
        values: dict[str, str] = {
            "s": "Linux",
            "n": session.hostname,
            "r": KERNEL,
            "v": KERNEL_BUILD,
            "m": "x86_64",
            "p": "x86_64",
            "i": "x86_64",
            "o": "GNU/Linux",
        }
        flags: str = "".join(arg[1:] for arg in args if arg.startswith("-")) or "s"

        if "a" in flags:
            flags = "snrvmpio"

        return [" ".join(value for flag, value in values.items() if flag in flags)]

    if name == "hostname":
        return [session.hostname]

    if name == "lsb_release":
        if "-ds" in args or "-sd" in args:
            return ["Ubuntu 24.04 LTS"]

        if "-rs" in args or "-sr" in args:
            return ["24.04"]

        return [
            "Distributor ID:\tUbuntu",
            "Description:\tUbuntu 24.04 LTS",
            "Release:\t24.04",
            "Codename:\tnoble",
        ]

    if name in ("env", "printenv"):
        env: dict[str, str] = {**session.environment, "PWD": session.cwd}

        if name == "printenv" and args:
            ctx.status = int(any(key not in env for key in args))
            return [env[key] for key in args if key in env]

        return [f"{key}={value}" for key, value in env.items()]

    if name == "date":
        now: datetime = datetime.now(timezone.utc)
        return [str(int(now.timestamp())) if args == ["+%s"] else now.strftime("%a %b %d %H:%M:%S UTC %Y")]

    if name == "uptime":
        return [f" {datetime.now(timezone.utc):%H:%M:%S} up 3 days,  4:12,  1 user,  load average: 0.00, 0.01, 0.00"]

    if name == "who":
        return [f"{user:<8} pts/0        {datetime.now(timezone.utc):%Y-%m-%d %H:%M} ({session.src_ip})"]

    if name == "ps":
        if not args:
            return ["    PID TTY          TIME CMD", "   1241 pts/0    00:00:00 bash", "   1250 pts/0    00:00:00 ps"]

        return [
            "USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND",
            "root           1  0.0  0.5  22544 11264 ?        Ss   Apr25   0:02 /sbin/init",
            "root         812  0.0  0.3  12020  7168 ?        Ss   Apr25   0:00 /usr/sbin/sshd -D",
            f"{user:<12}1241  0.0  0.2   9144  5120 pts/0    Ss   10:00   0:00 -bash",
        ]

    if name == "free":
        return [
            "               total        used        free      shared  buff/cache   available",
            "Mem:           1.9Gi       603Mi       782Mi       1.0Mi       601Mi       1.4Gi",
            "Swap:             0B          0B          0B",
        ] if "-h" in args else [
                    "               total        used        free      shared  buff/cache   available",
                    "Mem:         2034688      617472      801280        1024      615936     1417216",
                    "Swap:              0           0           0",
                ]

    ctx.status = int(name == "false")
    return []
