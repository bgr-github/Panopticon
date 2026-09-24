from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SSHHoneypotSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=2222, ge=1, le=65535)
    host_key_path: list[Path] = Field(
        default_factory=lambda: [Path("keys/ssh_host_key")],
        min_length=1,
    )


class LoggingSettings(BaseModel):
    log_dir: Path = Path("logs")
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PANOPTICON_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    app_name: str = "panopticon"
    environment: Literal["dev", "prod"] = "dev"

    ssh: SSHHoneypotSettings = Field(default_factory=SSHHoneypotSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()
