from dataclasses import dataclass
import posixpath

from panopticon.honeypots.ssh.persona import HOSTNAME, KERNEL, KERNEL_BUILD, MOTD, OS_RELEASE


@dataclass(frozen=True)
class FakeDirectory:
    pass


@dataclass(frozen=True)
class FakeFile:
    content: str


class FakeFileSystem:
    def __init__(self) -> None:
        """Creates the virtual Ubuntu directory tree and initial file contents"""

        self.entries: dict[str, FakeDirectory | FakeFile] = {
            "/": FakeDirectory(),
            "/home": FakeDirectory(),
            "/home/admin": FakeDirectory(),
            "/home/admin/readme.txt": FakeFile("Welcome to the server.\n"),
            "/etc": FakeDirectory(),
            "/etc/hostname": FakeFile("web-01\n"),
            "/var": FakeDirectory(),
            "/var/log": FakeDirectory(),
        }

        for path in (
            "/root",
            "/tmp",
            "/var/tmp",
            "/usr",
            "/usr/bin",
            "/usr/sbin",
            "/usr/lib",
            "/usr/local",
            "/usr/local/bin",
            "/bin",
            "/sbin",
            "/dev",
            "/proc",
            "/sys",
            "/run",
            "/opt",
            "/srv",
            "/boot",
            "/etc/ssh",
            "/etc/apt",
            "/var/www",
            "/var/www/html",
        ):
            self.entries[path] = FakeDirectory()

        files: dict[str, str] = {
            "/etc/os-release": OS_RELEASE,
            "/etc/lsb-release": 'DISTRIB_ID=Ubuntu\nDISTRIB_RELEASE=24.04\nDISTRIB_CODENAME=noble\nDISTRIB_DESCRIPTION="Ubuntu 24.04 LTS"\n',
            "/etc/issue": "Ubuntu 24.04 LTS \\n \\l\n\n",
            "/etc/hostname": HOSTNAME + "\n",
            "/etc/hosts": f"127.0.0.1 localhost\n127.0.1.1 {HOSTNAME}\n\n::1 localhost ip6-localhost ip6-loopback\n",
            "/etc/motd": MOTD,
            "/etc/passwd": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\nwww-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\n",
            "/etc/group": "root:x:0:\nadm:x:4:\nsudo:x:27:\nwww-data:x:33:\n",
            "/etc/shells": "/bin/sh\n/usr/bin/sh\n/bin/bash\n/usr/bin/bash\n",
            "/etc/ssh/sshd_config": "Include /etc/ssh/sshd_config.d/*.conf\nPermitRootLogin prohibit-password\nPasswordAuthentication yes\nUsePAM yes\n",
            "/proc/version": f"Linux version {KERNEL} (buildd@lcy02-amd64-084) (x86_64-linux-gnu-gcc-13 (Ubuntu 13.2.0-23ubuntu4) 13.2.0) {KERNEL_BUILD}\n",
            "/proc/cpuinfo": "processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Xeon(R) CPU E5-2676 v3 @ 2.40GHz\ncpu cores\t: 1\n",
            "/proc/meminfo": "MemTotal:        2034688 kB\nMemFree:          801280 kB\nMemAvailable:    1417216 kB\n",
            "/var/www/html/index.html": "<html><body><h1>Welcome to nginx!</h1></body></html>\n",
        }
        self.entries.update({path: FakeFile(content) for path, content in files.items()})
        # An ordinary account's home doesn't contain a honeypot welcome file.
        del self.entries["/home/admin/readme.txt"]

    def add_user(self, username: str) -> str:
        """Creates the simulated account files and home directory

        Args:
            username (str): Sanitised username for the virtual account

        Returns:
            str: Absolute path of the account home directory
        """

        home: str = "/root" if username == "root" else f"/home/{username}"
        self.entries[home] = FakeDirectory()
        self.entries[home + "/.bashrc"] = FakeFile("# ~/.bashrc: executed by bash for non-login shells.\n")
        self.entries[home + "/.profile"] = FakeFile('# ~/.profile: executed by the command interpreter for login shells.\n')

        if username != "root":
            self.entries["/etc/passwd"] = FakeFile(
                self.read_file("/etc/passwd") + f"{username}:x:1000:1000:,,,:{home}:/bin/bash\n"
            )
            self.entries["/etc/group"] = FakeFile(
                self.read_file("/etc/group") + f"{username}:x:1000:\n"
            )

        return home

    def write_file(self, path: str, content: str, cwd: str, append: bool = False) -> None:
        """Write only to the bounded virtual filesystem, never the host."""
        parent: str
        name: str
        parent, name = posixpath.split(path)
        directory: str = self.require_directory(parent or ".", cwd)
        target: str = posixpath.join(directory, name)

        if not name or isinstance(self.entries.get(target), FakeDirectory):
            raise IsADirectoryError(target)

        previous: FakeDirectory | FakeFile | None = self.entries.get(target)
        value: str = (previous.content if append and isinstance(previous, FakeFile) else "") + content

        if len(value) > 65536 or (target not in self.entries and len(self.entries) >= 1024):
            raise OSError("No space left on device")

        self.entries[target] = FakeFile(value)

    def resolve(self, path: str, cwd: str = "/") -> str:
        """Resolve a virtual Linux path and check it exists."""

        if not path:
            raise FileNotFoundError(path)

        # Absolute paths start at root; relative paths start at cwd.
        parts: list[str] = [] if path.startswith("/") else [part for part in cwd.split("/") if part]

        for component in path.split("/"):
            current: str = "/" + "/".join(parts)

            # You cannot traverse through a file.
            if not isinstance(self.entries[current], FakeDirectory):
                raise NotADirectoryError(current)

            if component in ("", "."):
                continue

            if component == "..":
                if parts:
                    parts.pop()

                continue

            parts.append(component)
            current = "/" + "/".join(parts)

            if current not in self.entries:
                raise FileNotFoundError(current)

        return "/" + "/".join(parts)

    def require_directory(self, path: str, cwd: str = "/") -> str:
        """Resolves a virtual path and checks it is a directory

        Args:
            path (str): Virtual path to resolve
            cwd (str): Working directory used to resolve relative paths

        Returns:
            str: Absolute path of the directory
        """

        resolved: str = self.resolve(path, cwd)

        if not isinstance(self.entries[resolved], FakeDirectory):
            raise NotADirectoryError(resolved)

        return resolved

    def list_directory(self, path: str = ".", cwd: str = "/") -> list[str]:
        """Lists the immediate children of a virtual directory

        Args:
            path (str): Virtual path to resolve
            cwd (str): Working directory used to resolve relative paths

        Returns:
            list[str]: Sorted names of entries in the directory
        """

        resolved: str = self.require_directory(path, cwd)
        prefix: str = resolved.rstrip("/") + "/"

        children: list[str] = []

        for entry_path in self.entries:
            if entry_path.startswith(prefix):
                name: str = entry_path[len(prefix) :]

                # Only immediate children, not their descendants.
                if name and "/" not in name:
                    children.append(name)

        return sorted(children)

    def read_file(self, path: str, cwd: str = "/") -> str:
        """Reads the contents of a virtual file

        Args:
            path (str): Virtual path to resolve
            cwd (str): Working directory used to resolve relative paths

        Returns:
            str: Contents of the file
        """

        resolved: str = self.resolve(path, cwd)
        entry: FakeDirectory | FakeFile = self.entries[resolved]

        if isinstance(entry, FakeDirectory):
            raise IsADirectoryError(resolved)

        return entry.content
