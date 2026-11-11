"""Domain models for wattnet storage."""

from .metric import Metric, MetricType
from .metric_spec import MetricSpec

__all__ = ["Metric", "MetricSpec", "MetricType"]
