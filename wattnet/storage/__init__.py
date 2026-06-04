"""wattnet-storage: Storage client for the Wattnet platform."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("wattnet-storage")
except PackageNotFoundError:
    __version__ = "unknown"
