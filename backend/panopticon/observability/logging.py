import logging
import sys
from pathlib import Path
from panopticon.config.settings import settings


class Logger:

    logger: logging.Logger

    def __init__(
        self,
        name: str,
        file_path: Path | None = None,
        level: int = logging.INFO,
        sys_out: bool = True,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        path = file_path or settings.logging.internal_log_path
        path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure handlers do not already exist
        if not self.logger.handlers:
            file_handler = logging.FileHandler(path)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

            if sys_out:
                stream_handler = logging.StreamHandler(sys.stdout)
                stream_handler.setLevel(level)
                stream_handler.setFormatter(formatter)
                self.logger.addHandler(stream_handler)

    # Logger.<level>() rather than Logger.logger.<level>()
    def info(self, module: str, message: str):
        self.logger.info(f"[{module}]: {message}")

    def warning(self, module: str, message: str):
        self.logger.warning(f"[{module}]: {message}")

    def error(self, module: str, message: str):
        self.logger.error(f"[{module}]: {message}")

    def debug(self, module: str, message: str):
        self.logger.debug(f"[{module}]: {message}")


logger: Logger
if settings.environment == "dev":
    logger: Logger = Logger("panopticon.internal", settings.logging.internal_log_path, level=logging.DEBUG)
else:
    logger: Logger = Logger("panopticon.internal", settings.logging.internal_log_path)
