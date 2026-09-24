from pathlib import Path

import asyncssh
import pytest

from panopticon.init_keys import ensure_host_key


def test_missing_key_is_created(tmp_path: Path):
    path = tmp_path / "keys" / "ssh_host_key"

    created = ensure_host_key(path)

    assert created is True
    assert path.is_file()

    # A file existing isn't enough: it must contain a usable key.
    key = asyncssh.read_private_key(path)
    assert key.get_algorithm() == "ssh-ed25519"


def test_existing_key_is_preserved(tmp_path: Path):
    path = tmp_path / "ssh_host_key"
    ensure_host_key(path)
    original_contents = path.read_bytes()

    created = ensure_host_key(path)

    assert created is False
    assert path.read_bytes() == original_contents


def test_invalid_existing_key_is_not_replaced(tmp_path: Path):
    path = tmp_path / "ssh_host_key"
    original_contents = b"this is not an SSH private key"
    path.write_bytes(original_contents)

    with pytest.raises(asyncssh.KeyImportError):
        ensure_host_key(path)

    assert path.read_bytes() == original_contents
