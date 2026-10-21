# Panopticon

Panopticon is an SSH honeypot that simulates shell interactions and stores structured events in SQLite. An API and a dashboard are planned for the future.

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

## Event database

The SSH server creates `data/panopticon.sqlite3` and its schema automatically on startup. Python's built-in `sqlite3` module provides storage; no database server or Redis service is required. All event types, including simulated transfer attempts, are stored in the `events` table.

The collector receives an `EventStore` interface, and `SQLiteEventStore` implements database setup and persistence. A single asynchronous collector sends writes to a background thread, keeping database operations outside the SSH event loop. New storage implementations can be injected without changing the commands or SSH callbacks.

Configuration is available in `.env`:

```dotenv
PANOPTICON_DATABASE__PATH=data/panopticon.sqlite3
PANOPTICON_DATABASE__TIMEOUT=5
PANOPTICON_DATABASE__QUEUE_CAPACITY=1000
```

Paths are relative to the working directory unless absolute. The timeout controls how long a write waits for a database lock; queue capacity limits pending events. Start the server from the project root:

```bash
uv sync --locked
uv run python -m panopticon.init_keys
uv run python -m panopticon.honeypots.ssh.server
```

The table contains indexed `id`, `timestamp`, `session_id`, `src_ip`, `src_port` and `event_type` fields alongside the complete event JSON in `payload`. Indexes support time, session, source-IP and event-type queries; source port is stored but not separately indexed. Indexed timestamps use UTC, while the JSON preserves the original event fields. Replaying an existing ID leaves the stored event unchanged.

For example, run this query with a SQLite client:

```sql
SELECT timestamp, event_type, session_id, src_ip, payload
FROM events
ORDER BY timestamp DESC, id DESC
LIMIT 50;
```

In Docker, the database lives at `/app/data/panopticon.sqlite3` in the `ssh_data` named volume. `docker compose down` preserves it; `docker compose down -v` removes the volumes and their collected data. Existing Redis configuration is accepted for compatibility but unused.

SQLite uses WAL journalling and full commit synchronisation. Graceful shutdown closes SSH connections, records disconnect events and drains the writer. `EventHandler.publish()` accepts a snapshot into memory; it does not mean the event is committed yet. Queue overflow raises an error, and storage failures stop the writer and listening service rather than being reported as successful persistence. Pending events have no durable spool or automatic retry, so an abrupt crash or failed storage write can lose uncommitted events. Back up a running WAL database with SQLite's backup facility; copying only the main database file can omit recent commits.

## File transfer attempts

The shell recognises `wget` downloads and `curl` downloads/uploads. Transfers are simulated: no network requests are made, no payloads are fetched or executed, and no virtual files are created or changed. The command response states that the attempt was recorded.

Direction is measured from the honeypot: fetching a remote URL is a download; sending a virtual file to a remote URL is an upload.

```bash
wget https://example.test/payload.sh
wget -qO /tmp/payload.sh https://example.test/payload.sh
curl -fsSL https://example.test/payload.sh -o /tmp/payload.sh
curl -T readme.txt https://example.test/upload
curl --data-binary @readme.txt https://example.test/upload
curl -F 'file=@readme.txt' https://example.test/upload
```

`FileDownloaded` and `FileUploaded` contain the original command, URL, filename, inferred MIME type, virtual path, method and connection metadata. Upload size is included when the source exists in the virtual filesystem; otherwise it is unknown. Download size is unknown because the content is never fetched. Every transfer event has `status="attempted"` and `simulated=true`; these events do not prove that a transfer completed. `FileDownload` and `FileUpload` remain aliases for the new class names.

Supported URLs use HTTP, HTTPS or FTP. `wget` supports multiple URLs, `-O`/`--output-document`, `-P`/`--directory-prefix`, and common quiet/continue flags. `curl` supports one URL, `-o`/`--output`, `-O`/`--remote-name`, `-T`/`--upload-file`, file-backed `--data`, `--data-binary`, and `-F`/`--form`, plus common `-fsSLk` flags. PUT and POST uploads are identified from the selected option; FTP uses the same direction categories. The method field describes the requested operation rather than an observed network exchange.

Quoted arguments are parsed without executing a host shell. Unsupported options and malformed requests return an error and retain their raw command event. Pipelines, shell scripts, SCP and SFTP are not implemented by these commands. MIME types are inferred from filenames rather than inspected file contents.



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
