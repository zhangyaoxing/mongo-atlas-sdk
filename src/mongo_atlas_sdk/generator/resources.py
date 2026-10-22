"""Render resource classes from templates, one method per API endpoint."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mongo_atlas_sdk.generator.naming import pascal_case, snake_case
from mongo_atlas_sdk.generator.schema import annotation
from mongo_atlas_sdk.generator.templating import docstring_text, render

_TYPING = frozenset({"Any", "Literal"})
_SUCCESS_PREFIX = "2"


def _success_type_expressions(endpoint: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    expressions: list[Mapping[str, Any]] = []
    for response in endpoint.get("responses") or []:
        status = str(response.get("status") or "")
        if not status.startswith(_SUCCESS_PREFIX):
            continue
        for content in response.get("content") or []:
            type_expr = content.get("type")
            if isinstance(type_expr, Mapping):
                expressions.append(type_expr)
    return expressions


def _response_annotation(endpoint: Mapping[str, Any], imports: set[str]) -> str:
    expressions = _success_type_expressions(endpoint)
    if not expressions:
        return "None"
    rendered = [annotation(expr, current="", imports=imports) for expr in expressions]
    return " | ".join(dict.fromkeys(rendered))


def _path_expression(path: str, path_parameters: list[Mapping[str, Any]], imports: set[str]) -> str:
    if not path_parameters:
        return json.dumps(path)
    imports.add("quote")
    rendered = path
    for parameter in path_parameters:
        raw_name = str(parameter.get("name") or "")
        variable = snake_case(raw_name)
        rendered = rendered.replace(
            "{" + raw_name + "}",
            "{quote(str(" + variable + "), safe='')}",
        )
    return "f" + json.dumps(rendered)


def _method_docstring(
    endpoint: Mapping[str, Any],
    path_parameters: list[Mapping[str, Any]],
    query_parameters: list[Mapping[str, Any]],
    body: Mapping[str, Any] | None,
) -> str:
    summary = str(endpoint.get("summary") or "").strip() or "Call the API endpoint."
    description = str(endpoint.get("description") or "").strip()
    parts = [summary]
    if description:
        parts.extend(["", description])

    arguments: list[tuple[str, str]] = []
    for parameter in path_parameters:
        arguments.append(
            (
                snake_case(str(parameter.get("name") or "")),
                str(parameter.get("description") or ""),
            )
        )
    for parameter in query_parameters:
        arguments.append(
            (
                snake_case(str(parameter.get("name") or "")),
                str(parameter.get("description") or ""),
            )
        )
    if body is not None:
        arguments.append(("body", str(body.get("description") or "")))

    if arguments:
        parts.extend(["", "Args:"])
        for name, description_text in arguments:
            collapsed = " ".join(description_text.split())
            parts.append(f"    {name}: {collapsed}" if collapsed else f"    {name}:")

    return "\n".join(parts).strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


def _render_method(endpoint: Mapping[str, Any], imports: set[str]) -> dict[str, Any]:
    operation_id = str(endpoint.get("operation_id") or "call")
    method_name = snake_case(operation_id)
    path_parameters = [
        parameter
        for parameter in (endpoint.get("path_parameters") or [])
        if isinstance(parameter, Mapping)
    ]
    query_parameters = [
        parameter
        for parameter in (endpoint.get("query_parameters") or [])
        if isinstance(parameter, Mapping)
    ]
    body = endpoint.get("request_body")
    if not isinstance(body, Mapping):
        body = None

    arguments: list[str] = ["self"]
    keyword_arguments: list[str] = []

    for parameter in path_parameters:
        parameter_type = annotation(parameter.get("type") or {}, current="", imports=imports)
        arguments.append(f"{snake_case(str(parameter.get('name') or ''))}: {parameter_type}")

    if body is not None:
        body_type = annotation(body.get("type") or {}, current="", imports=imports)
        if body.get("required"):
            arguments.append(f"body: {body_type}")
        else:
            keyword_arguments.append(f"body: {body_type} | None = None")

    for parameter in query_parameters:
        parameter_type = annotation(parameter.get("type") or {}, current="", imports=imports)
        name = snake_case(str(parameter.get("name") or ""))
        if parameter.get("required"):
            keyword_arguments.append(f"{name}: {parameter_type}")
        else:
            keyword_arguments.append(f"{name}: {parameter_type} | None = None")

    if keyword_arguments:
        arguments.append("*")
        arguments.extend(keyword_arguments)

    return_annotation = _response_annotation(endpoint, imports)
    return {
        "name": method_name,
        "arguments": arguments,
        "return_annotation": return_annotation,
        "docstring": _method_docstring(endpoint, path_parameters, query_parameters, body),
        "path": _path_expression(str(endpoint.get("path") or ""), path_parameters, imports),
        "query_params": [
            {
                "wire": str(parameter.get("name") or ""),
                "name": snake_case(str(parameter.get("name") or "")),
            }
            for parameter in query_parameters
        ],
        "has_body": body is not None,
        "http_method": str(endpoint.get("method") or "GET"),
        "response_model": return_annotation,
    }


def _import_block(imports: set[str], package: str) -> list[str]:
    lines: list[str] = []
    typing_names = sorted(_TYPING & imports)
    if typing_names:
        lines.append(f"from typing import {', '.join([*typing_names, 'TYPE_CHECKING'])}")
    else:
        lines.append("from typing import TYPE_CHECKING")
    datetime_names = sorted({"datetime", "date"} & imports)
    if datetime_names:
        lines.append(f"from datetime import {', '.join(datetime_names)}")
    if "quote" in imports:
        lines.append("from urllib.parse import quote")
    for name in sorted(imports - _TYPING - {"quote", "datetime", "date"}):
        lines.append(f"from {package}.models.{snake_case(name)} import {name}")
    return lines


def render_resource(category: Mapping[str, Any], *, package: str) -> str:
    """Render one normalized category as a resource class module."""
    class_name = pascal_case(str(category.get("name") or "Untagged"))
    imports: set[str] = set()
    methods: list[dict[str, Any]] = []
    for endpoint in category.get("endpoints") or []:
        if isinstance(endpoint, Mapping):
            methods.append(_render_method(endpoint, imports))

    return render(
        "resource.py.j2",
        class_name=class_name,
        package=package,
        imports=_import_block(imports, package),
        description=docstring_text(category.get("description"), f"Operations for {class_name}."),
        methods=methods,
    )


__all__ = ["render_resource"]
