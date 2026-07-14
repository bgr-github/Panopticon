"""Load a fake filesystem tree from a directory into memory.

Walks the real folder once at startup and builds a nested dictionary. This is load time only.
The honeypot never reads real disk in response to an attacker's input.
"""

from pathlib import Path
