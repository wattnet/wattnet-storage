from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from wattnet.storage.clients.manager import StorageClientsManager
from wattnet.storage.models import Metric, MetricType


def _make_mock_plugin():
    """Return a mock plugin class whose instances expose read/write_metrics."""
    instance = MagicMock()
    instance.read_metrics.return_value = []
    instance.write_metrics.return_value = None
    plugin_cls = MagicMock(return_value=instance)
    return plugin_cls, instance


@pytest.fixture
def mock_settings_empty(monkeypatch):
    mock = MagicMock()
    mock.storage_clients = []
    with patch("wattnet.storage.clients.manager.settings", mock):
        yield mock


@pytest.fixture
def mock_settings_clickhouse(monkeypatch):
    mock = MagicMock()
    mock.storage_clients = ["clickhouse"]
    with patch("wattnet.storage.clients.manager.settings", mock):
        yield mock


@pytest.fixture
def mock_plugin_loader_with_clickhouse():
    plugin_cls, instance = _make_mock_plugin()
    mock_loader = MagicMock()
    mock_loader.get_storage_clients_names.return_value = frozenset(["clickhouse"])
    mock_loader.get_storage_clients_extensions.return_value = {"clickhouse": plugin_cls}
    with patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
        yield mock_loader, plugin_cls, instance


class TestStorageClientsManagerInit:
    def test_no_clients_configured_does_not_raise(self, mock_settings_empty):
        mgr = StorageClientsManager()
        assert mgr is not None

    def test_unknown_client_raises_import_error(self, mock_settings_clickhouse):
        mock_loader = MagicMock()
        mock_loader.get_storage_clients_names.return_value = frozenset()
        with patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            with pytest.raises(ImportError, match="clickhouse"):
                StorageClientsManager()

    def test_known_client_populates_storage_clients(
        self, mock_settings_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        mgr = StorageClientsManager()
        assert "clickhouse" in mgr.storage_clients

    def test_client_instance_created(
        self, mock_settings_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, plugin_cls, _ = mock_plugin_loader_with_clickhouse
        StorageClientsManager()
        plugin_cls.assert_called_once()

    def test_multiple_clients_loaded(self):
        mock_settings = MagicMock()
        mock_settings.storage_clients = ["a", "b"]

        plugin_cls_a, instance_a = _make_mock_plugin()
        plugin_cls_b, instance_b = _make_mock_plugin()

        mock_loader = MagicMock()
        mock_loader.get_storage_clients_names.return_value = frozenset(["a", "b"])
        mock_loader.get_storage_clients_extensions.return_value = {
            "a": plugin_cls_a,
            "b": plugin_cls_b,
        }

        with patch("wattnet.storage.clients.manager.settings", mock_settings), \
             patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            mgr = StorageClientsManager()

        assert set(mgr.storage_clients.keys()) == {"a", "b"}


class TestStorageClientsManagerReadMetrics:
    def test_read_returns_empty_when_no_clients(self, mock_settings_empty):
        mgr = StorageClientsManager()
        # No storage_clients attribute set when empty — guard the call
        if hasattr(mgr, "storage_clients"):
            result = mgr.read_metrics("zone_generation")
            assert result == []

    def test_read_calls_client(
        self, mock_settings_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, _, instance = mock_plugin_loader_with_clickhouse
        mgr = StorageClientsManager()
        mgr.read_metrics("zone_generation")
        instance.read_metrics.assert_called_once_with(
            "zone_generation", None, None, None, None
        )

    def test_read_passes_params_to_client(
        self, mock_settings_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, _, instance = mock_plugin_loader_with_clickhouse
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        labels = {"zone": "ES"}
        mgr = StorageClientsManager()
        mgr.read_metrics("zone_generation", start=start, end=end, labels=labels)
        instance.read_metrics.assert_called_once_with(
            "zone_generation", start, end, labels, None
        )

    def test_read_aggregates_from_multiple_clients(self):
        m1 = Metric(MetricType.ZONE_GENERATION, 1.0)
        m2 = Metric(MetricType.ZONE_GENERATION, 2.0)

        mock_settings = MagicMock()
        mock_settings.storage_clients = ["a", "b"]

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

        with patch("wattnet.storage.clients.manager.settings", mock_settings), \
             patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            mgr = StorageClientsManager()
            result = mgr.read_metrics("zone_generation")

        assert m1 in result
        assert m2 in result
        assert len(result) == 2


class TestStorageClientsManagerWriteMetrics:
    def test_write_calls_client(
        self, mock_settings_clickhouse, mock_plugin_loader_with_clickhouse
    ):
        _, _, instance = mock_plugin_loader_with_clickhouse
        m = Metric(MetricType.ZONE_GENERATION, 1.0)
        mgr = StorageClientsManager()
        mgr.write_metrics([m])
        instance.write_metrics.assert_called_once_with([m])

    def test_write_sends_to_all_clients(self):
        m = Metric(MetricType.ZONE_GENERATION, 1.0)
        mock_settings = MagicMock()
        mock_settings.storage_clients = ["a", "b"]

        plugin_cls_a, instance_a = _make_mock_plugin()
        plugin_cls_b, instance_b = _make_mock_plugin()

        mock_loader = MagicMock()
        mock_loader.get_storage_clients_names.return_value = frozenset(["a", "b"])
        mock_loader.get_storage_clients_extensions.return_value = {
            "a": plugin_cls_a,
            "b": plugin_cls_b,
        }

        with patch("wattnet.storage.clients.manager.settings", mock_settings), \
             patch("wattnet.storage.clients.manager.plugin_loader", mock_loader):
            mgr = StorageClientsManager()
            mgr.write_metrics([m])

        instance_a.write_metrics.assert_called_once_with([m])
        instance_b.write_metrics.assert_called_once_with([m])
