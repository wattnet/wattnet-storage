"""Integration tests of the resampled reads (``resolution_minutes``).

Requires the ClickHouse of ``docker-compose.test.yml`` (see conftest.py).
"""

from datetime import datetime, timedelta, timezone

import pytest

from wattnet.storage.models import Metric, MetricType

T0 = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)


def _load(minutes: int, value: float, **labels) -> Metric:
    meta = {
        "zone": "ES",
        "unit": "MW",
        "data_state": "official",
        "datasource": "ENTSO-E",
        "valid": "true",
        "zone_status": "complete",
    }
    meta.update(labels)
    return Metric(
        MetricType.ZONE_LOAD, value, T0 + timedelta(minutes=minutes), metadata=meta
    )


def _write(ch_client, metrics) -> None:
    ch_client.write_metrics(metrics)
    ch_client._flush_all()


def _read(ch_client, resolution, start=T0, end=T0 + timedelta(hours=2), **extra):
    params = {"resolution_minutes": resolution} if resolution else None
    return ch_client.read_metrics(
        "zone_load", start, end, {"zone": "ES"}, params=params, **extra
    )


def test_a_bucket_is_the_average_of_its_points(ch_client) -> None:
    """Eight points of 15 minutes make two hours of averages."""
    _write(ch_client, [_load(15 * i, float(10 * (i + 1))) for i in range(8)])
    out = _read(ch_client, 60)
    assert [(m.timestamp, m.value) for m in out] == [
        (T0, 25.0),
        (T0 + timedelta(hours=1), 65.0),
    ]
    assert out[0].metadata["valid"] == "true"
    assert out[0].metadata["zone_status"] == "complete"
    assert out[0].metadata["datasource"] == "ENTSO-E"
    assert out[0].updated_at is not None


def test_the_resolution_of_the_series_gives_the_same_series(ch_client) -> None:
    """With the interval of the series nothing is averaged."""
    _write(ch_client, [_load(15 * i, float(i)) for i in range(8)])
    raw = _read(ch_client, None)
    same = _read(ch_client, 15)
    assert [(m.timestamp, m.value) for m in same] == [
        (m.timestamp, m.value) for m in raw
    ]


def test_a_bucket_is_valid_only_if_all_its_points_are_and_has_the_worst_status(
    ch_client,
) -> None:
    """One point that is not valid or complete marks its bucket."""
    _write(
        ch_client,
        [
            _load(0, 10.0),
            _load(15, 20.0, valid="false", zone_status="preview"),
            _load(30, 30.0),
            _load(45, 40.0),
            _load(60, 50.0),
            _load(75, 60.0),
            _load(90, 70.0),
            _load(105, 80.0, zone_status="missing"),
        ],
    )
    first, second = _read(ch_client, 60)
    assert (first.metadata["valid"], first.metadata["zone_status"]) == (
        "false",
        "preview",
    )
    assert (second.metadata["valid"], second.metadata["zone_status"]) == (
        "true",
        "missing",
    )


def test_series_with_other_labels_stay_apart(ch_client) -> None:
    """A datasource or a data state is its own series, as it is unaveraged."""
    _write(
        ch_client,
        [
            _load(0, 10.0),
            _load(15, 30.0),
            _load(30, 90.0, datasource="REE"),
            _load(45, 110.0, datasource="REE"),
        ],
    )
    out = _read(ch_client, 60, end=T0 + timedelta(hours=1))
    assert {(m.metadata["datasource"], m.value) for m in out} == {
        ("ENTSO-E", 20.0),
        ("REE", 100.0),
    }


def test_the_buckets_follow_the_utc_calendar_whatever_the_start(ch_client) -> None:
    """A query that starts at 00:30 has the buckets of 00:00 and 01:00."""
    _write(ch_client, [_load(15 * i, float(i)) for i in range(8)])
    out = _read(
        ch_client, 60, start=T0 + timedelta(minutes=30), end=T0 + timedelta(hours=2)
    )
    assert [(m.timestamp, m.value) for m in out] == [
        (T0, 2.5),  # only 00:30 and 00:45 are in the range
        (T0 + timedelta(hours=1), 5.5),  # 01:00 .. 01:45
    ]


def test_a_day_is_a_day_in_utc(ch_client) -> None:
    """With a day as resolution the buckets start at 00:00 UTC."""
    _write(
        ch_client,
        [_load(60 * 20, 10.0), _load(60 * 23, 30.0), _load(60 * 25, 100.0)],
    )
    out = ch_client.read_metrics(
        "zone_load",
        T0 + timedelta(hours=13, minutes=22),
        T0 + timedelta(hours=40),
        {"zone": "ES"},
        params={"resolution_minutes": 1440},
    )
    assert [(m.timestamp, m.value) for m in out] == [
        (T0, 20.0),
        (T0 + timedelta(days=1), 100.0),
    ]


def test_a_table_without_valid_or_zone_status_can_be_resampled(ch_client) -> None:
    """The factors have no ``valid`` or ``zone_status`` and the query still works."""
    metrics = [
        Metric(
            MetricType.FACTOR,
            v,
            T0 + timedelta(minutes=15 * i),
            metadata={
                "factor_type": "carbon",
                "production_type": "gas",
                "scope": "life-cycle",
                "source": "x",
                "source_link": "",
                "unit": "g",
                "year": 2024,
            },
        )
        for i, v in enumerate([1.0, 3.0])
    ]
    _write(ch_client, metrics)
    out = ch_client.read_metrics(
        "factor", T0, T0 + timedelta(hours=1), None, params={"resolution_minutes": 60}
    )
    assert [(m.value, m.metadata["production_type"]) for m in out] == [(2.0, "gas")]
    assert "valid" not in out[0].metadata


def test_min_value_leaves_out_the_negatives_before_the_average(ch_client) -> None:
    """The average of the values that stay, and nothing if none stays."""
    _write(
        ch_client,
        [
            _load(0, 10.0),
            _load(15, -50.0),
            _load(30, 30.0),
            _load(45, 50.0),
            _load(60, -5.0),
            _load(75, -6.0),
        ],
    )
    params = {"resolution_minutes": 60, "min_value": 0}
    out = ch_client.read_metrics(
        "zone_load", T0, T0 + timedelta(hours=2), {"zone": "ES"}, params=params
    )
    assert [(m.timestamp, m.value) for m in out] == [(T0, 30.0)]
    raw = ch_client.read_metrics(
        "zone_load",
        T0,
        T0 + timedelta(hours=2),
        {"zone": "ES"},
        params={"min_value": 0},
    )
    assert sorted(m.value for m in raw) == [10.0, 30.0, 50.0]


@pytest.mark.parametrize("bad", [0, -15, 10, 20])
def test_a_resolution_that_is_not_a_multiple_of_the_interval_is_refused(
    ch_client, bad
) -> None:
    """Only whole intervals: 15, 30, 60..."""
    with pytest.raises(ValueError):
        _read(ch_client, bad) if bad else ch_client.read_metrics(
            "zone_load",
            T0,
            T0 + timedelta(hours=1),
            None,
            params={"resolution_minutes": bad},
        )
