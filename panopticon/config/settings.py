from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class SSHHoneypotSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = Field(default=2222, ge=1, le=65535)
    host_key_path: list[Path] = Field(
        default_factory=lambda: [Path("keys/ssh_host_key")],
        min_length=1,
    )


class LoggingSettings(BaseSettings):
    log_dir: Path = Path("logs")
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class RedisSettings(BaseSettings):
    dsn: RedisDsn = RedisDsn("redis://localhost:6379/0")


class DatabaseSettings(BaseModel):
    path: Path = Path("data/panopticon.sqlite3")
    timeout: float = Field(default=5.0, gt=0)
    queue_capacity: int = Field(default=1000, ge=1)


class APISettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    poll_interval: float = Field(default=0.5, gt=0, le=60)
    heartbeat_interval: float = Field(default=15.0, gt=0, le=60)


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
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    # Retained so existing .env files remain valid; SQLite does not use Redis.
    redis: RedisSettings = Field(default_factory=RedisSettings)


settings = Settings()
