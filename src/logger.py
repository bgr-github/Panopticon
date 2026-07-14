import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path


def setup_logging(log_file="logs/panopticon.log"):
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("panopticon")
    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def log_event(event, **fields):
    logging.getLogger("panopticon").info(
        json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields})
    )
