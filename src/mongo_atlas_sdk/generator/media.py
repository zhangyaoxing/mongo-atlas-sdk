"""Helpers for Atlas versioned media types."""

from __future__ import annotations

import re
from collections.abc import Iterable

_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def media_type_date(media_type: str) -> tuple[int, int, int] | None:
    """Return the version date embedded in an Atlas media type, if any."""
    match = _DATE.search(media_type)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def latest_media_type(media_types: Iterable[str]) -> str | None:
    """Pick the newest versioned media type, preferring JSON on ties."""
    dated = [(media_type_date(media_type), media_type) for media_type in media_types]
    candidates = [(date, media_type) for date, media_type in dated if date is not None]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], "json" in item[1], item[1]))
    return candidates[-1][1]


__all__ = ["latest_media_type", "media_type_date"]
