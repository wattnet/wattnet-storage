"""Metric domain model."""

from datetime import datetime

from wattnet.storage.models.metric_type import MetricType


class Metric:
    """Class representing a metric."""

    def __init__(
        self,
        metric_type: MetricType,
        value: float,
        timestamp: datetime | None = None,
        metadata: dict | None = None,
    ):
        """Initialize a Metric instance.

        :param metric_type: The type of metric
        :type metric_type: MetricType

        :param value: The value of the metric
        :type value: float

        :param metadata: Additional metadata for the metric
        :type metadata: dict
        """
        # If timestamp is None, set it to now
        if timestamp is None:
            timestamp = datetime.now()

        self.name = metric_type.value
        self.value = value
        self.timestamp = timestamp
        self.metadata = metadata or {}

    def __str__(self):
        """Return a human-readable string representation."""
        return f"{self.name}: {self.value} ({self.metadata}) at {self.timestamp}"

    def __repr__(self):
        """Return an unambiguous string representation."""
        return self.__str__()

    def add_metadata(self, key: str, value: str) -> None:
        """Add metadata to the metric.

        :param key: The key of the metadata
        :type key: str

        :param value: The value of the metadata
        :type value: str
        """
        self.metadata[key] = value

    def to_dict(self) -> dict:
        """Convert the metric to a dictionary.

        :return: The metric as a dictionary
        :rtype: dict
        """
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
