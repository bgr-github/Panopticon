from logging import Formatter
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent
PROJECT_ROOT = BASE_DIR.parent.parent


class SSHHoneypotSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 2222
    host_key_path: list[Path] = Field(default_factory=lambda: [PROJECT_ROOT / "keys" / "ssh_host_key"])


class LoggingSettings(BaseSettings):
    log_dir: Path = PROJECT_ROOT / "logs"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class Settings(BaseSettings):
    app_name: str = "panopticon"
    environment: str = "dev"

    ssh: SSHHoneypotSettings = Field(default_factory=SSHHoneypotSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()

print(__name__)
