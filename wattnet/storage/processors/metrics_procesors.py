"""Metric filtering and processing functions."""

from collections import defaultdict
from typing import Dict, List, Tuple

from wattnet.storage.models.metric import Metric
from wattnet.storage.utils import log

# Priority mapping for zone_status
ZONE_STATUS_PRIORITY = {"missing": 0, "preview": 1, "complete": 2}

# Get logger
LOG = log.get(__name__)


def filter_best_metrics(metrics: List[Metric]) -> List[Metric]:
    """Filter metrics, keeping the best version of each logical data point.

    For each logical metric point (timestamp + metric_type + labels except
    'valid' and 'zone_status'), keep only the best metric according to:
      1. valid=True preferred over valid=False
      2. zone_status priority: complete > preview > missing
    """
    LOG.debug(f"Filtering {len(metrics)} metrics to find the best ones")

    if not metrics:
        return []

    # Determine labels that are NOT changing (exclude valid and zone_status)
    all_keys = [set(m.metadata.keys()) for m in metrics]
    common_keys = set.intersection(*all_keys) - {"valid", "zone_status"}

    metrics_by_key: Dict[Tuple, List[Metric]] = defaultdict(list)
    for m in metrics:
        # key = timestamp + metric_type + labels that are "common"
        key = (m.timestamp, m.name) + tuple(
            m.metadata.get(k) for k in sorted(common_keys)
        )
        metrics_by_key[key].append(m)

    filtered_metrics = []
    for metric_list in metrics_by_key.values():
        # Prefer valid=True
        valid_true_metrics = [m for m in metric_list if m.metadata.get("valid") is True]
        candidates = valid_true_metrics if valid_true_metrics else metric_list

        # Pick highest zone_status priority
        max_priority = max(
            ZONE_STATUS_PRIORITY.get(m.metadata.get("zone_status", "missing"), 0)
            for m in candidates
        )
        best_metrics = [
            m
            for m in candidates
            if ZONE_STATUS_PRIORITY.get(m.metadata.get("zone_status", "missing"), 0)
            == max_priority
        ]

        # There must be 1 best metric
        filtered_metrics.extend(best_metrics)

    return filtered_metrics
