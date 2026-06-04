from unittest.mock import MagicMock, patch

from wattnet.storage.utils.plugin_loader import (
    STORAGE_CLIENTS_NAMESPACE,
    _get_extensions,
    _get_names,
    get_storage_clients_extensions,
    get_storage_clients_names,
)


class TestConstants:
    def test_storage_clients_namespace(self):
        assert STORAGE_CLIENTS_NAMESPACE == "wattnet.storage.clients"


class TestGetNames:
    def _make_mgr(self, names):
        mgr = MagicMock()
        mgr.names.return_value = names
        return mgr

    def test_returns_frozenset(self):
        with patch(
            "stevedore.ExtensionManager", return_value=self._make_mgr(["clickhouse"])
        ):
            result = _get_names("some.namespace")
        assert isinstance(result, frozenset)

    def test_contains_returned_names(self):
        with patch(
            "stevedore.ExtensionManager", return_value=self._make_mgr(["a", "b"])
        ):
            result = _get_names("ns")
        assert result == frozenset(["a", "b"])

    def test_empty_namespace_returns_empty_frozenset(self):
        with patch("stevedore.ExtensionManager", return_value=self._make_mgr([])):
            result = _get_names("empty.ns")
        assert result == frozenset()

    def test_called_with_correct_namespace(self):
        with patch("stevedore.ExtensionManager") as mock_mgr_cls:
            mock_mgr_cls.return_value = self._make_mgr([])
            _get_names("my.namespace")
        mock_mgr_cls.assert_called_once_with(namespace="my.namespace")


class TestGetExtensions:
    def _make_mgr(self, items):
        """items: list of (name, plugin) tuples returned by map()"""
        mgr = MagicMock()
        mgr.map.return_value = items
        return mgr

    def test_returns_dict(self):
        with patch(
            "stevedore.ExtensionManager", return_value=self._make_mgr([("ch", object)])
        ):
            result = _get_extensions("ns")
        assert isinstance(result, dict)

    def test_contains_extensions(self):
        class FakePlugin:
            pass

        with patch(
            "stevedore.ExtensionManager",
            return_value=self._make_mgr([("clickhouse", FakePlugin)]),
        ):
            result = _get_extensions("ns")
        assert "clickhouse" in result
        assert result["clickhouse"] is FakePlugin

    def test_empty_returns_empty_dict(self):
        with patch("stevedore.ExtensionManager", return_value=self._make_mgr([])):
            result = _get_extensions("ns")
        assert result == {}

    def test_called_with_correct_namespace(self):
        with patch("stevedore.ExtensionManager") as mock_mgr_cls:
            mock_mgr_cls.return_value = self._make_mgr([])
            _get_extensions("my.namespace")
        mock_mgr_cls.assert_called_once_with(
            namespace="my.namespace", propagate_map_exceptions=True
        )


class TestPublicAPI:
    def test_get_storage_clients_names_uses_correct_namespace(self):
        mgr = MagicMock()
        mgr.names.return_value = []
        with patch("stevedore.ExtensionManager") as mock_mgr_cls:
            mock_mgr_cls.return_value = mgr
            get_storage_clients_names()
        mock_mgr_cls.assert_called_with(namespace=STORAGE_CLIENTS_NAMESPACE)

    def test_get_storage_clients_extensions_uses_correct_namespace(self):
        mgr = MagicMock()
        mgr.map.return_value = []
        with patch("stevedore.ExtensionManager") as mock_mgr_cls:
            mock_mgr_cls.return_value = mgr
            get_storage_clients_extensions()
        mock_mgr_cls.assert_called_with(
            namespace=STORAGE_CLIENTS_NAMESPACE, propagate_map_exceptions=True
        )

    def test_clickhouse_is_registered(self):
        # Real check: the package declares the clickhouse entry point
        names = get_storage_clients_names()
        assert "clickhouse" in names
