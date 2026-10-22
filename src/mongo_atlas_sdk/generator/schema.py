"""Type-expression helpers for the Python code generator."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mongo_atlas_sdk.generator.naming import pascal_case

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


def hoist_inline_objects(types: Mapping[str, Any]) -> dict[str, Any]:
    """Give anonymous object schemas deterministic names and register them as types."""
    hoisted: dict[str, Any] = {
        name: definition for name, definition in types.items() if isinstance(definition, Mapping)
    }
    reserved = set(hoisted)

    def unique(base: str) -> str:
        candidate = base
        counter = 2
        while candidate in reserved:
            candidate = f"{base}{counter}"
            counter += 1
        reserved.add(candidate)
        return candidate

    def transform(expr: Any, owner: str, path: list[str]) -> dict[str, Any]:
        if not isinstance(expr, Mapping):
            return {"kind": "any"}
        kind = expr.get("kind")
        if kind == "object" and "name" not in expr:
            name = unique(owner + "".join(pascal_case(part) for part in path))
            properties: dict[str, Any] = {}
            for property_name, property_definition in (expr.get("properties") or {}).items():
                entry = {key: value for key, value in property_definition.items() if key != "type"}
                entry["type"] = transform(
                    property_definition.get("type"),
                    name,
                    [property_name],
                )
                properties[property_name] = entry
            hoisted[name] = {
                "name": name,
                "kind": "object",
                "properties": properties,
                "additional_properties": expr.get("additional_properties"),
            }
            return {"kind": "reference", "name": name}
        if kind == "array":
            result: dict[str, Any] = {
                "kind": "array",
                "items": transform(expr.get("items"), owner, [*path, "Item"]),
            }
        elif kind == "union":
            result = {
                "kind": "union",
                "mode": expr.get("mode"),
                "variants": [
                    transform(variant, owner, [*path, f"Variant{index + 1}"])
                    for index, variant in enumerate(expr.get("variants") or [])
                ],
            }
            if expr.get("discriminator"):
                result["discriminator"] = expr["discriminator"]
        else:
            return dict(expr)
        if expr.get("nullable"):
            result["nullable"] = True
        return result

    for name in list(hoisted):
        definition = hoisted[name]
        kind = definition.get("kind")
        if kind == "object":
            for property_name, property_definition in (definition.get("properties") or {}).items():
                property_definition["type"] = transform(
                    property_definition.get("type"),
                    name,
                    [property_name],
                )
        elif kind == "union":
            definition["variants"] = [
                transform(variant, name, [f"Variant{index + 1}"])
                for index, variant in enumerate(definition.get("variants") or [])
            ]
        elif kind == "alias":
            definition["target"] = transform(definition.get("target"), name, [])
    return hoisted


def annotation(expr: Mapping[str, Any], *, current: str, imports: set[str]) -> str:
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
        values = ", ".join(json.dumps(value) for value in expr.get("values") or [])
        return f"Literal[{values}]"
    if kind == "array":
        items = annotation(expr.get("items") or {}, current=current, imports=imports)
        return f"list[{items}]"
    if kind == "reference":
        name = str(expr.get("name") or "Any")
        if name != current:
            imports.add(name)
        return name
    if kind == "union":
        parts = [
            annotation(variant, current=current, imports=imports)
            for variant in expr.get("variants") or []
        ]
        parts = list(dict.fromkeys(parts)) or ["Any"]
        return " | ".join(parts)
    if kind == "object":
        imports.add("Any")
        return "dict[str, Any]"
    imports.add("Any")
    return "Any"


def references(expr: Any, name: str) -> bool:
    """Whether ``expr`` contains a reference to ``name``."""
    if isinstance(expr, Mapping):
        if expr.get("kind") == "reference" and expr.get("name") == name:
            return True
        return any(references(value, name) for value in expr.values())
    if isinstance(expr, list):
        return any(references(value, name) for value in expr)
    return False
