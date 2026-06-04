from datetime import datetime

from wattnet.storage.models.metric import Metric
from wattnet.storage.models.metric_type import MetricType
from wattnet.storage.processors.metrics_procesors import filter_best_metrics

TS = datetime(2024, 1, 1, 12, 0, 0)


def make_metric(value=1.0, valid=None, zone_status=None, zone="ES", ts=TS):
    m = Metric(MetricType.ZONE_GENERATION, value, timestamp=ts)
    m.add_metadata("zone", zone)
    if valid is not None:
        m.add_metadata("valid", valid)
    if zone_status is not None:
        m.add_metadata("zone_status", zone_status)
    return m


class TestFilterBestMetrics:
    # --- Basic cases ---

    def test_empty_input(self):
        assert filter_best_metrics([]) == []

    def test_single_metric_returned(self):
        m = make_metric()
        assert filter_best_metrics([m]) == [m]

    def test_returns_list(self):
        result = filter_best_metrics([make_metric()])
        assert isinstance(result, list)

    # --- valid flag priority ---

    def test_prefers_valid_true_over_false(self):
        valid = make_metric(value=10.0, valid=True, zone_status="complete")
        invalid = make_metric(value=20.0, valid=False, zone_status="complete")
        result = filter_best_metrics([valid, invalid])
        assert len(result) == 1
        assert result[0].value == 10.0

    def test_valid_true_beats_invalid_regardless_of_zone_status(self):
        valid_missing = make_metric(valid=True, zone_status="missing")
        invalid_complete = make_metric(valid=False, zone_status="complete")
        result = filter_best_metrics([valid_missing, invalid_complete])
        assert len(result) == 1
        assert result[0].metadata["valid"] is True

    def test_all_invalid_keeps_best_zone_status(self):
        preview = make_metric(valid=False, zone_status="preview")
        missing = make_metric(valid=False, zone_status="missing")
        result = filter_best_metrics([preview, missing])
        assert len(result) == 1
        assert result[0].metadata["zone_status"] == "preview"

    # --- zone_status priority ---

    def test_complete_beats_preview(self):
        complete = make_metric(valid=True, zone_status="complete")
        preview = make_metric(valid=True, zone_status="preview")
        result = filter_best_metrics([complete, preview])
        assert len(result) == 1
        assert result[0].metadata["zone_status"] == "complete"

    def test_preview_beats_missing(self):
        preview = make_metric(valid=True, zone_status="preview")
        missing = make_metric(valid=True, zone_status="missing")
        result = filter_best_metrics([preview, missing])
        assert len(result) == 1
        assert result[0].metadata["zone_status"] == "preview"

    def test_complete_beats_missing(self):
        complete = make_metric(valid=True, zone_status="complete")
        missing = make_metric(valid=True, zone_status="missing")
        result = filter_best_metrics([complete, missing])
        assert len(result) == 1
        assert result[0].metadata["zone_status"] == "complete"

    def test_missing_zone_status_treated_as_lowest_priority(self):
        no_status = make_metric(valid=True)
        with_complete = make_metric(valid=True, zone_status="complete")
        result = filter_best_metrics([no_status, with_complete])
        assert len(result) == 1
        assert result[0].metadata.get("zone_status") == "complete"

    def test_unknown_zone_status_treated_as_missing_priority(self):
        unknown_status = make_metric(valid=True, zone_status="other")
        with_preview = make_metric(valid=True, zone_status="preview")
        result = filter_best_metrics([unknown_status, with_preview])
        assert len(result) == 1
        assert result[0].metadata["zone_status"] == "preview"

    # --- Key grouping ---

    def test_different_timestamps_produce_separate_groups(self):
        ts1 = datetime(2024, 1, 1, 12, 0, 0)
        ts2 = datetime(2024, 1, 1, 13, 0, 0)
        m1 = make_metric(valid=True, zone_status="complete", ts=ts1)
        m2 = make_metric(valid=True, zone_status="complete", ts=ts2)
        assert len(filter_best_metrics([m1, m2])) == 2

    def test_different_zones_produce_separate_groups(self):
        es = make_metric(valid=True, zone_status="complete", zone="ES")
        fr = make_metric(valid=True, zone_status="complete", zone="FR")
        assert len(filter_best_metrics([es, fr])) == 2

    def test_same_key_collapses_to_one_per_group(self):
        metrics = [
            make_metric(value=float(i), valid=True, zone_status="complete")
            for i in range(5)
        ]
        result = filter_best_metrics(metrics)
        assert len(result) == 5  # all tied: same zone, timestamp, and priority

    def test_ties_in_priority_keep_all(self):
        m1 = make_metric(value=1.0, valid=True, zone_status="complete")
        m2 = make_metric(value=2.0, valid=True, zone_status="complete")
        assert len(filter_best_metrics([m1, m2])) == 2

    # --- Metrics without valid/zone_status keys ---

    def test_no_valid_or_zone_status_keys_returns_metric(self):
        m = Metric(MetricType.ZONE_GENERATION, 5.0, timestamp=TS)
        result = filter_best_metrics([m])
        assert result == [m]

    def test_metrics_without_any_metadata_grouped_by_timestamp_and_name(self):
        ts1 = datetime(2024, 1, 1, 12, 0, 0)
        ts2 = datetime(2024, 1, 1, 13, 0, 0)
        m1 = Metric(MetricType.ZONE_GENERATION, 1.0, timestamp=ts1)
        m2 = Metric(MetricType.ZONE_GENERATION, 2.0, timestamp=ts2)
        assert len(filter_best_metrics([m1, m2])) == 2

    # --- Multi-zone × multi-timestamp batch ---

    def test_large_batch_correct_count(self):
        zones = ["ES", "FR", "DE", "IT"]
        timestamps = [datetime(2024, 1, 1, h, 0, 0) for h in range(6)]
        metrics = []
        for z in zones:
            for ts in timestamps:
                metrics.append(
                    make_metric(valid=True, zone_status="complete", zone=z, ts=ts)
                )
                metrics.append(
                    make_metric(valid=False, zone_status="preview", zone=z, ts=ts)
                )
        result = filter_best_metrics(metrics)
        # 4 zones × 6 timestamps = 24 groups, one winner each
        assert len(result) == 24

    def test_large_batch_all_winners_are_valid(self):
        zones = ["ES", "FR"]
        timestamps = [datetime(2024, 1, 1, h, 0, 0) for h in range(4)]
        metrics = []
        for z in zones:
            for ts in timestamps:
                metrics.append(
                    make_metric(valid=True, zone_status="complete", zone=z, ts=ts)
                )
                metrics.append(
                    make_metric(valid=False, zone_status="complete", zone=z, ts=ts)
                )
        result = filter_best_metrics(metrics)
        assert all(m.metadata["valid"] is True for m in result)
