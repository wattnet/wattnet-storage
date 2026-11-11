"""Declared metrics (MetricSpec), replicated tables and ping."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from clickhouse_connect.driver.exceptions import OperationalError

from wattnet.storage.clients.base import BaseStorageClient
from wattnet.storage.clients.manager import StorageClientsManager
from wattnet.storage.clients.plugins.clickhouse import ClickHouseClient
from wattnet.storage.config import StorageConfig
from wattnet.storage.models import Metric, MetricSpec, MetricType
from wattnet.storage.repository import MetricsRepository


def _config(**clickhouse):
    return StorageConfig(
        plugin_configs={"clickhouse": {"database": "test", **clickhouse}}
    )


@pytest.fixture
def db():
    """The mocked ClickHouse connection every client of the plugin gets."""
    conn = MagicMock()
    conn.query.return_value.result_rows = []
    with patch("clickhouse_connect.get_client", return_value=conn):
        yield conn


def _client(**clickhouse):
    client = ClickHouseClient(config=_config(**clickhouse))
    client._stop_event.set()
    client._flush_thread.join(timeout=1)
    return client


def _commands(db):
    return [c.args[0] for c in db.command.call_args_list]


class TestMetricSpec:
    def test_default_key_leaves_out_the_version_labels(self):
        spec = MetricSpec("zone_price", ("zone", "market", "valid", "unit"))
        assert spec.key == ("zone", "market")

    def test_explicit_key(self):
        assert MetricSpec("zone_price", ("zone", "market"), key=("zone",)).key == (
            "zone",
        )

    def test_labels_given_as_a_list_become_a_tuple(self):
        assert MetricSpec("zone_price", ["zone"]).labels == ("zone",)

    def test_columns(self):
        spec = MetricSpec(
            "zone_price", ("zone", "year"), types={"year": "Nullable(Int32)"}
        )
        assert spec.columns() == [
            ("timestamp", "DateTime"),
            ("value", "Float32"),
            ("zone", "LowCardinality(String)"),
            ("year", "Nullable(Int32)"),
            ("updated_at", "DateTime"),
        ]

    @pytest.mark.parametrize(
        "name, labels, extra",
        [
            ("Zone-Price", ("zone",), {}),
            ("zone_price;drop", ("zone",), {}),
            ("zone_price", ("zone name",), {}),
            ("zone_price", ("value",), {}),
            ("zone_price", ("zone", "zone"), {}),
            ("zone_price", ("zone",), {"key": ("market",)}),
            ("zone_price", ("zone",), {"types": {"market": "String"}}),
            ("zone_price", ("zone",), {"types": {"zone": "String) ENGINE = Log --"}}),
        ],
    )
    def test_invalid_specs_are_rejected(self, name, labels, extra):
        with pytest.raises(ValueError):
            MetricSpec(name, labels, **extra)


class TestMetricName:
    def test_a_declared_metric_is_named_by_a_string(self):
        assert Metric("zone_price", 1.0).name == "zone_price"

    def test_a_built_in_metric_keeps_its_value(self):
        assert Metric(MetricType.ZONE_LOAD, 1.0).name == "zone_load"


class TestBootstrap:
    def test_not_replicated_by_default(self, db):
        _client()
        sql = _commands(db)
        assert sql[0] == "CREATE DATABASE IF NOT EXISTS test"
        assert all("Replicated" not in s for s in sql)

    def test_replicated_database_and_tables(self, db):
        _client(replicated=True)
        sql = _commands(db)
        assert sql[0] == (
            "CREATE DATABASE IF NOT EXISTS test ENGINE = "
            "Replicated('/clickhouse/databases/test', '{shard}', '{replica}')"
        )
        tables = [s for s in sql if "CREATE TABLE" in s]
        assert tables and all(
            "ReplicatedReplacingMergeTree(updated_at)" in s for s in tables
        )

    def test_missing_columns_of_an_existing_table_are_added(self, db):
        db.query.return_value.result_rows = [("timestamp", "DateTime")]
        _client()
        assert (
            "ALTER TABLE test.zone_load ADD COLUMN IF NOT EXISTS zone LowCardinality(String)"
            in _commands(db)
        )


class TestRegisterMetric:
    def test_creates_the_table_with_the_key(self, db):
        client = _client()
        client.register_metric(MetricSpec("zone_price", ("zone", "unit")))
        create = _commands(db)[-1]
        assert "test.zone_price" in create
        assert "ORDER BY (timestamp, zone)" in create

    def test_a_registered_metric_is_written(self, db):
        client = _client()
        client.register_metric(MetricSpec("zone_price", ("zone",)))
        client.write_metrics(
            [Metric("zone_price", 2.5, datetime(2026, 1, 1), {"zone": "ES"})]
        )
        row = client._buffer["zone_price"][0]
        assert row[1:3] == [2.5, "ES"]

    def test_an_unregistered_metric_is_not_written(self, db):
        client = _client()
        client.write_metrics([Metric("zone_price", 2.5)])
        assert "zone_price" not in client._buffer

    def test_a_built_in_metric_cannot_be_declared(self, db):
        with pytest.raises(ValueError, match="built-in"):
            _client().register_metric(MetricSpec("zone_load", ("zone",)))


class TestReadUnknownMetric:
    def test_a_table_found_in_clickhouse_can_be_read(self, db):
        client = _client()
        db.query.return_value.result_rows = [
            ("timestamp", "DateTime"),
            ("value", "Float32"),
            ("zone", "LowCardinality(String)"),
        ]
        sql, params = client._build_query(
            "zone_price", datetime(2026, 1, 1), datetime(2026, 1, 2), {"zone": "ES"}
        )
        assert "test.zone_price" in sql and params["label_zone"] == "ES"
        db.query.reset_mock()
        client._build_query("zone_price", datetime(2026, 1, 1), datetime(2026, 1, 2))
        db.query.assert_not_called()  # cached

    def test_a_bad_name_is_rejected_before_asking_clickhouse(self, db):
        client = _client()
        db.query.reset_mock()
        with pytest.raises(ValueError):
            client._build_query(
                "x; DROP TABLE y", datetime(2026, 1, 1), datetime(2026, 1, 2)
            )
        db.query.assert_not_called()

    def test_read_metrics_returns_metrics_named_by_the_table(self, db):
        client = _client()
        with patch.object(client, "_schema", return_value=[("timestamp", "DateTime")]):
            df = MagicMock(empty=False, columns=["timestamp", "value"])
            df.itertuples.return_value = [(MagicMock(), 3.0)]
            db.query_df.return_value = df
            metrics = client.read_metrics(
                "zone_price", datetime(2026, 1, 1), datetime(2026, 1, 2)
            )
        assert metrics[0].name == "zone_price"
        assert metrics[0].updated_at is None


class TestUpdatedAt:
    def test_read_moves_updated_at_out_of_the_labels(self, db):
        import pandas as pd

        client = _client()
        written = pd.Timestamp("2026-01-01 12:00:00")
        df = MagicMock(
            empty=False, columns=["timestamp", "value", "zone", "updated_at"]
        )
        df.itertuples.return_value = [(pd.Timestamp("2026-01-01"), 3.0, "ES", written)]
        db.query_df.return_value = df
        (metric,) = client.read_metrics(
            "zone_load", datetime(2026, 1, 1), datetime(2026, 1, 2)
        )
        assert metric.metadata == {"zone": "ES"}
        assert metric.updated_at == datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


class TestReadRetry:
    def test_a_broken_connection_is_retried_once(self, db):
        client = _client()
        empty = MagicMock(empty=True)
        db.query_df.side_effect = [OperationalError("gone"), empty]
        assert (
            client.read_metrics("zone_load", datetime(2026, 1, 1), datetime(2026, 1, 2))
            == []
        )
        assert db.query_df.call_count == 2


class TestPing:
    def test_true_when_clickhouse_answers(self, db):
        db.ping.return_value = True
        assert _client().ping() is True

    def test_false_when_it_fails(self, db):
        client = _client()
        db.ping.side_effect = RuntimeError("down")
        assert client.ping() is False


class TestOtherBackends:
    def test_a_backend_without_support_says_so(self):
        class Minimal(BaseStorageClient):
            def read_metrics(
                self, metric_name, start=None, end=None, labels=None, params=None
            ):
                return []

            def write_metrics(self, metrics):
                pass

        with pytest.raises(NotImplementedError):
            Minimal().register_metric(MetricSpec("zone_price", ("zone",)))
        with pytest.raises(NotImplementedError):
            Minimal().ping()


class TestManagerAndRepository:
    def test_manager_passes_specs_and_pings_every_client(self):
        manager = StorageClientsManager(StorageConfig())
        a, b = MagicMock(), MagicMock()
        b.ping.return_value = False
        manager.storage_clients = {"a": a, "b": b}
        spec = MetricSpec("zone_price", ("zone",))
        manager.register_metric(spec)
        a.register_metric.assert_called_once_with(spec)
        b.register_metric.assert_called_once_with(spec)
        assert manager.ping() is False

    def test_repository_registers_and_pings(self):
        with patch(
            "wattnet.storage.repository.metrics_repository.StorageClientsManager"
        ) as manager_class:
            manager = manager_class.return_value
            manager.ping.return_value = True
            repo = MetricsRepository(StorageConfig())
            first, second = (
                MetricSpec("a_metric", ("zone",)),
                MetricSpec("b_metric", ("zone",)),
            )
            repo.register_metrics(first, second)
            assert [c.args[0] for c in manager.register_metric.call_args_list] == [
                first,
                second,
            ]
            assert repo.ping() is True
