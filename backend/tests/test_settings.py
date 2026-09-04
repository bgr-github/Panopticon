from pathlib import Path

from panopticon.config.settings import DatabaseSettings, LoggingSettings, RedisSettings


def test_redis_dsn() -> None:
    settings = RedisSettings(host="localhost", port=6379)

    assert settings.dsn == "redis://localhost:6379"


def test_database_dsn() -> None:
    settings = DatabaseSettings(
        user="panopticon",
        password="testpass",
        host="localhost",
        port=5432,
        name="panopticon",
    )

    assert settings.dsn == "postgresql://panopticon:testpass@localhost:5432/panopticon"


def test_logging_path() -> None:
    settings = LoggingSettings(
        log_dir=Path("logs"),
        internal_log_file="internal.log",
    )

    assert settings.internal_log_path == Path("logs") / "internal.log"
