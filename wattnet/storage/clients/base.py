import datetime
from abc import ABCMeta, abstractmethod

from wattnet.storage.models import Metric


class BaseStorageClient(metaclass=ABCMeta):
    """Base class for storage clients."""

    @abstractmethod
    def read_metrics(
        self,
        metric_name: str,
        start: datetime = None,
        end: datetime = None,
        labels: dict = None,
        params: dict = None,
    ) -> list[Metric]:
        """Read metrics from the storage backend.

        :param metric_name: The name of the metric to read
        :type metric_name: str
        :param start: The start datetime for the query
        :type start: datetime, optional
        :param end: The end datetime for the query
        :type end: datetime, optional
        :param labels: Optional labels to filter the metrics
        :type labels: dict, optional
        :param params: Additional query parameters
        :type params: dict, optional

        :return: The list of metrics read from the storage backend
        :rtype: list[Metric]
        """
        pass

    @abstractmethod
    def write_metrics(self, metrics: list[Metric]) -> None:
        """Write metrics to the storage backend.

        :param metrics: The list of metrics to write
        :type metrics: list[Metric]
        """
        pass
