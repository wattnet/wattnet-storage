"""Metric filtering and processing functions."""

from typing import Dict, List, Tuple

from wattnet.storage.models.metric import Metric
from wattnet.storage.utils import log

# Priority mapping for zone_status
ZONE_STATUS_PRIORITY = {"missing": 0, "preview": 1, "complete": 2}

# Get logger
LOG = log.get(__name__)


def _is_valid(metric: Metric) -> bool:
    """Return True if the label valid is true (a bool when written, text when read)."""
    return str(metric.metadata.get("valid")).lower() == "true"


def filter_best_metrics(metrics: List[Metric]) -> List[Metric]:
    """Filter metrics, keeping the best version of each logical data point.

    For each logical metric point (timestamp + metric_type + labels except
    'valid' and 'zone_status'), keep only the best metric according to:
      1. valid=True preferred over valid=False
      2. zone_status priority: complete > preview > missing

    Note: depending on the storage backend, this deduplication may already be
    enforced at the database level via update policies (e.g. ReplacingMergeTree
    in ClickHouse). This layer exists as a safety net regardless, since relying
    on backend-specific behaviour would couple the repository logic to a
    particular storage implementation.
    """
    LOG.debug(f"Filtering {len(metrics)} metrics to find the best ones")

    if not metrics:
        return []

    # Determine labels that are NOT changing (exclude valid and zone_status). The
    # intersection is kept in one set: a set for each metric is hundreds of MiB for
    # a year of data.
    common = set(metrics[0].metadata)
    for m in metrics:
        common.intersection_update(m.metadata)
    common_keys = sorted(common - {"valid", "zone_status"})

    # One pass, and for each logical point only the best of the metrics seen so far:
    # valid=True first, then the priority of zone_status. The ones that tie are all
    # kept, in the order they came. A point is a list [rank, metric, ...].
    best: Dict[Tuple, list] = {}
    for m in metrics:
        # key = timestamp + metric_type + labels that are "common"
        key = (m.timestamp, m.name) + tuple(m.metadata.get(k) for k in common_keys)
        rank = (
            _is_valid(m),
            ZONE_STATUS_PRIORITY.get(m.metadata.get("zone_status", "missing"), 0),
        )
        point = best.get(key)
        if point is None:
            best[key] = [rank, m]
        elif rank > point[0]:
            best[key] = [rank, m]
        elif rank == point[0]:
            point.append(m)

    filtered_metrics: List[Metric] = []
    for point in best.values():
        filtered_metrics.extend(point[1:])
    return filtered_metrics
