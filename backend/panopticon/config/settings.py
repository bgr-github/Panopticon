from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROJECT_ROOT = BASE_DIR.parent.parent


class RedisSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 6379
    stream_name: str = "panopticon.events"

    @property
    def dsn(self) -> str:
        return f"redis://{self.host}:{self.port}"


class DatabaseSettings(BaseSettings):
    user: str = "panopticon"
    password: str = "testpass"
    host: str = "localhost"
    port: int = 5432
    name: str = "panopticon"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class SSHHoneypotSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 2222
    host_key_path: list[Path] = Field(default_factory=lambda: [PROJECT_ROOT / "keys" / "ssh_host_key"])


class LoggingSettings(BaseSettings):
    log_dir: Path = PROJECT_ROOT / "logs"
    internal_log_file: str = "internal.log"

    @property
    def internal_log_path(self) -> Path:
        return self.log_dir / self.internal_log_file


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", extra="ignore")

    app_name: str = "panopticon"
    environment: str = "dev"

    redis: RedisSettings = Field(default_factory=RedisSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ssh: SSHHoneypotSettings = Field(default_factory=SSHHoneypotSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()
