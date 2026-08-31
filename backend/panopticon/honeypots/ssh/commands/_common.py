from pathlib import PurePosixPath

from panopticon.honeypots.ssh.context import SSHSessionContext


HOSTNAME = "web-prod-01"
KERNEL = "Linux web-prod-01 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux"
DEFAULT_CWD = "/root"

DIRECTORIES: dict[str, list[str]] = {
    "/": ["bin", "boot", "dev", "etc", "home", "lib", "opt", "proc", "root", "tmp", "usr", "var"],
    "/bin": ["bash", "cat", "chmod", "echo", "ls", "sh"],
    "/etc": ["crontab", "group", "hostname", "hosts", "issue", "passwd", "profile", "shadow", "ssh"],
    "/home": ["ubuntu"],
    "/home/ubuntu": ["notes.txt"],
    "/root": ["backup.sh", "deploy.log", "snap"],
    "/tmp": [],
    "/usr": ["bin", "lib", "local", "sbin", "share"],
    "/var": ["log", "tmp", "www"],
    "/var/log": ["auth.log", "syslog"],
    "/var/www": ["html"],
    "/var/www/html": ["index.html"],
}

FILES: dict[str, str] = {
    "/etc/hostname": f"{HOSTNAME}\n",
    "/etc/hosts": "127.0.0.1 localhost\n127.0.1.1 web-prod-01\n",
    "/etc/issue": "Ubuntu 22.04.3 LTS \\n \\l\n",
    "/etc/passwd": (
        "root:x:0:0:root:/root:/bin/bash\n"
        "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n"
        "www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\n"
        "ubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash\n"
    ),
    "/etc/shadow": "cat: /etc/shadow: Permission denied\n",
    "/root/backup.sh": "#!/bin/bash\ntar -czf /tmp/site-backup.tgz /var/www/html\n",
    "/root/deploy.log": "deploy completed successfully\n",
    "/home/ubuntu/notes.txt": "TODO: rotate staging credentials\n",
    "/var/www/html/index.html": "<html><body>OK</body></html>\n",
}


def current_user(session: SSHSessionContext) -> str:
    return session.username or "root"


def get_cwd(session: SSHSessionContext) -> str:
    cwd = getattr(session, "cwd", None)

    if cwd is None:
        cwd = DEFAULT_CWD
        setattr(session, "cwd", cwd)

    return cwd


def set_cwd(session: SSHSessionContext, path: str) -> None:
    setattr(session, "cwd", path)


def resolve_path(session: SSHSessionContext, path: str | None) -> str:
    if not path or path == "~":
        return DEFAULT_CWD

    if path.startswith("~/"):
        path = f"{DEFAULT_CWD}/{path[2:]}"

    if path.startswith("/"):
        candidate = PurePosixPath(path)
    else:
        candidate = PurePosixPath(get_cwd(session)) / path

    parts: list[str] = []
    for part in candidate.parts:
        if part in {"", "/"}:
            continue
        if part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)

    return "/" + "/".join(parts) if parts else "/"


def is_dir(path: str) -> bool:
    return path in DIRECTORIES


def is_file(path: str) -> bool:
    return path in FILES


def list_dir(path: str) -> list[str]:
    return DIRECTORIES.get(path, [])
