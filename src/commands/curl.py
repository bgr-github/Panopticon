from logger import log_event

NAME = "curl"
MAN = "curl - transfer a URL"


def run(args, session):
    urls = [a for a in args if not a.startswith("-")]
    if not urls:
        return "curl: try 'curl --help' for more information"

    outputs = []
    for url in urls:
        log_event(
            "download_attempt",
            session=session["id"],
            tool="curl",
            url=url,
            src_ip=session["src_ip"],
        )
        outputs.append("")
    return "\n".join(outputs)
