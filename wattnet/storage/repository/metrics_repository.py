from datetime import datetime
from typing import List, Optional

from wattnet.storage.clients.manager import StorageClientsManager
from wattnet.storage.models.metric import Metric
from wattnet.storage.processors import filter_best_metrics
from wattnet.storage.settings import settings
from wattnet.storage.utils import log

# Get logger
LOG = log.get(__name__)


class MetricsRepository:
    """
    Repository for storing and querying Metric objects in the storage backend.
    """

    def __init__(self):
        LOG.info("Initializing MetricsRepository...")
        self.storage_manager = StorageClientsManager()
        # Set step size in seconds
        self.step = int(settings.timeseries_step_minutes) * 60

    def query_metrics(
        self,
        metric_name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        labels: Optional[dict] = None,
    ) -> List[Metric]:
        """
        Query metrics from storage.

        :param metric_name: Name of the metric (MetricType.value)
        :param start: Start datetime
        :param end: End datetime
        :param labels: Optional labels to filter metrics
        :return: List of Metric objects
        """

        # Step 1: Query raw metrics
        query = f"{metric_name}{{"
        if labels:
            query += ",".join(f"{k}='{v}'" for k, v in labels.items())
        query += f"}}[{self.step}s]"

        metrics: List[Metric] = self.storage_manager.read_metrics(
            query=query, start=start, end=end
        )
        best_metrics = filter_best_metrics(metrics)
        return best_metrics

    def write_metrics(self, metrics: List[Metric]) -> None:
        """
        Write a list of Metric objects to the storage backend.

        :param metrics: List of Metric objects
        """
        if not metrics:
            return

        self.storage_manager.write_metrics(metrics)
