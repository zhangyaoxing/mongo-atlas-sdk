"""Render pydantic v2 model modules from templates."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mongo_atlas_sdk.generator.ir import references
from mongo_atlas_sdk.generator.python.naming import enum_member, field_name, snake_case
from mongo_atlas_sdk.generator.python.schema import annotation
from mongo_atlas_sdk.generator.python.templating import docstring_text
from mongo_atlas_sdk.generator.templating import render

_TYPING = frozenset({"Any", "Literal", "TypeAlias"})
_DATETIME = frozenset({"datetime", "date"})
_MODEL_IMPORT_SKIP = _TYPING | _DATETIME


def _import_block(imports: set[str], package: str) -> list[str]:
    lines: list[str] = []
    typing_names = sorted(_TYPING & imports)
    if typing_names:
        lines.append(f"from typing import {', '.join(typing_names)}")
    datetime_names = sorted(_DATETIME & imports)
    if datetime_names:
        lines.append(f"from datetime import {', '.join(datetime_names)}")
    for name in sorted(imports - _MODEL_IMPORT_SKIP):
        lines.append(f"from {package}.models.{snake_case(name)} import {name}")
    return lines


def _object_fields(
    definition: Mapping[str, Any], *, name: str, imports: set[str]
) -> tuple[list[dict[str, Any]], bool]:
    fields: list[dict[str, Any]] = []
    used_fields: set[str] = set()
    needs_rebuild = False
    properties = definition.get("properties") or {}
    for property_name, property_definition in properties.items():
        field = field_name(property_name)
        base = field
        counter = 2
        while field in used_fields:
            field = f"{base}_{counter}"
            counter += 1
        used_fields.add(field)

        type_expr = property_definition.get("type") or {}
        resolved = annotation(type_expr, current=name, imports=imports)
        if type_expr.get("nullable") or not property_definition.get("required"):
            resolved = f"{resolved} | None"

        alias_needed = field != property_name
        description_value = property_definition.get("description")
        description_needed = isinstance(description_value, str) and bool(description_value.strip())
        required = bool(property_definition.get("required"))

        arguments: list[str] = []
        if not required:
            arguments.append("default=None")
        if alias_needed:
            arguments.append(f"alias={json.dumps(property_name)}")
        if description_needed and isinstance(description_value, str):
            arguments.append(f"description={json.dumps(description_value)}")

        if required:
            suffix = f" = Field({', '.join(arguments)})" if arguments else ""
        elif alias_needed or description_needed:
            suffix = f" = Field({', '.join(arguments)})"
        else:
            suffix = " = None"

        fields.append({"name": field, "annotation": resolved, "suffix": suffix})
        if references(type_expr, name):
            needs_rebuild = True
    return fields, needs_rebuild


def _enum_members(definition: Mapping[str, Any]) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    used: set[str] = set()
    for index, value in enumerate(definition.get("values") or []):
        member = enum_member(value, index)
        base = member
        counter = 2
        while member in used:
            member = f"{base}_{counter}"
            counter += 1
        used.add(member)
        members.append({"name": member, "value": json.dumps(value)})
    return members


def render_model(definition: Mapping[str, Any], *, package: str) -> str:
    """Render one normalized type definition as a Python module."""
    name = str(definition.get("name"))
    kind = definition.get("kind")
    imports: set[str] = set()

    if kind == "object":
        fields, rebuild = _object_fields(definition, name=name, imports=imports)
        return render(
            "python",
            "model_object.py.j2",
            name=name,
            imports=_import_block(imports, package),
            description=docstring_text(
                definition.get("description"), f"Generated model for {name}."
            ),
            fields=fields,
            rebuild=rebuild,
        )

    if kind == "enum":
        base = "int" if definition.get("type") == "integer" else "str"
        return render(
            "python",
            "model_enum.py.j2",
            name=name,
            base=base,
            description=docstring_text(
                definition.get("description"), f"Generated enum for {name}."
            ),
            members=_enum_members(definition),
        )

    if kind == "union":
        target: Mapping[str, Any] = {
            "kind": "union",
            "variants": definition.get("variants") or [],
        }
    else:
        target = definition.get("target") or {}
    imports.add("TypeAlias")
    rendered_target = annotation(target, current=name, imports=imports)
    return render(
        "python",
        "model_alias.py.j2",
        name=name,
        imports=_import_block(imports, package),
        target=rendered_target,
    )


__all__ = ["render_model"]
