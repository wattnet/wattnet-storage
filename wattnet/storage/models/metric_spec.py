"""Declaration of a metric that is not one of the built-in MetricType values."""

import re
from dataclasses import dataclass, field

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
# A storage type such as Nullable(Int32): it goes into the DDL, so nothing else is
# allowed.
_TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\([A-Za-z0-9_, ()]*\))?$")

# Labels that describe the quality or the origin of a value, not which data point it
# is: by default they are left out of the key, so a newer version of a point replaces
# the old one.
VERSION_LABELS = frozenset({"valid", "zone_status", "data_state", "datasource", "unit"})

# Columns that every metric has; a label cannot use these names.
RESERVED = frozenset({"timestamp", "value", "updated_at"})

DEFAULT_LABEL_TYPE = "LowCardinality(String)"


def check_identifier(name: str) -> str:
    """Return the name if it is a safe identifier (lowercase, digits, underscores)."""
    if not _IDENTIFIER.match(name):
        raise ValueError(
            f"Invalid name {name!r}: use lowercase letters, digits and underscores"
        )
    return name


@dataclass(frozen=True)
class MetricSpec:
    """A metric declared by the application that writes it.

    :param name: name of the metric, also the name of its table
    :param labels: names of the labels (metadata keys) the metric has
    :param key: labels that identify a data point. Two values with the same timestamp
        and key are versions of one point and only the newest is kept. Default: every
        label except those in VERSION_LABELS.
    :param types: storage type of a label when it is not a short text, for example
        {"year": "Nullable(Int32)"}
    """

    name: str
    labels: tuple[str, ...]
    key: tuple[str, ...] | None = None
    types: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate names, so they can be used as table and column names."""
        check_identifier(self.name)
        object.__setattr__(self, "labels", tuple(self.labels))
        for label in self.labels:
            check_identifier(label)
            if label in RESERVED:
                raise ValueError(f"Label {label!r} is reserved")
        if len(set(self.labels)) != len(self.labels):
            raise ValueError(f"Metric {self.name!r} repeats a label")
        key = self.key
        if key is None:
            key = tuple(x for x in self.labels if x not in VERSION_LABELS)
        object.__setattr__(self, "key", tuple(key))
        unknown = (set(self.key or ()) | set(self.types)) - set(self.labels)
        if unknown:
            raise ValueError(f"Not labels of {self.name!r}: {sorted(unknown)}")
        for label, typ in self.types.items():
            if not _TYPE.match(typ):
                raise ValueError(f"Invalid type {typ!r} for label {label!r}")

    def columns(self) -> list[tuple[str, str]]:
        """Columns of the table: timestamp, value, the labels and updated_at."""
        return [
            ("timestamp", "DateTime"),
            ("value", "Float32"),
            *((x, self.types.get(x, DEFAULT_LABEL_TYPE)) for x in self.labels),
            ("updated_at", "DateTime"),
        ]
