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
        min_value: Optional[float] = None,
    ) -> List[Metric]:
        """Query metrics from storage.

        :param metric_name: Name of the metric (a MetricType value or a declared metric)
        :param start: Start datetime
        :param end: End datetime
        :param labels: Optional labels to filter metrics
        :param resolution_minutes: Optional bucket, in minutes, to get the series
            averaged instead of one metric per interval (a multiple of the interval of
            the series). Each bucket is one metric, and the buckets follow the UTC
            calendar (hours and days in UTC), so the first and the last may have fewer
            points than the others. Its timestamp is the start of the bucket, its
            ``valid`` is true only if all its points are valid, its ``zone_status`` is
            the worst of them and its ``updated_at`` the latest. The best version of
            each point is chosen before averaging. By default the series comes as it
            is stored.
        :param min_value: Optional lower bound: the values below it are left out. With
            a resolution they are left out before the average, so it is the average of
            the values that stay.
        :return: List of Metric objects
        """
        query_params = {
            name: value
            for name, value in (
                ("resolution_minutes", resolution_minutes),
                ("min_value", min_value),
            )
            if value is not None
        }
        extra = {"params": query_params} if query_params else {}
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

    def latest_timestamp(
        self,
        metric_name: str,
        before: datetime,
        labels: Optional[dict] = None,
        after: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """Return the timestamp of the latest point of a series before a moment.

        It answers with one query, so a reader can find where the data of a series
        stops (for example, the last official point before a gap) without reading
        the series back window after window.

        :param metric_name: Name of the metric (a MetricType value or a declared metric)
        :param before: Only points strictly before this moment count
        :param labels: Optional labels to filter the points (any column of the table,
            for example ``{"zone": "ES", "data_state": "official"}``)
        :param after: Optional lower bound of the search, to keep it to a range
        :return: The timestamp (UTC), or None if the series has no point in the range
        """
        return self.storage_manager.latest_timestamp(metric_name, before, labels, after)

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
