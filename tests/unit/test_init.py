import importlib
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch


def test_version_is_string():
    import wattnet.storage

    assert isinstance(wattnet.storage.__version__, str)


def test_version_fallback_to_unknown_when_package_not_found():
    import wattnet.storage as storage_mod

    with patch(
        "importlib.metadata.version",
        side_effect=PackageNotFoundError("wattnet-storage"),
    ):
        importlib.reload(storage_mod)
        assert storage_mod.__version__ == "unknown"

    importlib.reload(storage_mod)
