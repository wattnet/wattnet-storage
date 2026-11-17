from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from wattnet.storage.config import StorageConfig
from wattnet.storage.models import Metric, MetricType
from wattnet.storage.repository import MetricsRepository


@pytest.fixture
def mock_manager():
    with patch(
        "wattnet.storage.repository.metrics_repository.StorageClientsManager"
    ) as MockManager:
        manager = MagicMock()
        MockManager.return_value = manager
        yield manager


@pytest.fixture
def config():
    return StorageConfig(storage_clients=[])


@pytest.fixture
def repo(mock_manager, config):
    return MetricsRepository(config)


class TestMetricsRepositoryInit:
    def test_creates_storage_manager(self, mock_manager, config):
        r = MetricsRepository(config)
        assert r.storage_manager is mock_manager

    def test_step_derived_from_config(self, mock_manager):
        cfg = StorageConfig(timeseries_step_minutes=30)
        r = MetricsRepository(cfg)
        assert r.step == 30 * 60

    def test_step_default_is_15_minutes(self, mock_manager, config):
        r = MetricsRepository(config)
        assert r.step == 15 * 60


TS = datetime(2024, 1, 1, tzinfo=timezone.utc)


class TestQueryMetrics:
    def test_returns_list(self, repo, mock_manager):
        mock_manager.read_metrics.return_value = []
        assert isinstance(repo.query_metrics("zone_generation"), list)

    def test_delegates_to_storage_manager_with_all_args(self, repo, mock_manager):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        mock_manager.read_metrics.return_value = []
        repo.query_metrics(
            "zone_generation", start=start, end=end, labels={"zone": "ES"}
        )
        mock_manager.read_metrics.assert_called_once_with(
            metric_name="zone_generation",
            start=start,
            end=end,
            labels={"zone": "ES"},
        )

    def test_resolution_is_passed_on_and_the_series_is_not_filtered_again(
        self, repo, mock_manager
    ):
        """The query of a resampled series has already chosen what to keep."""
        rows = [
            Metric(
                MetricType.ZONE_LOAD, 1.0, timestamp=TS, metadata={"valid": "false"}
            ),
            Metric(MetricType.ZONE_LOAD, 2.0, timestamp=TS, metadata={"valid": "true"}),
        ]
        mock_manager.read_metrics.return_value = rows
        result = repo.query_metrics("zone_load", resolution_minutes=60)
        assert result == rows
        mock_manager.read_metrics.assert_called_once_with(
            metric_name="zone_load",
            start=None,
            end=None,
            labels=None,
            params={"resolution_minutes": 60},
        )

    def test_min_value_is_passed_on_with_or_without_a_resolution(
        self, repo, mock_manager
    ):
        """The bound travels in the params, alone or with the resolution."""
        mock_manager.read_metrics.return_value = []
        repo.query_metrics("zone_load", min_value=0)
        assert mock_manager.read_metrics.call_args.kwargs["params"] == {"min_value": 0}
        repo.query_metrics("zone_load", resolution_minutes=60, min_value=0)
        assert mock_manager.read_metrics.call_args.kwargs["params"] == {
            "resolution_minutes": 60,
            "min_value": 0,
        }

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
