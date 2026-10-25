from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mongo_atlas_sdk.cli import main
from mongo_atlas_sdk.normalizer import normalize_api_docs, pascal_case


def _docs(
    schemas: dict[str, Any],
    body_schema: dict[str, Any],
    parameters: dict[str, Any] | None = None,
    responses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "meta": {"source": "test://spec", "api_version": "2.0"},
        "schemas": schemas,
        "categories": [
            {
                "name": "Test",
                "description": "",
                "endpoints": [
                    {
                        "operation_id": "op",
                        "summary": "Op",
                        "description": "",
                        "method": "POST",
                        "path": "/x",
                        "tags": ["Test"],
                        "parameters": parameters or {"path": [], "query": [], "body": []},
                        "request_body": {
                            "content_type": "application/json",
                            "type": "object",
                            "required": True,
                            "description": "",
                            "schema_ref": None,
                            "schema": body_schema,
                        },
                        "responses": responses or [],
                    }
                ],
            }
        ],
    }


def _endpoint(docs: dict[str, Any]) -> dict[str, Any]:
    endpoint: dict[str, Any] = docs["categories"][0]["endpoints"][0]
    return endpoint


def test_object_properties_are_normalized() -> None:
    schemas = {
        "Thing": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer", "format": "int64", "description": "Identifier."},
                "name": {"type": "string"},
            },
        }
    }
    docs = normalize_api_docs(
        _docs(schemas, {"$ref": "#/components/schemas/Thing"}),
        normalized_at="2026-01-01T00:00:00+00:00",
    )

    thing = docs["types"]["Thing"]
    assert thing["kind"] == "object"
    assert thing["properties"]["id"]["required"] is True
    assert thing["properties"]["id"]["description"] == "Identifier."
    assert thing["properties"]["id"]["type"] == {
        "kind": "primitive",
        "type": "integer",
        "format": "int64",
    }
    assert thing["properties"]["name"]["required"] is False
    assert _endpoint(docs)["request_body"]["type"] == {"kind": "reference", "name": "Thing"}
    assert docs["meta"]["stats"] == {"categories": 1, "endpoints": 1, "types": 1}


def test_all_of_merges_properties_and_required() -> None:
    schemas = {
        "Base": {
            "type": "object",
            "required": ["a"],
            "properties": {"a": {"type": "string"}},
        },
        "Extended": {
            "allOf": [
                {"$ref": "#/components/schemas/Base"},
                {
                    "type": "object",
                    "required": ["b"],
                    "properties": {"b": {"type": "integer"}},
                    "description": "Extended.",
                },
            ]
        },
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Extended"}))

    extended = docs["types"]["Extended"]
    assert extended["kind"] == "object"
    assert set(extended["properties"]) == {"a", "b"}
    assert extended["properties"]["a"]["required"] is True
    assert extended["properties"]["b"]["required"] is True
    assert extended["description"] == "Extended."


def test_one_of_becomes_a_union() -> None:
    schemas = {
        "A": {"type": "object", "properties": {"a": {"type": "string"}}},
        "B": {"type": "object", "properties": {"b": {"type": "string"}}},
        "Choice": {
            "oneOf": [{"$ref": "#/components/schemas/A"}, {"$ref": "#/components/schemas/B"}]
        },
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Choice"}))

    choice = docs["types"]["Choice"]
    assert choice["kind"] == "union"
    assert choice["mode"] == "oneOf"
    assert [variant["name"] for variant in choice["variants"]] == ["A", "B"]


def test_named_enum_is_preserved() -> None:
    schemas = {
        "Color": {"type": "string", "enum": ["red", "blue"], "description": "Colour."},
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Color"}))

    color = docs["types"]["Color"]
    assert color["kind"] == "enum"
    assert color["type"] == "string"
    assert color["values"] == ["red", "blue"]
    assert color["description"] == "Colour."


def test_recursive_schema_stays_a_reference() -> None:
    schemas = {
        "Node": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "children": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/Node"},
                },
            },
        }
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Node"}))

    children = docs["types"]["Node"]["properties"]["children"]["type"]
    assert children["kind"] == "array"
    assert children["items"] == {"kind": "reference", "name": "Node"}
    assert docs["meta"]["stats"]["types"] == 1


def test_inline_object_keeps_additional_properties() -> None:
    docs = normalize_api_docs(
        _docs({}, {"type": "object", "additionalProperties": {"type": "string"}})
    )

    body_type = _endpoint(docs)["request_body"]["type"]
    assert body_type["kind"] == "object"
    assert body_type["additional_properties"] == {"kind": "primitive", "type": "string"}


def test_unresolved_ref_yields_any_and_warning() -> None:
    docs = normalize_api_docs(_docs({}, {"$ref": "#/components/schemas/Missing"}))

    assert _endpoint(docs)["request_body"]["type"] == {"kind": "any"}
    assert any("Missing" in warning for warning in docs["meta"]["warnings"])


def test_nullable_from_flag_and_type_list() -> None:
    schemas = {
        "Thing": {
            "type": "object",
            "properties": {
                "a": {"type": "string", "nullable": True},
                "b": {"type": ["string", "null"]},
            },
        }
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Thing"}))

    properties = docs["types"]["Thing"]["properties"]
    assert properties["a"]["type"]["nullable"] is True
    assert properties["b"]["type"]["nullable"] is True


def test_name_collisions_get_a_suffix() -> None:
    schemas = {
        "foo-bar": {"type": "object", "properties": {"a": {"type": "string"}}},
        "foo_bar": {"type": "object", "properties": {"b": {"type": "string"}}},
    }
    body = {
        "type": "object",
        "properties": {
            "x": {"$ref": "#/components/schemas/foo-bar"},
            "y": {"$ref": "#/components/schemas/foo_bar"},
        },
    }
    docs = normalize_api_docs(_docs(schemas, body))

    assert set(docs["types"]) == {"FooBar", "FooBar2"}


def test_path_parameter_is_normalized() -> None:
    parameters = {
        "path": [
            {
                "name": "id",
                "type": "string",
                "required": True,
                "description": "The identifier.",
                "schema": {"type": "string", "format": "24-hex"},
            }
        ],
        "query": [],
        "body": [],
    }
    docs = normalize_api_docs(_docs({}, {"type": "object"}, parameters))

    parameter = _endpoint(docs)["path_parameters"][0]
    assert parameter["name"] == "id"
    assert parameter["required"] is True
    assert parameter["type"] == {"kind": "primitive", "type": "string", "format": "24-hex"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("clusterDescription", "ClusterDescription"),
        ("foo-bar", "FooBar"),
        ("foo_bar", "FooBar"),
        ("2024thing", "Type2024thing"),
        ("---", "Anonymous"),
    ],
)
def test_pascal_case(raw: str, expected: str) -> None:
    assert pascal_case(raw) == expected


def test_cli_normalize_writes_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = _docs(
        {"Thing": {"type": "object", "properties": {"id": {"type": "string"}}}},
        {"$ref": "#/components/schemas/Thing"},
    )
    input_path = tmp_path / "api_docs.json"
    input_path.write_text(json.dumps(raw), encoding="utf-8")
    output_path = tmp_path / "normalized_api_docs.json"

    assert main(["normalize", "-i", str(input_path), "-o", str(output_path)]) == 0

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["types"]["Thing"]["kind"] == "object"
    assert "1 categories, 1 endpoints, 1 types" in capsys.readouterr().out


def test_cli_normalize_rejects_invalid_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bad = tmp_path / "api_docs.json"
    bad.write_text("{not json", encoding="utf-8")

    assert main(["normalize", "-i", str(bad), "-o", str(tmp_path / "out.json")]) == 1
    assert "invalid json" in capsys.readouterr().err.lower()


def test_cli_normalize_requires_schema_section(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw: dict[str, Any] = {"meta": {}, "categories": []}
    path = tmp_path / "api_docs.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    assert main(["normalize", "-i", str(path), "-o", str(tmp_path / "out.json")]) == 1
    assert "re-run" in capsys.readouterr().err


def test_alias_chain_resolves_to_final_type() -> None:
    schemas = {
        "Alias": {"$ref": "#/components/schemas/Real"},
        "Real": {"type": "object", "properties": {"x": {"type": "string"}}},
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Alias"}))

    assert set(docs["types"]) == {"Real"}
    assert _endpoint(docs)["request_body"]["type"] == {"kind": "reference", "name": "Real"}


def test_all_of_self_reference_does_not_recurse() -> None:
    schemas = {
        "Loop": {
            "allOf": [
                {"$ref": "#/components/schemas/Loop"},
                {"type": "object", "properties": {"x": {"type": "string"}}},
            ]
        }
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Loop"}))

    loop = docs["types"]["Loop"]
    assert loop["kind"] == "object"
    assert set(loop["properties"]) == {"x"}


def test_named_array_becomes_an_alias() -> None:
    schemas = {"Names": {"type": "array", "items": {"type": "string"}}}
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Names"}))

    names = docs["types"]["Names"]
    assert names["kind"] == "alias"
    assert names["target"] == {
        "kind": "array",
        "items": {"kind": "primitive", "type": "string"},
    }


def test_additional_properties_false_and_defaults() -> None:
    body = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "limit": {"type": "integer", "format": "int64", "default": 10},
        },
    }
    docs = normalize_api_docs(_docs({}, body))

    body_type = _endpoint(docs)["request_body"]["type"]
    assert body_type["additional_properties"] is False
    assert body_type["properties"]["limit"]["type"] == {
        "kind": "primitive",
        "type": "integer",
        "format": "int64",
        "default": 10,
    }


def test_type_list_becomes_a_union() -> None:
    body = {"type": "object", "properties": {"value": {"type": ["string", "integer"]}}}
    docs = normalize_api_docs(_docs({}, body))

    value_type = _endpoint(docs)["request_body"]["type"]["properties"]["value"]["type"]
    assert value_type["kind"] == "union"
    assert value_type["mode"] == "anyOf"
    assert {variant["type"] for variant in value_type["variants"]} == {"string", "integer"}


def test_discriminator_is_preserved() -> None:
    schemas = {
        "A": {"type": "object", "properties": {"a": {"type": "string"}}},
        "B": {"type": "object", "properties": {"b": {"type": "string"}}},
        "Choice": {
            "oneOf": [
                {"$ref": "#/components/schemas/A"},
                {"$ref": "#/components/schemas/B"},
            ],
            "discriminator": {"propertyName": "kind"},
        },
    }
    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Choice"}))

    assert docs["types"]["Choice"]["discriminator"] == "kind"


def test_cli_normalize_reports_missing_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["normalize", "-i", str(tmp_path / "missing.json")]) == 1
    assert "cannot read" in capsys.readouterr().err.lower()


def test_cli_normalize_rejects_non_object(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")

    assert main(["normalize", "-i", str(path), "-o", str(tmp_path / "out.json")]) == 1
    assert "json object" in capsys.readouterr().err.lower()


def test_responses_are_normalized() -> None:
    schemas = {"Thing": {"type": "object", "properties": {"id": {"type": "string"}}}}
    responses: list[dict[str, Any]] = [
        {
            "status": "200",
            "description": "OK",
            "content": [
                {
                    "content_type": "application/json",
                    "schema_ref": "Thing",
                    "schema": {"$ref": "#/components/schemas/Thing"},
                }
            ],
        },
        {"status": "204", "description": "No content", "content": []},
    ]
    docs = normalize_api_docs(_docs(schemas, {"type": "object"}, responses=responses))

    normalized = _endpoint(docs)["responses"]
    assert [response["status"] for response in normalized] == ["200", "204"]
    assert normalized[0]["content"][0]["type"] == {"kind": "reference", "name": "Thing"}
    assert normalized[1]["content"] == []
    assert docs["meta"]["stats"]["types"] == 1


def test_const_becomes_single_value_enum() -> None:
    docs = normalize_api_docs(
        _docs(
            {
                "Thing": {
                    "type": "object",
                    "properties": {"kind": {"const": "API"}},
                }
            },
            {"$ref": "#/components/schemas/Thing"},
        )
    )

    kind = docs["types"]["Thing"]["properties"]["kind"]["type"]
    assert kind == {"kind": "enum", "type": "string", "values": ["API"], "const": True}


def test_nested_refs_are_resolved() -> None:
    schemas = {
        "Logs": {
            "Parts": {
                "Base": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                }
            },
            "API": {
                "allOf": [
                    {"$ref": "#/components/schemas/Logs/Parts/Base"},
                    {
                        "type": "object",
                        "properties": {"kind": {"const": "API"}},
                    },
                ]
            },
        }
    }

    docs = normalize_api_docs(_docs(schemas, {"$ref": "#/components/schemas/Logs/API"}))

    assert docs["meta"]["warnings"] == []
    assert "LogsAPI" in docs["types"]
    assert set(docs["types"]["LogsAPI"]["properties"]) == {"id", "kind"}


def test_null_schema_becomes_a_null_primitive() -> None:
    docs = normalize_api_docs(
        _docs(
            {},
            {
                "type": "object",
                "properties": {"value": {"type": "null"}},
            },
        )
    )

    value = docs["categories"][0]["endpoints"][0]["request_body"]["type"]["properties"]["value"]
    assert value["type"] == {"kind": "primitive", "type": "null"}


def test_scalar_all_of_merges_enum_values() -> None:
    schemas = {
        "AppEnvironment": {
            "type": "string",
            "enum": ["development", "production"],
        },
        "NullableAppEnvironment": {
            "allOf": [
                {"type": "string", "enum": ["", "development"]},
                {"$ref": "#/components/schemas/AppEnvironment"},
            ]
        },
    }

    docs = normalize_api_docs(
        _docs(schemas, {"$ref": "#/components/schemas/NullableAppEnvironment"})
    )

    nullable = docs["types"]["NullableAppEnvironment"]
    assert nullable["kind"] == "enum"
    assert nullable["values"] == ["", "development", "production"]
