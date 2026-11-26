"""latest_timestamp: where the data of a series stops, in one query."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from clickhouse_connect.driver.exceptions import OperationalError

from wattnet.storage.clients.base import BaseStorageClient
from wattnet.storage.clients.manager import StorageClientsManager
from wattnet.storage.clients.plugins.clickhouse import ClickHouseClient
from wattnet.storage.config import StorageConfig
from wattnet.storage.repository import MetricsRepository

BEFORE = datetime(2021, 10, 17, 21, 45, tzinfo=timezone.utc)


@pytest.fixture
def db():
    """The mocked ClickHouse connection every client of the plugin gets."""
    conn = MagicMock()
    conn.query.return_value.result_rows = []
    with patch("clickhouse_connect.get_client", return_value=conn):
        yield conn


def _client():
    client = ClickHouseClient(
        config=StorageConfig(plugin_configs={"clickhouse": {"database": "test"}})
    )
    client._stop_event.set()
    client._flush_thread.join(timeout=1)
    return client


class TestClickHouse:
    def test_returns_the_latest_timestamp_in_utc(self, db):
        client = _client()
        db.query.return_value.result_rows = [(datetime(2021, 9, 27, 6, 45), 1918)]
        latest = client.latest_timestamp("zone_import", BEFORE)
        assert latest == datetime(2021, 9, 27, 6, 45, tzinfo=timezone.utc)

    def test_none_when_there_is_no_point(self, db):
        client = _client()
        # max() of nothing is the epoch in ClickHouse: the count tells it apart.
        db.query.return_value.result_rows = [(datetime(1970, 1, 1), 0)]
        assert client.latest_timestamp("zone_import", BEFORE) is None

    def test_query_filters_labels_and_bounds(self, db):
        client = _client()
        db.query.return_value.result_rows = [(datetime(2021, 9, 27), 1)]
        client.latest_timestamp(
            "zone_import",
            BEFORE,
            labels={"from": "IT_SARDINIA", "data_state": "official", "nope": "x"},
            after=datetime(2021, 1, 1, tzinfo=timezone.utc),
        )
        sql = db.query.call_args.args[0]
        params = db.query.call_args.kwargs["parameters"]
        assert sql.startswith("SELECT max(timestamp), count() FROM test.zone_import FINAL")
        assert "timestamp < toDateTime({before:String})" in sql
        assert "timestamp >= toDateTime({after:String})" in sql
        assert "from_zone = {label_from_zone:String}" in sql
        assert "data_state = {label_data_state:String}" in sql
        assert "nope" not in sql  # not a column of the table
        assert params["before"] == "2021-10-17 21:45:00"
        assert params["after"] == "2021-01-01 00:00:00"
        assert params["label_from_zone"] == "IT_SARDINIA"
        assert params["label_data_state"] == "official"

    def test_without_after_there_is_no_lower_bound(self, db):
        client = _client()
        db.query.return_value.result_rows = [(datetime(2021, 9, 27), 1)]
        client.latest_timestamp("zone_import", BEFORE)
        assert "after" not in db.query.call_args.args[0]

    def test_a_broken_connection_is_retried_once(self, db):
        client = _client()
        good = MagicMock(result_rows=[(datetime(2021, 9, 27), 1)])
        db.query.reset_mock()  # the start-up of the client queries too
        db.query.side_effect = [OperationalError("gone"), good]
        assert client.latest_timestamp("zone_import", BEFORE) == datetime(
            2021, 9, 27, tzinfo=timezone.utc
        )
        assert db.query.call_count == 2


class TestOtherLayers:
    def test_a_backend_without_support_says_so(self):
        class Minimal(BaseStorageClient):
            def read_metrics(
                self, metric_name, start=None, end=None, labels=None, params=None
            ):
                return []

            def write_metrics(self, metrics):
                pass

        with pytest.raises(NotImplementedError):
            Minimal().latest_timestamp("zone_import", BEFORE)

    def test_manager_takes_the_latest_of_its_clients(self):
        manager = StorageClientsManager(StorageConfig())
        a, b, c = MagicMock(), MagicMock(), MagicMock()
        a.latest_timestamp.return_value = datetime(2021, 9, 1, tzinfo=timezone.utc)
        b.latest_timestamp.return_value = None
        c.latest_timestamp.return_value = datetime(2021, 9, 27, tzinfo=timezone.utc)
        manager.storage_clients = {"a": a, "b": b, "c": c}
        labels = {"zone": "ES"}
        assert manager.latest_timestamp("zone_load", BEFORE, labels) == datetime(
            2021, 9, 27, tzinfo=timezone.utc
        )
        a.latest_timestamp.assert_called_once_with("zone_load", BEFORE, labels, None)

    def test_manager_none_when_no_client_has_a_point(self):
        manager = StorageClientsManager(StorageConfig())
        only = MagicMock()
        only.latest_timestamp.return_value = None
        manager.storage_clients = {"only": only}
        assert manager.latest_timestamp("zone_load", BEFORE) is None

    def test_repository_asks_the_manager(self):
        with patch(
            "wattnet.storage.repository.metrics_repository.StorageClientsManager"
        ) as manager_class:
            manager = manager_class.return_value
            manager.latest_timestamp.return_value = None
            repo = MetricsRepository(StorageConfig())
            after = datetime(2021, 1, 1, tzinfo=timezone.utc)
            assert repo.latest_timestamp("zone_load", BEFORE, {"zone": "ES"}, after) is None
            manager.latest_timestamp.assert_called_once_with(
                "zone_load", BEFORE, {"zone": "ES"}, after
            )
