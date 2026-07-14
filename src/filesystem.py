"""Load a fake filesystem tree from a directory into memory.

Walks the real folder once at startup and builds a nested dictionary. This is load time only.
The honeypot never reads real disk in response to an attacker's input.
"""

from pathlib import Path


class FakeFS:
    def __init__(self, tree):
        self._tree = tree

    def resolve(self, cwd, path):
        """Transforms path file and turns it into a abspath"""

        raw = path if path.startswith("/") else f"{cwd}/{path}"
        stack = []

        for part in raw.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if stack:
                    stack.pop()
            else:
                stack.append(part)
        return "/" + "/".join(stack)

    def exists(self, abspath):
        """Returns True if something exists"""
        return self._node(abspath) is not None

    def is_dir(self, abspath):
        """Checks if node is a dictionary (directory)"""
        return isinstance(self._node(abspath), dict)

    def list_dir(self, abspath):
        """Returns child names if its a directory else None"""
        node = self._node(abspath)
        return sorted(node.keys()) if isinstance(node, dict) else None

    def read_file(self, abspath):
        """Returns file contents if it's a file, else None"""
        node = self._node(abspath)
        return node if isinstance(node, str) else None

    def _node(self, abspath):
        """Walks down the tree when given an abspath and returns whats at the end of None"""
        node = self._tree

        for part in abspath.split("/"):
            if part == "":
                continue
            if not isinstance(node, dict) or part not in node:
                return None

            node = node[part]

        return node


def load_filesystem(root):
    """Builds the in-memory structure from the directory at root."""

    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Filesystem root not found: {root}")
    return _walk(root)


def _walk(dir):
    """Recursively walks the file structure, adding it to a dict."""
    node = {}
    for child in sorted(dir.iterdir()):
        if child.is_dir():
            node[child.name] = _walk(child)
        else:
            try:
                node[child.name] = child.read_text()
            except UnicodeDecodeError:
                # Binary file keep placeholder so files dont break
                node[child.name] = "[binary content]"
    return node
