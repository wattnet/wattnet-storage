from pathlib import Path

from wattnet.storage.settings import Settings


def bare() -> Settings:
    """Settings instance with no env file and no env vars interference."""
    return Settings(_env_file=None)


class TestSettingsDefaults:
    """Test class-level defaults, bypassing any .env.* files."""

    def test_storage_clients_default_empty(self, monkeypatch):
        monkeypatch.delenv("STORAGE_CLIENTS", raising=False)
        assert bare().storage_clients == []

    def test_clickhouse_host_default(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
        assert bare().clickhouse_host == "localhost"

    def test_clickhouse_port_default(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_PORT", raising=False)
        assert bare().clickhouse_port == 9000

    def test_clickhouse_user_default(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_USER", raising=False)
        assert bare().clickhouse_user == "default"

    def test_clickhouse_password_default_empty(self, monkeypatch):
        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
        assert bare().clickhouse_password == ""

    def test_database_default(self, monkeypatch):
        monkeypatch.delenv("DATABASE", raising=False)
        assert bare().database == "wattnet"

    def test_timeseries_step_minutes_default(self, monkeypatch):
        monkeypatch.delenv("TIMESERIES_STEP_MINUTES", raising=False)
        assert bare().timeseries_step_minutes == 15

    def test_log_level_default(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert bare().log_level == "INFO"

    def test_log_handlers_default(self, monkeypatch):
        monkeypatch.delenv("LOG_HANDLERS", raising=False)
        assert bare().log_handlers == ["console"]

    def test_log_file_is_path(self):
        assert isinstance(bare().log_file, Path)

    def test_log_file_ends_with_expected_name(self):
        assert bare().log_file.name == "wattnet-storage.log"

    def test_storage_db_url_default(self, monkeypatch):
        monkeypatch.delenv("STORAGE_DB_URL", raising=False)
        assert bare().storage_db_url == "http://localhost:8428"


class TestSettingsEnvOverrides:
    def test_clickhouse_host_from_env(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_HOST", "myhost")
        assert Settings().clickhouse_host == "myhost"

    def test_clickhouse_port_from_env(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_PORT", "9999")
        assert Settings().clickhouse_port == 9999

    def test_database_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE", "mydb")
        assert Settings().database == "mydb"

    def test_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert Settings().log_level == "DEBUG"

    def test_timeseries_step_minutes_from_env(self, monkeypatch):
        monkeypatch.setenv("TIMESERIES_STEP_MINUTES", "30")
        assert Settings().timeseries_step_minutes == 30

    def test_storage_clients_from_env(self, monkeypatch):
        monkeypatch.setenv("STORAGE_CLIENTS", '["clickhouse"]')
        s = Settings()
        assert s.storage_clients == ["clickhouse"]

    def test_storage_clients_multiple_from_env(self, monkeypatch):
        monkeypatch.setenv("STORAGE_CLIENTS", '["clickhouse", "other"]')
        s = Settings()
        assert s.storage_clients == ["clickhouse", "other"]

    def test_log_handlers_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_HANDLERS", '["file"]')
        s = Settings()
        assert s.log_handlers == ["file"]

    def test_case_insensitive_env(self, monkeypatch):
        monkeypatch.setenv("clickhouse_host", "lower-case")
        assert Settings().clickhouse_host == "lower-case"
