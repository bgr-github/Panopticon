from pathlib import Path

from panopticon.config.settings import DatabaseSettings, LoggingSettings, RedisSettings


def test_redis_dsn_is_derived_from_host_and_port() -> None:
    settings = RedisSettings(host="redis", port=6380)

    assert settings.dsn == "redis://redis:6380"


def test_database_dsn_is_derived_from_connection_fields() -> None:
    settings = DatabaseSettings(
        user="user",
        password="secret",
        host="db",
        port=5433,
        name="panopticon_test",
    )

    assert settings.dsn == "postgresql://user:secret@db:5433/panopticon_test"


def test_internal_log_path_combines_dir_and_file_name(tmp_path: Path) -> None:
    settings = LoggingSettings(log_dir=tmp_path, internal_log_file="test.log")

    assert settings.internal_log_path == tmp_path / "test.log"
