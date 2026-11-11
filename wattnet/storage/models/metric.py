"""Metric domain model."""

from datetime import datetime

from wattnet.storage.models.metric_type import MetricType


class Metric:
    """Class representing a metric."""

    def __init__(
        self,
        metric_type: MetricType | str,
        value: float,
        timestamp: datetime | None = None,
        metadata: dict | None = None,
        updated_at: datetime | None = None,
    ):
        """Initialize a Metric instance.

        :param metric_type: The type of metric: a built-in MetricType or the name of a
            metric declared with a MetricSpec
        :type metric_type: MetricType | str

        :param value: The value of the metric
        :type value: float

        :param metadata: Additional metadata for the metric
        :type metadata: dict

        :param updated_at: When Wattnet stored this version of the value (UTC). It is
            set on metrics read from storage and ignored on write, where the time of
            the write is used.
        :type updated_at: datetime, optional
        """
        # If timestamp is None, set it to now
        if timestamp is None:
            timestamp = datetime.now()

        self.name = (
            metric_type.value if isinstance(metric_type, MetricType) else metric_type
        )
        self.value = value
        self.timestamp = timestamp
        self.metadata = metadata or {}
        self.updated_at = updated_at

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
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
