import pytest

from wattnet.storage.config import StorageConfig


class TestStorageConfigDefaults:
    def test_storage_clients_default_empty(self):
        assert StorageConfig().storage_clients == []

    def test_timeseries_step_minutes_default(self):
        assert StorageConfig().timeseries_step_minutes == 15

    def test_plugin_configs_default_empty(self):
        assert StorageConfig().plugin_configs == {}


class TestStorageConfigInstantiation:
    def test_all_fields_overridable(self):
        cfg = StorageConfig(
            timeseries_step_minutes=30,
            storage_clients=["clickhouse"],
            plugin_configs={"clickhouse": {"host": "myhost", "port": 9999}},
        )
        assert cfg.timeseries_step_minutes == 30
        assert cfg.storage_clients == ["clickhouse"]
        assert cfg.plugin_configs == {"clickhouse": {"host": "myhost", "port": 9999}}

    def test_storage_clients_list_is_independent_between_instances(self):
        a = StorageConfig()
        b = StorageConfig()
        a.storage_clients.append("clickhouse")
        assert b.storage_clients == []

    def test_plugin_configs_dict_is_independent_between_instances(self):
        a = StorageConfig()
        b = StorageConfig()
        a.plugin_configs["clickhouse"] = {"host": "x"}
        assert b.plugin_configs == {}


class TestStorageConfigValidation:
    def test_zero_step_raises_value_error(self):
        with pytest.raises(ValueError, match="timeseries_step_minutes"):
            StorageConfig(timeseries_step_minutes=0)

    def test_negative_step_raises_value_error(self):
        with pytest.raises(ValueError, match="timeseries_step_minutes"):
            StorageConfig(timeseries_step_minutes=-1)

    def test_positive_step_does_not_raise(self):
        cfg = StorageConfig(timeseries_step_minutes=1)
        assert cfg.timeseries_step_minutes == 1

    def test_duplicate_storage_clients_raises_value_error(self):
        with pytest.raises(ValueError, match="duplicate entries"):
            StorageConfig(storage_clients=["clickhouse", "clickhouse"])

    def test_no_duplicate_storage_clients_does_not_raise(self):
        cfg = StorageConfig(storage_clients=["clickhouse", "postgres"])
        assert len(cfg.storage_clients) == 2


class TestStorageConfigImmutability:
    def test_reassigning_field_raises(self):
        from dataclasses import FrozenInstanceError

        cfg = StorageConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.timeseries_step_minutes = 30
