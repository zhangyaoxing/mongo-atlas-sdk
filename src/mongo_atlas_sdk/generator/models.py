"""Render pydantic v2 model modules."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mongo_atlas_sdk.generator.naming import docstring_lines, enum_member, field_name, snake_case
from mongo_atlas_sdk.generator.schema import annotation, references

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


def _object_body(definition: Mapping[str, Any], *, name: str, imports: set[str]) -> list[str]:
    lines = [f"class {name}(BaseModel):"]
    description = definition.get("description")
    lines.extend(docstring_lines(description or f"Generated model for {name}.", "    "))
    lines.append('    model_config = ConfigDict(populate_by_name=True, extra="allow")')

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

        lines.append(f"    {field}: {resolved}{suffix}")
        if references(type_expr, name):
            needs_rebuild = True

    if not properties:
        lines.append("    pass")
    elif needs_rebuild:
        lines.extend(["", f"{name}.model_rebuild()"])
    return lines


def _enum_body(definition: Mapping[str, Any], *, name: str) -> list[str]:
    base = "int" if definition.get("type") == "integer" else "str"
    lines = [f"class {name}({base}, Enum):"]
    lines.extend(
        docstring_lines(definition.get("description") or f"Generated enum for {name}.", "    ")
    )
    used: set[str] = set()
    values = definition.get("values") or []
    for index, value in enumerate(values):
        member = enum_member(value, index)
        base_member = member
        counter = 2
        while member in used:
            member = f"{base_member}_{counter}"
            counter += 1
        used.add(member)
        lines.append(f"    {member} = {json.dumps(value)}")
    if not values:
        lines.append("    pass")
    return lines


def _alias_body(definition: Mapping[str, Any], *, name: str, imports: set[str]) -> list[str]:
    if definition.get("kind") == "union":
        target: Mapping[str, Any] = {
            "kind": "union",
            "variants": definition.get("variants") or [],
        }
    else:
        target = definition.get("target") or {}
    rendered = annotation(target, current=name, imports=imports)
    imports.add("TypeAlias")
    return [f"{name}: TypeAlias = {rendered}"]


def render_model(definition: Mapping[str, Any], *, package: str) -> str:
    """Render one normalized type definition as a Python module."""
    name = str(definition.get("name"))
    kind = definition.get("kind")
    imports: set[str] = set()

    if kind == "object":
        body = _object_body(definition, name=name, imports=imports)
        third_party = ["from pydantic import BaseModel, ConfigDict, Field"]
    elif kind == "enum":
        body = _enum_body(definition, name=name)
        third_party = ["from enum import Enum"]
    else:
        body = _alias_body(definition, name=name, imports=imports)
        third_party = []

    header = [
        f'"""Generated model for {name}. Do not edit manually."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    stdlib = _import_block(imports, package)
    if stdlib:
        header.extend(stdlib)
        header.append("")
    if third_party:
        header.extend(third_party)
        header.append("")
    header.extend(body)
    return "\n".join(header).rstrip() + "\n"


__all__ = ["render_model"]
