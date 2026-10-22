"""Naming helpers for generated Python code."""

from __future__ import annotations

import keyword
import re
from typing import Any

from mongo_atlas_sdk.normalizer.schema import pascal_case

_ACRONYM = re.compile(r"([A-Z]+)([A-Z][a-z])")
_WORD = re.compile(r"([a-z0-9])([A-Z])")
_NON_WORD = re.compile(r"[^0-9A-Za-z]+")

_ENUM_OPERATORS = {
    "<": "LT",
    ">": "GT",
    "<=": "LTE",
    ">=": "GTE",
    "==": "EQ",
    "!=": "NE",
}

RESERVED_FIELDS = frozenset(
    {
        "model_config",
        "model_fields",
        "model_dump",
        "model_validate",
        "model_copy",
        "model_json_schema",
        "dict",
        "json",
        "copy",
        "schema",
        "self",
    }
)

__all__ = ["docstring_lines", "enum_member", "field_name", "pascal_case", "snake_case"]


def snake_case(name: str) -> str:
    """Convert a camelCase or PascalCase name to snake_case."""
    value = _ACRONYM.sub(r"\1_\2", name)
    value = _WORD.sub(r"\1_\2", value)
    value = _NON_WORD.sub("_", value).strip("_").lower()
    if not value:
        value = "value"
    if value[0].isdigit():
        value = f"field_{value}"
    if keyword.iskeyword(value):
        value = f"{value}_"
    return value


def field_name(property_name: str) -> str:
    """Convert a wire property name to a safe Python attribute name."""
    value = property_name.lstrip("_")
    value = snake_case(value) if value else "field"
    if value in RESERVED_FIELDS:
        value = f"{value}_"
    return value


def enum_member(value: Any, index: int) -> str:
    """Convert an enum value to a valid, readable member name."""
    text = str(value)
    if text in _ENUM_OPERATORS:
        return _ENUM_OPERATORS[text]
    member = _NON_WORD.sub("_", text).strip("_").upper()
    if not member:
        member = f"VALUE_{index}"
    if member[0].isdigit():
        member = f"VALUE_{member}"
    if keyword.iskeyword(member.lower()):
        member = f"{member}_"
    return member


def docstring_lines(text: object, indent: str) -> list[str]:
    """Render ``text`` as a (possibly multi-line) docstring body."""
    if not isinstance(text, str) or not text.strip():
        return []
    cleaned = text.strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    lines = cleaned.splitlines()
    if len(lines) == 1:
        return [f'{indent}"""{lines[0]}"""']
    return [f'{indent}"""', *(f"{indent}{line}" for line in lines), f'{indent}"""']
