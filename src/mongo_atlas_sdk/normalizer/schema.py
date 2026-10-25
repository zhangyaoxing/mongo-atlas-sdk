"""Normalize OpenAPI schema fragments into a generator-friendly type tree."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

PRIMITIVE_TYPES = frozenset({"string", "integer", "number", "boolean"})
_ALIAS_KEYS = frozenset({"$ref", "description", "title"})
_SCHEMA_REF_PREFIX = "#/components/schemas/"
_DELIMITER = re.compile(r"[^0-9A-Za-z]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def pascal_case(raw: str) -> str:
    """Turn a schema name into a valid PascalCase identifier."""
    cleaned = _DELIMITER.sub(" ", raw).strip()
    words = [word for chunk in cleaned.split() for word in _CAMEL_BOUNDARY.split(chunk) if word]
    name = "".join(word[:1].upper() + word[1:] for word in words)
    if not name:
        return "Anonymous"
    if name[0].isdigit():
        return f"Type{name}"
    return name


def _ref_tokens(ref: str) -> list[str]:
    suffix = ref[len(_SCHEMA_REF_PREFIX) :] if ref.startswith(_SCHEMA_REF_PREFIX) else ref
    return [token.replace("~1", "/").replace("~0", "~") for token in suffix.split("/")]


def _const_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"


class SchemaNormalizer:
    """Resolve ``$ref``/``allOf``/``oneOf`` and register the named type graph."""

    def __init__(self, schemas: Mapping[str, Any]) -> None:
        self._schemas = schemas
        self.types: dict[str, dict[str, Any]] = {}
        self.warnings: list[str] = []
        self._names_by_ref: dict[str, str] = {}

    def expression(self, schema: Any) -> dict[str, Any]:
        """Return a closed type expression for ``schema``."""
        if not isinstance(schema, Mapping) or not schema:
            return {"kind": "any"}

        ref = schema.get("$ref")
        if isinstance(ref, str):
            resolved = self._resolve_alias(ref)
            if resolved is None:
                return {"kind": "any"}
            raw, final_ref = resolved
            name = self._ensure_type(final_ref, raw)
            self._names_by_ref.setdefault(ref, name)
            reference: dict[str, Any] = {"kind": "reference", "name": name}
            if schema.get("nullable"):
                reference["nullable"] = True
            return reference

        all_of = schema.get("allOf")
        if isinstance(all_of, list) and all_of:
            merged = self._merge_all_of(schema, set())
            if merged is not None:
                return self.expression(merged)

        for keyword in ("oneOf", "anyOf"):
            variants = schema.get(keyword)
            if isinstance(variants, list) and variants:
                union: dict[str, Any] = {
                    "kind": "union",
                    "mode": keyword,
                    "variants": [self.expression(variant) for variant in variants],
                }
                discriminator = schema.get("discriminator")
                if isinstance(discriminator, Mapping) and discriminator.get("propertyName"):
                    union["discriminator"] = discriminator["propertyName"]
                if schema.get("nullable"):
                    union["nullable"] = True
                return union

        kind = schema.get("type")
        if isinstance(kind, list):
            return self._type_list_expression(schema, kind)

        if kind == "null":
            return {"kind": "primitive", "type": "null"}

        if kind == "array":
            array_expr: dict[str, Any] = {
                "kind": "array",
                "items": self.expression(schema.get("items") or {}),
            }
            if schema.get("nullable"):
                array_expr["nullable"] = True
            return array_expr

        if kind == "object" or "properties" in schema or "additionalProperties" in schema:
            object_expr = self._object_expression(schema)
            if schema.get("nullable"):
                object_expr["nullable"] = True
            return object_expr

        if "const" in schema and schema["const"] is not None:
            value = schema["const"]
            const_expr: dict[str, Any] = {
                "kind": "enum",
                "type": kind if isinstance(kind, str) else _const_type(value),
                "values": [value],
                "const": True,
            }
            self._apply_scalar_metadata(const_expr, schema)
            return const_expr

        if "enum" in schema:
            enum_expr: dict[str, Any] = {
                "kind": "enum",
                "type": kind if isinstance(kind, str) else "string",
                "values": list(schema["enum"]),
            }
            self._apply_scalar_metadata(enum_expr, schema)
            return enum_expr

        if isinstance(kind, str) and kind in PRIMITIVE_TYPES:
            primitive: dict[str, Any] = {"kind": "primitive", "type": kind}
            self._apply_scalar_metadata(primitive, schema)
            return primitive

        return {"kind": "any"}

    # -- schema plumbing -------------------------------------------------
    def _apply_scalar_metadata(self, expr: dict[str, Any], schema: Mapping[str, Any]) -> None:
        fmt = schema.get("format")
        if isinstance(fmt, str):
            expr["format"] = fmt
        if "default" in schema:
            expr["default"] = schema["default"]
        if schema.get("nullable"):
            expr["nullable"] = True

    def _type_list_expression(self, schema: Mapping[str, Any], kinds: list[Any]) -> dict[str, Any]:
        non_null = [kind for kind in kinds if kind != "null"]
        nullable = "null" in kinds
        if not non_null:
            return {"kind": "primitive", "type": "null"}
        if len(non_null) == 1:
            clone = dict(schema)
            clone["type"] = non_null[0]
            expr = self.expression(clone)
            if nullable:
                expr["nullable"] = True
            return expr
        union: dict[str, Any] = {
            "kind": "union",
            "mode": "anyOf",
            "variants": [self.expression({**schema, "type": kind}) for kind in non_null],
        }
        if nullable:
            union["nullable"] = True
        return union

    def _object_expression(self, schema: Mapping[str, Any]) -> dict[str, Any]:
        required = {name for name in (schema.get("required") or []) if isinstance(name, str)}
        properties: dict[str, Any] = {}
        raw_properties = schema.get("properties")
        if isinstance(raw_properties, Mapping):
            for name, prop_schema in raw_properties.items():
                entry: dict[str, Any] = {"required": name in required}
                if isinstance(prop_schema, Mapping):
                    description = prop_schema.get("description")
                    if isinstance(description, str) and description:
                        entry["description"] = description
                entry["type"] = self.expression(prop_schema)
                properties[name] = entry
        return {
            "kind": "object",
            "properties": properties,
            "additional_properties": self._additional_properties(schema),
        }

    def _additional_properties(self, schema: Mapping[str, Any]) -> Any:
        if "additionalProperties" not in schema:
            return None
        value = schema["additionalProperties"]
        if isinstance(value, bool):
            return value
        if isinstance(value, Mapping):
            return self.expression(value)
        return None

    def _resolve_alias(self, ref: str) -> tuple[Mapping[str, Any], str] | None:
        seen: set[str] = set()
        current = ref
        while True:
            if current in seen:
                self.warnings.append(f"Circular $ref: {current}")
                return None
            seen.add(current)
            raw = self._lookup(current)
            if raw is None:
                self.warnings.append(f"Unresolved $ref: {current}")
                return None
            nested = raw.get("$ref")
            if isinstance(nested, str) and set(raw) <= _ALIAS_KEYS:
                current = nested
                continue
            return raw, current

    def _lookup(self, ref: str) -> Mapping[str, Any] | None:
        if not ref.startswith(_SCHEMA_REF_PREFIX):
            return None
        node: Any = self._schemas
        for token in _ref_tokens(ref):
            if not isinstance(node, Mapping):
                return None
            node = node.get(token)
        return node if isinstance(node, Mapping) else None

    def _ensure_type(self, ref: str, raw: Mapping[str, Any]) -> str:
        existing = self._names_by_ref.get(ref)
        if existing is not None:
            return existing
        name = self._unique_name(ref)
        self._names_by_ref[ref] = name
        placeholder: dict[str, Any] = {"name": name, "kind": "unknown"}
        self.types[name] = placeholder
        placeholder.update(self._definition(name, raw))
        return name

    def _unique_name(self, ref: str) -> str:
        base = pascal_case("_".join(_ref_tokens(ref)))
        candidate = base
        counter = 2
        while candidate in self.types:
            candidate = f"{base}{counter}"
            counter += 1
        return candidate

    def _definition(self, name: str, raw: Mapping[str, Any]) -> dict[str, Any]:
        all_of = raw.get("allOf")
        if isinstance(all_of, list) and all_of:
            merged = self._merge_all_of(raw, set())
            if merged is not None:
                raw = merged

        description = raw.get("description")
        definition: dict[str, Any] = {"name": name}
        if isinstance(description, str) and description:
            definition["description"] = description

        for keyword in ("oneOf", "anyOf"):
            variants = raw.get(keyword)
            if isinstance(variants, list) and variants:
                definition["kind"] = "union"
                definition["mode"] = keyword
                definition["variants"] = [self.expression(variant) for variant in variants]
                discriminator = raw.get("discriminator")
                if isinstance(discriminator, Mapping) and discriminator.get("propertyName"):
                    definition["discriminator"] = discriminator["propertyName"]
                if raw.get("nullable"):
                    definition["nullable"] = True
                return definition

        kind = raw.get("type")
        if kind == "array":
            definition["kind"] = "alias"
            definition["target"] = {
                "kind": "array",
                "items": self.expression(raw.get("items") or {}),
            }
            if raw.get("nullable"):
                definition["nullable"] = True
            return definition

        if kind == "object" or "properties" in raw or "additionalProperties" in raw:
            definition.update(self._object_expression(raw))
            if raw.get("nullable"):
                definition["nullable"] = True
            return definition

        if raw.get("type") == "null":
            definition.update({"kind": "primitive", "type": "null"})
            return definition

        if "const" in raw and raw["const"] is not None:
            value = raw["const"]
            definition.update(
                {
                    "kind": "enum",
                    "type": kind if isinstance(kind, str) else _const_type(value),
                    "values": [value],
                    "const": True,
                }
            )
            self._apply_scalar_metadata(definition, raw)
            return definition

        if "enum" in raw:
            definition.update(
                {
                    "kind": "enum",
                    "type": kind if isinstance(kind, str) else "string",
                    "values": list(raw["enum"]),
                }
            )
            self._apply_scalar_metadata(definition, raw)
            return definition

        if isinstance(kind, str) and kind in PRIMITIVE_TYPES:
            definition.update({"kind": "primitive", "type": kind})
            self._apply_scalar_metadata(definition, raw)
            return definition

        definition.update({"kind": "alias", "target": {"kind": "any"}})
        return definition

    def _merge_all_of(self, schema: Mapping[str, Any], seen: set[str]) -> dict[str, Any] | None:
        merged: dict[str, Any] = {}
        properties: dict[str, Any] = {}
        required: list[str] = []
        descriptions: list[str] = []

        for branch in schema.get("allOf") or []:
            if not isinstance(branch, Mapping):
                continue
            ref = branch.get("$ref")
            if isinstance(ref, str):
                if ref in seen:
                    continue
                seen.add(ref)
                resolved = self._resolve_alias(ref)
                if resolved is None:
                    continue
                branch = resolved[0]
            nested_all_of = branch.get("allOf")
            if isinstance(nested_all_of, list) and nested_all_of:
                nested = self._merge_all_of(branch, seen)
                if nested is None:
                    continue
                branch = nested
            if isinstance(branch.get("properties"), Mapping):
                properties.update(branch["properties"])
            for name in branch.get("required") or []:
                if isinstance(name, str) and name not in required:
                    required.append(name)
            description = branch.get("description")
            if isinstance(description, str) and description:
                descriptions.append(description)
            for key in ("type", "additionalProperties", "nullable", "format"):
                if key in branch and key not in merged:
                    merged[key] = branch[key]

        own_properties = schema.get("properties")
        if isinstance(own_properties, Mapping):
            properties.update(own_properties)
        for name in schema.get("required") or []:
            if isinstance(name, str) and name not in required:
                required.append(name)
        for key, value in schema.items():
            if key in {"allOf", "properties", "required"}:
                continue
            merged[key] = value

        merged["properties"] = properties
        if required:
            merged["required"] = required
        if "description" not in merged and descriptions:
            merged["description"] = descriptions[0]
        merged.setdefault("type", "object")
        return merged
