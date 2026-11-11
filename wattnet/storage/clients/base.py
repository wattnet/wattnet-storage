"""Abstract base class for storage clients."""

import typing
from abc import ABCMeta, abstractmethod
from datetime import datetime

from pydantic_settings import BaseSettings

from wattnet.storage.models import Metric, MetricSpec


class BaseStorageClient(metaclass=ABCMeta):
    """Base class for storage clients."""

    config_class: "typing.ClassVar[type[BaseSettings]]"

    @abstractmethod
    def read_metrics(
        self,
        metric_name: str,
        start: datetime | None = None,
        end: datetime | None = None,
        labels: dict | None = None,
        params: dict | None = None,
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

    # Not abstract, so a backend written before they existed keeps working.

    def register_metric(self, spec: MetricSpec) -> None:
        """Prepare the backend to store a metric declared by the application."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support declared metrics"
        )

    def ping(self) -> bool:
        """Return True if the backend answers."""
        raise NotImplementedError(f"{type(self).__name__} does not support ping")
