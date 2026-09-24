# Panopticon

Panopticon is an SSH honeypot that simulates shell interactions and emits structured events for a number of event types. Persistent event storage, an API and a dashboard are planned for the future.

## Quick Start

1. Clone the repository and change directory

`git clone git@github.com:bgr-github/Panopticon.git && cd Panopticon`

2. Create Docker container & generate SSH keys

```bash
docker compose build
docker compose run --rm ssh python -m panopticon.init_keys
docker compose up -d
```

3. Test the server

`ssh <username>@127.0.0.1 -p 2222`

4. To shut down the server
`docker compose down`

## Information

The honeypot currently accepts any password from any username. Ensure you use dummy credentials when testing as everything is stored in plain text.

Upon connecting to the server, the attacker will see a welcome banner and a shell prompt. The welcome banner will be updated down the line when I start working on the server realism.



## Creating commands
You are more than welcome to create commands for Panopticon using the module template. The command handler will read all matching modules in the `honeypots/ssh/commands/` folder and load them into registry.

Here is the echo command as an example. Return type must be a `list[str]`, even if it is just one line.

- `NAME` - Name of the command. File name will be used if this is not present.
- `MAN` - Manual text for this command, should match Unix systems exactly. `man echo` for example.

```py
from panopticon.honeypots.ssh.context import SSHCommandContext

NAME = "echo"
MAN = "echo - display a line of text"


def run(ctx: SSHCommandContext) -> list[str]:
    return [" ".join(ctx.args)]
```

## Testing
To run tests use `uv run --locked pytest panopticon/tests -v`. SSH integration tests do not require Panopticon to be running in Docker to work.