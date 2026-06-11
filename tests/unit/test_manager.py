from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from wattnet.storage.clients.manager import StorageClientsManager
from wattnet.storage.config import StorageConfig
from wattnet.storage.models import Metric, MetricType


def _make_mock_plugin():
    """Return a mock plugin class whose instances expose read/write_metrics."""
    instance = MagicMock()
    instance.read_metrics.return_value = []
    instance.write_metrics.return_value = None
    plugin_cls = MagicMock(return_value=instance)
    return plugin_cls, instance


@pytest.fixture
def config_empty():
    return StorageConfig(storage_clients=[])


@pytest.fixture
def config_clickhouse():
    return StorageConfig(storage_clients=["clickhouse"])


@pytest.fixture
def mock_plugin_loader_with_clickhouse():
    plugin_cls, instance = _make_mock_plugin()
    mock_loader = MagicMock()
    mock_loader.get_storage_clients_names.return_value = frozenset(["clickhouse"])
    mock_loader.get_storage_clients_extensions.return_value = {"clickhouse": plugin_cls}
    with patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
        yield mock_loader, plugin_cls, instance


class TestStorageClientsManagerInit:
    def test_no_clients_configured_does_not_raise(self, config_empty):
        mgr = StorageClientsManager(config_empty)
        assert mgr is not None

    def test_unknown_client_raises_import_error(self, config_clickhouse):
        mock_loader = MagicMock()
        mock_loader.get_storage_clients_names.return_value = frozenset()
        with patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            with pytest.raises(ImportError, match="clickhouse"):
                StorageClientsManager(config_clickhouse)

    def test_known_client_populates_storage_clients(
        self, config_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        mgr = StorageClientsManager(config_clickhouse)
        assert "clickhouse" in mgr.storage_clients

    def test_client_instance_created(
        self, config_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, plugin_cls, _ = mock_plugin_loader_with_clickhouse
        StorageClientsManager(config_clickhouse)
        plugin_cls.assert_called_once()

    def test_multiple_clients_loaded(self):
        config = StorageConfig(storage_clients=["a", "b"])

        plugin_cls_a, instance_a = _make_mock_plugin()
        plugin_cls_b, instance_b = _make_mock_plugin()

        mock_loader = MagicMock()
        mock_loader.get_storage_clients_names.return_value = frozenset(["a", "b"])
        mock_loader.get_storage_clients_extensions.return_value = {
            "a": plugin_cls_a,
            "b": plugin_cls_b,
        }

        with patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            mgr = StorageClientsManager(config)

        assert set(mgr.storage_clients.keys()) == {"a", "b"}


class TestStorageClientsManagerReadMetrics:
    def test_read_returns_empty_when_no_clients(self, config_empty):
        mgr = StorageClientsManager(config_empty)
        assert mgr.read_metrics("zone_generation") == []

    def test_read_calls_client(
        self, config_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, _, instance = mock_plugin_loader_with_clickhouse
        mgr = StorageClientsManager(config_clickhouse)
        mgr.read_metrics("zone_generation")
        instance.read_metrics.assert_called_once_with(
            "zone_generation", None, None, None, None
        )

    def test_read_passes_params_to_client(
        self, config_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, _, instance = mock_plugin_loader_with_clickhouse
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        labels = {"zone": "ES"}
        mgr = StorageClientsManager(config_clickhouse)
        mgr.read_metrics("zone_generation", start=start, end=end, labels=labels)
        instance.read_metrics.assert_called_once_with(
            "zone_generation", start, end, labels, None
        )

    def test_read_aggregates_from_multiple_clients(self):
        m1 = Metric(MetricType.ZONE_GENERATION, 1.0)
        m2 = Metric(MetricType.ZONE_GENERATION, 2.0)

        config = StorageConfig(storage_clients=["a", "b"])

        plugin_cls_a, instance_a = _make_mock_plugin()
        plugin_cls_b, instance_b = _make_mock_plugin()
        instance_a.read_metrics.return_value = [m1]
        instance_b.read_metrics.return_value = [m2]

        mock_loader = MagicMock()
        mock_loader.get_storage_clients_names.return_value = frozenset(["a", "b"])
        mock_loader.get_storage_clients_extensions.return_value = {
            "a": plugin_cls_a,
            "b": plugin_cls_b,
        }

        with patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            mgr = StorageClientsManager(config)
            result = mgr.read_metrics("zone_generation")

        assert m1 in result
        assert m2 in result
        assert len(result) == 2

    def test_write_does_not_raise_when_no_clients(self, config_empty):
        mgr = StorageClientsManager(config_empty)
        m = Metric(MetricType.ZONE_GENERATION, 1.0)
        mgr.write_metrics([m])  # must not raise


class TestStorageClientsManagerWriteMetrics:
    def test_write_calls_client(
        self, config_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, _, instance = mock_plugin_loader_with_clickhouse
        m = Metric(MetricType.ZONE_GENERATION, 1.0)
        mgr = StorageClientsManager(config_clickhouse)
        mgr.write_metrics([m])
        instance.write_metrics.assert_called_once_with([m])

    def test_write_sends_to_all_clients(self):
        m = Metric(MetricType.ZONE_GENERATION, 1.0)
        config = StorageConfig(storage_clients=["a", "b"])

        plugin_cls_a, instance_a = _make_mock_plugin()
        plugin_cls_b, instance_b = _make_mock_plugin()

        mock_loader = MagicMock()
        mock_loader.get_storage_clients_names.return_value = frozenset(["a", "b"])
        mock_loader.get_storage_clients_extensions.return_value = {
            "a": plugin_cls_a,
            "b": plugin_cls_b,
        }

        with patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            mgr = StorageClientsManager(config)
            mgr.write_metrics([m])

        instance_a.write_metrics.assert_called_once_with([m])
        instance_b.write_metrics.assert_called_once_with([m])
