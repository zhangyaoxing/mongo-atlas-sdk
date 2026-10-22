"""Turn an OpenAPI document into the raw intermediate ``api_docs.json`` shape."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
PARAMETER_LOCATIONS = ("path", "query", "body")
UNTAGGED = "Untagged"


def _resolve_pointer(spec: Mapping[str, Any], ref: str) -> Mapping[str, Any]:
    """Resolve a local JSON pointer such as ``#/components/schemas/Cluster``."""
    if not ref.startswith("#/"):
        raise ValueError(f"Only local $ref values are supported, got: {ref}")
    node: Any = spec
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            node = node[token]
        except (KeyError, TypeError) as exc:
            raise KeyError(f"Unresolvable $ref: {ref}") from exc
    if not isinstance(node, Mapping):
        raise TypeError(f"$ref must point to an object: {ref}")
    return node


def _resolve_if_ref(spec: Mapping[str, Any], node: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = node.get("$ref")
    if isinstance(ref, str):
        return _resolve_pointer(spec, ref)
    return node


def _resolve_schema(spec: Mapping[str, Any], schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Follow ``$ref`` aliases until a schema with real content is reached."""
    seen: set[str] = set()
    current = schema
    while isinstance(current.get("$ref"), str):
        ref = current["$ref"]
        if ref in seen:
            raise ValueError(f"Circular $ref: {ref}")
        seen.add(ref)
        current = _resolve_pointer(spec, ref)
    return current


def _type_name(schema: Mapping[str, Any]) -> str:
    """Return a compact, unresolved type label for a schema fragment."""
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref.rsplit("/", 1)[-1]
    kind = schema.get("type")
    if kind == "array":
        items = schema.get("items")
        inner = _type_name(items) if isinstance(items, Mapping) else "unknown"
        return f"array<{inner}>"
    if isinstance(kind, str):
        return kind
    if any(key in schema for key in ("allOf", "oneOf", "anyOf")):
        return "composed"
    return "unknown"


def _build_parameter(spec: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
    parameter = _resolve_if_ref(spec, raw)
    schema = parameter.get("schema")
    schema = _resolve_schema(spec, schema) if isinstance(schema, Mapping) else {}
    return {
        "name": parameter.get("name") or "",
        "in": parameter.get("in") or "",
        "type": _type_name(schema),
        "required": bool(parameter.get("required", False)),
        "description": parameter.get("description") or "",
        "schema": schema,
    }


def _build_body(
    spec: Mapping[str, Any],
    raw_body: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not raw_body:
        return None
    body = _resolve_if_ref(spec, raw_body)
    content = body.get("content") or {}
    if not isinstance(content, Mapping) or not content:
        return None

    content_type = next((key for key in content if "json" in key), next(iter(content)))
    media = content.get(content_type) or {}
    schema_raw = media.get("schema") if isinstance(media, Mapping) else {}
    if not isinstance(schema_raw, Mapping):
        schema_raw = {}
    schema = _resolve_schema(spec, schema_raw)
    if schema.get("type") == "array" and isinstance(schema.get("items"), Mapping):
        property_source = _resolve_schema(spec, schema["items"])
    else:
        property_source = schema
    required = set(property_source.get("required") or [])
    properties = property_source.get("properties") or {}

    parameters = [
        {
            "name": name,
            "in": "body",
            "type": _type_name(prop) if isinstance(prop, Mapping) else "unknown",
            "required": name in required,
            "description": (prop.get("description") or "") if isinstance(prop, Mapping) else "",
            "schema": prop if isinstance(prop, Mapping) else {},
        }
        for name, prop in properties.items()
    ]
    parameters.sort(key=lambda item: item["name"])

    ref = schema_raw.get("$ref")
    return {
        "content_type": content_type,
        "type": _type_name(schema),
        "required": bool(body.get("required", False)),
        "description": body.get("description") or "",
        "schema_ref": ref.rsplit("/", 1)[-1] if isinstance(ref, str) else None,
        "schema": schema_raw,
        "parameters": parameters,
    }


def _build_endpoint(
    spec: Mapping[str, Any],
    path: str,
    method: str,
    operation: Mapping[str, Any],
    path_parameters: list[Mapping[str, Any]],
) -> dict[str, Any]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in (*path_parameters, *(operation.get("parameters") or [])):
        parameter = _build_parameter(spec, raw)
        merged[(parameter["name"], parameter["in"])] = parameter

    grouped: dict[str, list[dict[str, Any]]] = {location: [] for location in PARAMETER_LOCATIONS}
    for parameter in merged.values():
        bucket = grouped.get(parameter["in"])
        if bucket is not None:
            bucket.append(parameter)

    body = _build_body(spec, operation.get("requestBody"))
    grouped["body"] = body["parameters"] if body else []
    for bucket in grouped.values():
        bucket.sort(key=lambda item: item["name"])

    request_body = None
    if body is not None:
        request_body = {key: value for key, value in body.items() if key != "parameters"}

    return {
        "operation_id": operation.get("operationId") or "",
        "summary": operation.get("summary") or "",
        "description": operation.get("description") or "",
        "method": method.upper(),
        "path": path,
        "tags": list(operation.get("tags") or []),
        "parameters": grouped,
        "request_body": request_body,
    }


def _spec_digest(spec: Mapping[str, Any]) -> str:
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def extract_api_docs(
    spec: Mapping[str, Any],
    *,
    source_url: str,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Project an OpenAPI document onto the raw crawl output structure."""
    tag_descriptions = {
        tag["name"]: tag.get("description") or ""
        for tag in (spec.get("tags") or [])
        if isinstance(tag, Mapping) and tag.get("name")
    }
    declared_order = list(tag_descriptions)
    by_tag: dict[str, list[dict[str, Any]]] = {}

    paths = spec.get("paths") or {}
    for path, path_item in paths.items():
        if not isinstance(path_item, Mapping):
            continue
        path_parameters = [p for p in (path_item.get("parameters") or []) if isinstance(p, Mapping)]
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, Mapping):
                continue
            endpoint = _build_endpoint(spec, path, method, operation, path_parameters)
            primary_tag = endpoint["tags"][0] if endpoint["tags"] else UNTAGGED
            by_tag.setdefault(primary_tag, []).append(endpoint)

    order = [tag for tag in declared_order if tag in by_tag]
    order += sorted(tag for tag in by_tag if tag not in declared_order)

    categories = [
        {
            "name": tag,
            "description": tag_descriptions.get(tag, ""),
            "endpoints": sorted(by_tag[tag], key=lambda item: (item["path"], item["method"])),
        }
        for tag in order
    ]

    info = spec.get("info") or {}
    return {
        "meta": {
            "source": source_url,
            "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "title": info.get("title"),
            "api_version": info.get("version"),
            "openapi": spec.get("openapi"),
            "spec_sha256": _spec_digest(spec),
        },
        "categories": categories,
    }
