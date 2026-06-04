import pytest

from wattnet.storage.models.metric import Metric
from wattnet.storage.models.metric_type import MetricType


@pytest.fixture
def sample_metric():
    return Metric(metric_type=MetricType.ZONE_GENERATION, value=42.5)
