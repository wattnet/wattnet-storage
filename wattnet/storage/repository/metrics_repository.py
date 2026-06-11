"""High-level repository for reading and writing Metric objects."""

from datetime import datetime
from typing import List, Optional

from wattnet.storage.clients.manager import StorageClientsManager
from wattnet.storage.config import StorageConfig
from wattnet.storage.models.metric import Metric
from wattnet.storage.processors import filter_best_metrics
from wattnet.storage.utils import log

# Get logger
LOG = log.get(__name__)


class MetricsRepository:
    """Repository for storing and querying Metric objects in the storage backend."""

    def __init__(self, config: StorageConfig):
        """Initialize the MetricsRepository and connect to the storage backend."""
        LOG.info("Initializing MetricsRepository...")
        self.storage_manager = StorageClientsManager(config)
        self.step = config.timeseries_step_minutes * 60

    def query_metrics(
        self,
        metric_name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        labels: Optional[dict] = None,
    ) -> List[Metric]:
        """Query metrics from storage.

        :param metric_name: Name of the metric (MetricType.value)
        :param start: Start datetime
        :param end: End datetime
        :param labels: Optional labels to filter metrics
        :return: List of Metric objects
        """
        # Step 1: Query raw metrics
        metrics: List[Metric] = self.storage_manager.read_metrics(
            metric_name=metric_name,
            start=start,
            end=end,
            labels=labels,
        )
        best_metrics = filter_best_metrics(metrics)
        return best_metrics

    def write_metrics(self, metrics: List[Metric]) -> None:
        """Write a list of Metric objects to the storage backend.

        :param metrics: List of Metric objects
        """
        if not metrics:
            return

        self.storage_manager.write_metrics(metrics)
