# Contributing to Panopticon

Thanks for your interest in improving Panopticon. This guide covers how the
project is structured, how to add commands and personas, the one safety rule that
can never be broken, and what a good pull request looks like.

Panopticon is MIT licensed. By contributing, you agree that your contributions
are licensed under the same terms.

---

## The one rule that governs everything

Panopticon is a honeypot. Its entire value, and its entire safety model, rests on
a single invariant:

> **Attacker input is data. It is logged and answered with simulated output. It
> is never executed, never used to touch the real system, and never used to reach
> the network.**

Concretely, code you contribute must never:

- run attacker input as a shell command, or pass it to `os.system`, `subprocess`,
  `eval`, `exec`, or similar,
- read, write, or delete real files on the host in response to attacker input
  (the fake filesystem is entirely in memory),
- make outbound network requests driven by attacker input (for example, actually
  fetching a URL an attacker passes to `wget`).

If a change would make any attacker-supplied string cause a real effect on the
host or network, it will not be merged, no matter how much realism it adds. The
moment a honeypot executes attacker input, it stops being a decoy and becomes a
foothold. Everything else in this guide is secondary to this.

---

## Project layout

```
src/
  server.py            SSH server, sessions, auth
  command_handler.py   Command discovery and dispatch
  config.py            Persona profile loading and validation
  filesystem.py        In-memory FakeFS interface
  logger.py            Structured JSON logging
  commands/            One module per command
config.yaml            Example persona profile
filesystem/<persona>/  Fake filesystem content for each persona
```

---

## Adding a command

Commands are the most common contribution and the easiest. Each command is a
single module in `src/commands/`, auto-discovered at startup. There is no central
list to edit.

### The contract

A command module exposes:

- `run(args, session)` (required): the function that runs the command.
- `NAME` (optional): the command name. Defaults to the filename if omitted.
- `MAN` (optional): the manual-page text shown by `man <command>`.

```python
"""uname - print system information."""

NAME = "uname"
MAN = "uname - print system information"


def run(args, session):
    """Return the string to display.

    args:    list of arguments after the command name (e.g. ["-a"])
    session: shared per-connection state (see below)
    returns: a string; the dispatcher handles the trailing newline
    """
    host = session["profile"]["host"]
    if "-a" in args:
        return f"{host['kernel_name']} {host['hostname']} {host['kernel_release']}"
    return host["kernel_name"]
```

### What's in `session`

`session` is a dict of shared per-connection state. The keys you'll use most:

| Key         | What it holds                                              |
|-------------|------------------------------------------------------------|
| `username`  | The logged-in username                                     |
| `cwd`       | The current working directory (a string path)              |
| `fs`        | The `FakeFS` object for this session                       |
| `profile`   | The loaded persona (host identity, os_release, accounts)   |
| `id`        | The session ID (use this when logging)                     |
| `src_ip`    | The attacker's source IP                                   |

Reading machine facts from `session["profile"]` rather than hardcoding them is
what keeps commands consistent with the rest of the persona. A command that
hardcodes a hostname will contradict `hostname`, `uname`, and the config the
moment someone runs a different persona.

### Using the fake filesystem

Never touch the raw tree. Go through the `FakeFS` interface on `session["fs"]`:

```python
fs = session["fs"]
cwd = session["cwd"]
target = fs.resolve(cwd, args[0])   # normalise a path (handles . .. absolute/relative)

if not fs.exists(target):
    return f"{args[0]}: No such file or directory"
if fs.is_dir(target):
    names = fs.list_dir(target)     # sorted child names
else:
    content = fs.read_file(target)  # file content as a string
```

Going through the interface (rather than indexing the dict directly) is what lets
the filesystem's internal representation change without breaking your command.

### Realism guidance

The point of a command is to be convincing, not just to run:

- **Match real output.** Compare against the real command on a real Linux box.
  Column alignment, exact error wording, and phrasing all matter. A subtly-wrong
  error message (for example `Unknown command` instead of the real
  `command not found`) is a fingerprint.
- **Stay consistent with the persona.** If your command names services, users, or
  files, they must agree with the rest of the machine (the fake filesystem, the
  accounts in the profile, what `uname` reports).
- **Fake success over honest failure where it keeps an attacker engaged**, but
  never by doing anything real. A simulated success string is fine; an actual
  action is not.
- **Handle arguments.** Attackers rarely type a bare command. Handle the common
  flags (`ls -la`, `uname -a`) at minimum.

### Logging from a command

If your command captures something worth recording (a URL, an interesting
action), log it through the logger:

```python
from logger import log_event

log_event("download_attempt", session=session["id"], url=url, src_ip=session["src_ip"])
```

Use the field name `session` for the session ID consistently, so events can be
correlated across the whole log.

---

## Adding a persona

A persona is a YAML profile plus a fake filesystem directory. To add one:

1. Copy `config.yaml` and edit the identity, accounts, and `filesystem.root`.
2. Create the matching `filesystem/<persona>/` directory with the fake files.
3. Keep everything consistent. This is the part that matters most:
   - `etc/os-release` in the filesystem must match the `os_release` block.
   - `etc/passwd` must list the same users (and uids) as the profile `accounts`.
   - `etc/hostname` must match `host.hostname`.
   - `proc/cpuinfo` and `proc/meminfo` must describe a machine consistent with
     the kernel and architecture the profile reports.

Harvesting real files from a genuine machine of that type is a good starting
point, but curate them into a coherent, plausibly-aged server rather than copying
a freshly-installed box wholesale.

Empty directories are not tracked by git. If a persona needs an empty directory
(for example `/tmp` or `/var/log`), add a `.gitkeep` file inside it.

---

## Testing

Commands are near-pure functions of `(args, session)` that return strings, which
makes them straightforward to test without a live SSH connection. A test builds a
fake session (including a `FakeFS` from a small in-memory tree), calls `run`, and
asserts on the returned string.

Please include tests for new commands, and run the existing suite before opening a
PR:

```bash
pytest
```

A command with tests can be verified by reviewers and protected against future
changes; one without is a manual gamble every time the code around it changes.

---

## Coding style

- Follow PEP 8. Running `black` (formatting) and `flake8` (linting) before
  committing keeps this automatic.
- Write docstrings for modules and functions. Explain *why* where the reasoning
  isn't obvious from the code; don't just restate *what* the line does.
- Keep commands small and focused. The surrounding code should stay simple; put
  cleverness into realistic behaviour, not into the plumbing.

---

## Pull requests

Before opening a PR, please check:

- [ ] The change respects the safety invariant (no execution of attacker input,
      no real filesystem or network access driven by attacker input).
- [ ] New commands follow the `run(args, session)` contract and read machine
      facts from the persona rather than hardcoding them.
- [ ] New commands and personas are internally consistent with the rest of the
      machine.
- [ ] Tests are included and the suite passes.
- [ ] Code is formatted and linted.

Keep PRs focused on one change where you can; it makes review faster and history
clearer. A short description of what the change does and why is always welcome.

---

## Reporting security issues

If you find a way that attacker input could cause a real effect on the host or
network (a break in the core invariant), please treat it as a security issue and
report it privately to the maintainer rather than opening a public issue, so it
can be fixed before it's widely known.

Thanks for helping make Panopticon better.