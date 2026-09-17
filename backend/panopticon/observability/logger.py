import logging
import sys

from panopticon.config.settings import settings

_logging_level: int = logging.DEBUG if settings.environment == "dev" else logging.INFO


def configure_logging(service: str) -> None:
    """Configures the logging module on a per-service basis.

    Args:
        service_name (str): Name of the service being logged
    """
    log_dir = settings.logging.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=_logging_level,
        format=settings.logging.format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / f"{service}.log", encoding="utf-8"),
        ],
    )
