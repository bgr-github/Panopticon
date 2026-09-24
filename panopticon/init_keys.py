import os
from pathlib import Path

import asyncssh

from panopticon.config.settings import settings


def ensure_host_key(path: Path) -> bool:
    """Creates a missing host key, validates and preserves existing one

    Args:
        path (Path): Path of key

    Returns:
        bool: True if one is created
    """

    if path.exists():
        asyncssh.read_private_key(path)
        return False

    path.parent.mkdir(parents=True, exist_ok=True)

    key: asyncssh.SSHKey = asyncssh.generate_private_key("ssh-ed25519")
    key_data: bytes = key.export_private_key("openssh")

    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        asyncssh.read_private_key(path)
        return False

    with os.fdopen(descriptor, "wb") as file:
        file.write(key_data)

    return True


def main() -> None:
    for path in settings.ssh.host_key_path:
        created = ensure_host_key(path)
        action = "Created" if created else "Kept existing"
        print(f"{action} SSH host key: {path.resolve()}")


if __name__ == "__main__":
    main()
