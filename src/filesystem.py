"""Load a fake filesystem tree from a directory into memory.

Walks the real folder once at startup and builds a nested dictionary. This is load time only.
The honeypot never reads real disk in response to an attacker's input.
"""

from pathlib import Path


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
