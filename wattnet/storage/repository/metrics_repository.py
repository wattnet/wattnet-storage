"""High-level repository for reading and writing Metric objects."""

from datetime import datetime
from typing import List, Optional

from wattnet.storage.clients.manager import StorageClientsManager
from wattnet.storage.config import StorageConfig
from wattnet.storage.models import Metric, MetricSpec
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
        resolution_minutes: Optional[int] = None,
    ) -> List[Metric]:
        """Query metrics from storage.

        :param metric_name: Name of the metric (a MetricType value or a declared metric)
        :param start: Start datetime
        :param end: End datetime
        :param labels: Optional labels to filter metrics
        :param resolution_minutes: Optional bucket, in minutes, to get the series
            averaged instead of one metric per interval (a multiple of the interval of
            the series). Each bucket is one metric: its timestamp is the start of the
            bucket, its ``valid`` is true only if all its points are valid, its
            ``zone_status`` is the worst of them and its ``updated_at`` the latest.
            The best version of each point is chosen before averaging. By default the
            series comes as it is stored.
        :return: List of Metric objects
        """
        extra = {}
        if resolution_minutes is not None:
            extra["params"] = {"resolution_minutes": resolution_minutes}
        metrics: List[Metric] = self.storage_manager.read_metrics(
            metric_name=metric_name,
            start=start,
            end=end,
            labels=labels,
            **extra,
        )
        if resolution_minutes is not None:
            return metrics  # the query already chose the best version of each point
        return filter_best_metrics(metrics)

    def write_metrics(self, metrics: List[Metric]) -> None:
        """Write a list of Metric objects to the storage backend.

        :param metrics: List of Metric objects
        """
        if not metrics:
            return

        self.storage_manager.write_metrics(metrics)

    def register_metrics(self, *specs: MetricSpec) -> None:
        """Declare metrics that are not built-in, so they can be written and read.

        Call it once at start-up, before writing them. Their tables are created, and
        labels added to a spec later are added to the existing table.

        :param specs: MetricSpec objects
        """
        for spec in specs:
            self.storage_manager.register_metric(spec)

    def ping(self) -> bool:
        """Return True if every storage backend answers, for a health check."""
        return self.storage_manager.ping()
