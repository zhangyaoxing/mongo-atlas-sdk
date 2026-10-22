"""Render resource classes with one method per API endpoint."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from mongo_atlas_sdk.generator.naming import docstring_lines, pascal_case, snake_case
from mongo_atlas_sdk.generator.schema import annotation

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
) -> list[str]:
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

    text = "\n".join(parts).strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    lines = ['        """']
    lines.extend(f"        {line}" if line else "" for line in text.splitlines())
    lines.append('        """')
    return lines


def _render_method(endpoint: Mapping[str, Any], imports: set[str]) -> list[str]:
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

    arguments: list[str] = ["        self,"]
    keyword_arguments: list[str] = []

    for parameter in path_parameters:
        parameter_type = annotation(parameter.get("type") or {}, current="", imports=imports)
        arguments.append(
            f"        {snake_case(str(parameter.get('name') or ''))}: {parameter_type},"
        )

    if body is not None:
        body_type = annotation(body.get("type") or {}, current="", imports=imports)
        if body.get("required"):
            arguments.append(f"        body: {body_type},")
        else:
            keyword_arguments.append(f"        body: {body_type} | None = None,")

    for parameter in query_parameters:
        parameter_type = annotation(parameter.get("type") or {}, current="", imports=imports)
        name = snake_case(str(parameter.get("name") or ""))
        if parameter.get("required"):
            keyword_arguments.append(f"        {name}: {parameter_type},")
        else:
            keyword_arguments.append(f"        {name}: {parameter_type} | None = None,")

    if keyword_arguments:
        arguments.append("        *,")
        arguments.extend(keyword_arguments)

    return_annotation = _response_annotation(endpoint, imports)

    lines = [f"    def {method_name}("]
    lines.extend(arguments)
    lines.append(f"    ) -> {return_annotation}:")
    lines.extend(_method_docstring(endpoint, path_parameters, query_parameters, body))
    lines.append(
        f"        path = {_path_expression(str(endpoint.get('path') or ''), path_parameters, imports)}"
    )

    if query_parameters:
        lines.append("        params = {")
        for parameter in query_parameters:
            wire_name = str(parameter.get("name") or "")
            lines.append(f"            {json.dumps(wire_name)}: {snake_case(wire_name)},")
        lines.append("        }")

    lines.append("        return self._client.request(")
    lines.append(f"            method={json.dumps(str(endpoint.get('method') or 'GET'))},")
    lines.append("            path=path,")
    if query_parameters:
        lines.append("            params=params,")
    if body is not None:
        lines.append("            json=body,")
    lines.append(
        "            response_model=None,"
        if return_annotation == "None"
        else f"            response_model={return_annotation},"
    )
    lines.append("        )")
    return lines


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
    methods: list[list[str]] = []
    for endpoint in category.get("endpoints") or []:
        if isinstance(endpoint, Mapping):
            methods.append(_render_method(endpoint, imports))

    lines = [
        f'"""Generated resource for {class_name}. Do not edit manually."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    lines.extend(_import_block(imports, package))
    lines.extend(
        [
            "",
            "if TYPE_CHECKING:",
            f"    from {package}.client import AtlasClient",
            "",
            "",
            f"class {class_name}:",
        ]
    )
    lines.extend(
        docstring_lines(
            category.get("description") or f"Operations for {class_name}.",
            "    ",
        )
    )
    lines.extend(
        [
            "",
            "    def __init__(self, client: AtlasClient) -> None:",
            "        self._client = client",
            "",
        ]
    )
    for method_lines in methods:
        lines.extend(method_lines)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["render_resource"]
