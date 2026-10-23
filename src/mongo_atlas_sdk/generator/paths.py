"""Shared URL path helpers for generated clients."""

from __future__ import annotations

ATLAS_API_PATH_PREFIX = "/api/atlas/v2"


def api_path(path: str, *, prefix: str = ATLAS_API_PATH_PREFIX) -> str:
    """Make an Atlas path relative to a base URL that already carries the prefix."""
    if path == prefix:
        return "/"
    if path.startswith(prefix + "/"):
        return path[len(prefix) :]
    return path


__all__ = ["ATLAS_API_PATH_PREFIX", "api_path"]
