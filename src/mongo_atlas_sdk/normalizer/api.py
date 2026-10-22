"""Normalize the raw crawl output into the generator-facing API document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mongo_atlas_sdk.normalizer.schema import SchemaNormalizer

DEFAULT_TIMESTAMP_FORMAT = "seconds"


def _normalize_parameter(normalizer: SchemaNormalizer, parameter: Any) -> dict[str, Any]:
    if not isinstance(parameter, dict):
        parameter = {}
    return {
        "name": parameter.get("name") or "",
        "required": bool(parameter.get("required", False)),
        "description": parameter.get("description") or "",
        "type": normalizer.expression(parameter.get("schema") or {}),
    }


def _normalize_body(normalizer: SchemaNormalizer, body: Any) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    return {
        "content_type": body.get("content_type") or "",
        "required": bool(body.get("required", False)),
        "description": body.get("description") or "",
        "type": normalizer.expression(body.get("schema") or {}),
    }


def _normalize_endpoint(normalizer: SchemaNormalizer, endpoint: Any) -> dict[str, Any]:
    if not isinstance(endpoint, dict):
        endpoint = {}
    parameters = endpoint.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {}
    return {
        "operation_id": endpoint.get("operation_id") or "",
        "summary": endpoint.get("summary") or "",
        "description": endpoint.get("description") or "",
        "method": endpoint.get("method") or "",
        "path": endpoint.get("path") or "",
        "tags": list(endpoint.get("tags") or []),
        "path_parameters": [
            _normalize_parameter(normalizer, parameter)
            for parameter in parameters.get("path") or []
        ],
        "query_parameters": [
            _normalize_parameter(normalizer, parameter)
            for parameter in parameters.get("query") or []
        ],
        "request_body": _normalize_body(normalizer, endpoint.get("request_body")),
    }


def normalize_api_docs(
    docs: dict[str, Any],
    *,
    normalized_at: str | None = None,
) -> dict[str, Any]:
    """Return a closed, generator-facing view of the raw crawl document."""
    schemas = docs.get("schemas")
    normalizer = SchemaNormalizer(schemas if isinstance(schemas, dict) else {})

    categories: list[dict[str, Any]] = []
    endpoint_count = 0
    for category in docs.get("categories") or []:
        if not isinstance(category, dict):
            continue
        endpoints = [
            _normalize_endpoint(normalizer, endpoint)
            for endpoint in category.get("endpoints") or []
        ]
        endpoint_count += len(endpoints)
        categories.append(
            {
                "name": category.get("name") or "",
                "description": category.get("description") or "",
                "endpoints": endpoints,
            }
        )

    meta = dict(docs.get("meta") or {})
    meta.update(
        {
            "normalized_at": normalized_at
            or datetime.now(timezone.utc).isoformat(timespec=DEFAULT_TIMESTAMP_FORMAT),
            "stats": {
                "categories": len(categories),
                "endpoints": endpoint_count,
                "types": len(normalizer.types),
            },
            "warnings": normalizer.warnings,
        }
    )
    return {"meta": meta, "types": normalizer.types, "categories": categories}
