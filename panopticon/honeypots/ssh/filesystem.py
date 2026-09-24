from dataclasses import dataclass


@dataclass(frozen=True)
class FakeDirectory:
    pass


@dataclass(frozen=True)
class FakeFile:
    content: str


class FakeFileSystem:
    def __init__(self):
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

    def resolve(self, path: str, cwd: str = "/") -> str:
        """Resolve a virtual Linux path and check it exists."""

        if not path:
            raise FileNotFoundError(path)

        # Absolute paths start at root; relative paths start at cwd.
        parts = [] if path.startswith("/") else [part for part in cwd.split("/") if part]

        for component in path.split("/"):
            current = "/" + "/".join(parts)

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
        resolved = self.resolve(path, cwd)

        if not isinstance(self.entries[resolved], FakeDirectory):
            raise NotADirectoryError(resolved)

        return resolved

    def list_directory(self, path: str = ".", cwd: str = "/") -> list[str]:
        resolved = self.require_directory(path, cwd)
        prefix = resolved.rstrip("/") + "/"

        children = []

        for entry_path in self.entries:
            if entry_path.startswith(prefix):
                name = entry_path[len(prefix) :]

                # Only immediate children, not their descendants.
                if name and "/" not in name:
                    children.append(name)

        return sorted(children)

    def read_file(self, path: str, cwd: str = "/") -> str:
        resolved = self.resolve(path, cwd)
        entry = self.entries[resolved]

        if isinstance(entry, FakeDirectory):
            raise IsADirectoryError(resolved)

        return entry.content
