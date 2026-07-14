from logger import log_event

NAME = "wget"
MAN = "wget - The non-interactive network downloader"


def run(args, session):
    urls = [a for a in args if not a.startswith("-")]
    if not urls:
        return "wget: missing URL\nUsage: wget [OPTION]... [URL]..."

    fs = session["fs"]
    cwd = session["cwd"]

    outputs = []
    for url in urls:
        log_event(
            "download_attempt",
            session=session["id"],
            tool="wget",
            url=url,
            src_ip=session["src_ip"],
        )
        filename = url.rstrip("/").split("/")[-1] or "index.html"
        target = fs.resolve(cwd, filename)

        # Save a PLACEHOLDER, never the real remote content — we never fetch.
        saved = fs.write_file(target, f"[downloaded from {url}]\n")
        if not saved:
            outputs.append(f"{filename}: Cannot write to '{filename}' (No such file or directory)")
        else:
            outputs.append(_fake_download(url, filename))
    return "\n".join(outputs)


def _fake_download(url, filename):
    return (
        f"--2024-11-14 12:00:01--  {url}\n"
        f"Resolving {_host(url)}... 93.184.216.34\n"
        f"Connecting to {_host(url)}|93.184.216.34|:80... connected.\n"
        f"HTTP request sent, awaiting response... 200 OK\n"
        f"Length: 3048 (3.0K) [application/octet-stream]\n"
        f"Saving to: '{filename}'\n"
        f"\n"
        f"{filename}          100%[===================>]   3.00K  --.-KB/s    in 0s\n"
        f"\n"
        f"2024-11-14 12:00:01 (12.4 MB/s) - '{filename}' saved [3048/3048]"
    )


def _host(url):
    stripped = url.split("://")[-1]
    return stripped.split("/")[0]
