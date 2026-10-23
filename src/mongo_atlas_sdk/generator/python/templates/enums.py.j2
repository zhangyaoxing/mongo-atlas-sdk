"""Runtime helpers for generated enums. Do not edit manually."""

from __future__ import annotations

from enum import Enum
from typing import Any


def upper_case(value: Any) -> Any:
    """Uppercase string values before enum validation."""
    return value.upper() if isinstance(value, str) else value


class CaseInsensitiveEnum(str, Enum):
    """String enum that accepts any casing of its declared values."""

    @classmethod
    def _missing_(cls, value: Any) -> CaseInsensitiveEnum | None:
        if isinstance(value, str):
            upper = value.upper()
            for member in cls:
                if member.value == upper:
                    return member
        return None
