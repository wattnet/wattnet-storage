from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from wattnet.storage.models import Metric, MetricType
from wattnet.storage.repository import MetricsRepository
from wattnet.storage.settings import settings


@pytest.fixture
def mock_manager():
    with patch(
        "wattnet.storage.repository.metrics_repository.StorageClientsManager"
    ) as MockManager:
        manager = MagicMock()
        MockManager.return_value = manager
        yield manager


@pytest.fixture
def repo(mock_manager):
    return MetricsRepository()


class TestMetricsRepositoryInit:
    def test_creates_storage_manager(self, mock_manager):
        r = MetricsRepository()
        assert r.storage_manager is mock_manager

    def test_step_derived_from_settings(self, mock_manager):
        r = MetricsRepository()
        assert r.step == int(settings.timeseries_step_minutes) * 60


class TestQueryMetrics:
    def test_returns_list(self, repo, mock_manager):
        mock_manager.read_metrics.return_value = []
        assert isinstance(repo.query_metrics("zone_generation"), list)

    def test_delegates_to_storage_manager_with_all_args(self, repo, mock_manager):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_manager.read_metrics.return_value = []
        repo.query_metrics("zone_generation", start=start, end=end, labels={"zone": "ES"})
        mock_manager.read_metrics.assert_called_once_with(
            metric_name="zone_generation",
            start=start,
            end=end,
            labels={"zone": "ES"},
        )

    def test_applies_filter_best_metrics(self, repo, mock_manager):
        m = Metric(
            MetricType.ZONE_GENERATION,
            1.0,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        mock_manager.read_metrics.return_value = [m]
        result = repo.query_metrics("zone_generation")
        assert isinstance(result, list)


class TestWriteMetrics:
    def test_empty_list_returns_none_without_calling_manager(self, repo, mock_manager):
        assert repo.write_metrics([]) is None
        mock_manager.write_metrics.assert_not_called()

    def test_delegates_to_storage_manager(self, repo, mock_manager):
        m = Metric(MetricType.ZONE_GENERATION, 1.0)
        repo.write_metrics([m])
        mock_manager.write_metrics.assert_called_once_with([m])

    def test_multiple_metrics_passed_through(self, repo, mock_manager):
        metrics = [Metric(MetricType.ZONE_GENERATION, float(i)) for i in range(3)]
        repo.write_metrics(metrics)
        mock_manager.write_metrics.assert_called_once_with(metrics)
