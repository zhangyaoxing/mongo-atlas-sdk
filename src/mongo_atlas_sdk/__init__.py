"""MongoDB Atlas SDK."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mongo-atlas-sdk")
except PackageNotFoundError:  # pragma: no cover - running from a plain source checkout
    __version__ = "0.0.0"

__all__ = ["__version__"]
