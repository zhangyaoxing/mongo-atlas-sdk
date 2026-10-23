"""Language-agnostic transformations over the normalized type graph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mongo_atlas_sdk.generator.naming import pascal_case


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
        if kind == "object" and "name" not in expr and not (expr.get("properties") or {}):
            additional = expr.get("additional_properties")
            if isinstance(additional, Mapping):
                additional = transform(additional, owner, [*path, "Value"])
            map_result = {
                "kind": "object",
                "properties": {},
                "additional_properties": additional,
            }
            if expr.get("nullable"):
                map_result["nullable"] = True
            return map_result
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


def references(expr: Any, name: str) -> bool:
    """Whether ``expr`` contains a reference to ``name``."""
    if isinstance(expr, Mapping):
        if expr.get("kind") == "reference" and expr.get("name") == name:
            return True
        return any(references(value, name) for value in expr.values())
    if isinstance(expr, list):
        return any(references(value, name) for value in expr)
    return False


__all__ = ["hoist_inline_objects", "references"]
