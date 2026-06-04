from datetime import datetime

import pytest

from wattnet.storage.models import Metric, MetricType
from wattnet.storage.models.metric import Metric as MetricDirect
from wattnet.storage.models.metric_type import MetricType as MetricTypeDirect


class TestMetricType:
    def test_values_are_strings(self):
        assert MetricType.ZONE_GENERATION == "zone_generation"

    def test_is_string_enum(self):
        assert isinstance(MetricType.FACTOR, str)

    def test_all_values_are_lowercase(self):
        for mt in MetricType:
            assert mt.value == mt.value.lower()

    def test_all_values_are_unique(self):
        values = [mt.value for mt in MetricType]
        assert len(values) == len(set(values))

    def test_can_construct_from_string(self):
        assert MetricType("zone_generation") is MetricType.ZONE_GENERATION

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            MetricType("not_a_real_metric")

    def test_unknown_member_exists(self):
        assert MetricType.UNKNOWN == "unknown"

    def test_all_expected_members_present(self):
        expected = {
            "zone_generation", "zone_import", "zone_export", "zone_load",
            "zone_mix_generation", "factor", "local_footprint", "global_footprint",
            "local_impact", "global_impact", "local_score", "global_score",
            "flow_share", "mix_share", "footprint_share", "impact_share", "unknown",
        }
        assert {mt.value for mt in MetricType} == expected

    def test_usable_in_set(self):
        s = {MetricType.ZONE_GENERATION, MetricType.FACTOR}
        assert MetricType.ZONE_GENERATION in s

    def test_top_level_import_is_same_class(self):
        assert MetricType is MetricTypeDirect


class TestMetric:
    def test_creation_basic(self, sample_metric):
        assert sample_metric.name == "zone_generation"
        assert sample_metric.value == 42.5
        assert isinstance(sample_metric.timestamp, datetime)
        assert sample_metric.metadata == {}

    def test_default_timestamp_is_recent(self):
        before = datetime.now()
        m = Metric(MetricType.FACTOR, 1.0)
        after = datetime.now()
        assert before <= m.timestamp <= after

    def test_explicit_timestamp_preserved(self):
        ts = datetime(2024, 6, 1, 12, 0, 0)
        m = Metric(MetricType.FACTOR, 1.0, timestamp=ts)
        assert m.timestamp == ts

    def test_name_comes_from_metric_type_value(self):
        for mt in MetricType:
            m = Metric(mt, 0.0)
            assert m.name == mt.value

    def test_float_value(self):
        m = Metric(MetricType.FACTOR, 3.14159)
        assert m.value == 3.14159

    def test_integer_value_accepted(self):
        m = Metric(MetricType.FACTOR, 42)
        assert m.value == 42

    def test_negative_value_accepted(self):
        m = Metric(MetricType.FACTOR, -99.9)
        assert m.value == -99.9

    def test_zero_value_accepted(self):
        m = Metric(MetricType.FACTOR, 0.0)
        assert m.value == 0.0

    def test_metadata_defaults_to_empty_dict(self):
        m = Metric(MetricType.FACTOR, 1.0)
        assert m.metadata == {}

    def test_explicit_none_metadata_becomes_empty_dict(self):
        m = Metric(MetricType.FACTOR, 1.0, metadata=None)
        assert m.metadata == {}

    def test_explicit_metadata_preserved(self):
        meta = {"zone": "ES", "unit": "MW"}
        m = Metric(MetricType.FACTOR, 1.0, metadata=meta)
        assert m.metadata == meta

    def test_metadata_is_not_shared_between_instances(self):
        m1 = Metric(MetricType.FACTOR, 1.0)
        m2 = Metric(MetricType.FACTOR, 2.0)
        m1.add_metadata("key", "val")
        assert "key" not in m2.metadata

    def test_add_metadata_single(self, sample_metric):
        sample_metric.add_metadata("zone", "ES")
        assert sample_metric.metadata["zone"] == "ES"

    def test_add_metadata_multiple(self, sample_metric):
        sample_metric.add_metadata("zone", "ES")
        sample_metric.add_metadata("unit", "MW")
        assert sample_metric.metadata == {"zone": "ES", "unit": "MW"}

    def test_add_metadata_overwrites_existing_key(self, sample_metric):
        sample_metric.add_metadata("zone", "ES")
        sample_metric.add_metadata("zone", "FR")
        assert sample_metric.metadata["zone"] == "FR"

    def test_to_dict_keys(self, sample_metric):
        assert set(sample_metric.to_dict().keys()) == {"name", "value", "timestamp", "metadata"}

    def test_to_dict_name(self, sample_metric):
        assert sample_metric.to_dict()["name"] == "zone_generation"

    def test_to_dict_value(self, sample_metric):
        assert sample_metric.to_dict()["value"] == 42.5

    def test_to_dict_timestamp_is_iso_string(self, sample_metric):
        ts_str = sample_metric.to_dict()["timestamp"]
        assert isinstance(ts_str, str)
        datetime.fromisoformat(ts_str)  # must parse without error

    def test_to_dict_timestamp_roundtrip(self):
        ts = datetime(2024, 6, 1, 12, 30, 0)
        m = Metric(MetricType.FACTOR, 1.0, timestamp=ts)
        parsed = datetime.fromisoformat(m.to_dict()["timestamp"])
        assert parsed == ts

    def test_to_dict_metadata(self):
        m = Metric(MetricType.FACTOR, 1.0, metadata={"zone": "ES"})
        assert m.to_dict()["metadata"] == {"zone": "ES"}

    def test_str_contains_name(self, sample_metric):
        assert "zone_generation" in str(sample_metric)

    def test_str_contains_value(self, sample_metric):
        assert "42.5" in str(sample_metric)

    def test_repr_equals_str(self, sample_metric):
        assert repr(sample_metric) == str(sample_metric)

    def test_top_level_import_is_same_class(self):
        assert Metric is MetricDirect
