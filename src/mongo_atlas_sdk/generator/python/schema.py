"""Python type annotations for normalized type expressions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

PRIMITIVE_TYPES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
}

_STRING_FORMATS = {
    "date-time": "datetime",
    "date": "date",
}


def annotation(
    expr: Mapping[str, Any],
    *,
    current: str,
    imports: set[str],
    case_insensitive: bool = True,
) -> str:
    """Render a normalized type expression as a Python annotation."""
    kind = expr.get("kind")
    if kind == "primitive":
        fmt = expr.get("format")
        if isinstance(fmt, str) and fmt in _STRING_FORMATS:
            imports.add(_STRING_FORMATS[fmt])
            return _STRING_FORMATS[fmt]
        return PRIMITIVE_TYPES.get(str(expr.get("type")), "Any")
    if kind == "enum":
        imports.add("Literal")
        raw_values = list(expr.get("values") or [])
        values = ", ".join(json.dumps(value) for value in raw_values)
        literal = f"Literal[{values}]"
        uppercase_strings = bool(raw_values) and all(
            isinstance(value, str) and value == value.upper() for value in raw_values
        )
        if case_insensitive and uppercase_strings:
            imports.update({"Annotated", "BeforeValidator", "upper_case"})
            return f"Annotated[{literal}, BeforeValidator(upper_case)]"
        return literal
    if kind == "array":
        items = annotation(
            expr.get("items") or {},
            current=current,
            imports=imports,
            case_insensitive=case_insensitive,
        )
        return f"list[{items}]"
    if kind == "reference":
        name = str(expr.get("name") or "Any")
        if name != current:
            imports.add(name)
        return name
    if kind == "union":
        parts = [
            annotation(
                variant,
                current=current,
                imports=imports,
                case_insensitive=case_insensitive,
            )
            for variant in expr.get("variants") or []
        ]
        parts = list(dict.fromkeys(parts)) or ["Any"]
        return " | ".join(parts)
    if kind == "object":
        imports.add("Any")
        return "dict[str, Any]"
    imports.add("Any")
    return "Any"
