import datetime
from abc import ABCMeta, abstractmethod

from wattnet.storage.models import Metric


class BaseStorageClient(metaclass=ABCMeta):
    """Base class for storage clients."""

    @abstractmethod
    def read_metrics(self, query: str, start: datetime, end: datetime) -> list[Metric]:
        """Read metrics from the storage backend.

        :param query: The query to read metrics
        :type query: str
        :param start: The start datetime
        :type start: datetime
        :param end: The end datetime
        :type end: datetime

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
