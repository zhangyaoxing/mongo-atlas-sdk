from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from mongo_atlas_sdk.cli import main
from mongo_atlas_sdk.crawler import SpecSourceError, extract_api_docs, load_spec
from mongo_atlas_sdk.crawler.loader import fetch_spec

FIXTURE = Path(__file__).parent / "fixtures" / "mini_openapi.json"
FIXED_TIME = "2026-01-01T00:00:00+00:00"


@pytest.fixture()
def spec() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return document


@pytest.fixture()
def docs(spec: dict[str, Any]) -> dict[str, Any]:
    return extract_api_docs(spec, source_url="test://spec", fetched_at=FIXED_TIME)


def test_categories_follow_tag_order_with_untagged_last(docs: dict[str, Any]) -> None:
    names = [category["name"] for category in docs["categories"]]

    assert names == ["Clusters", "Alerts", "Untagged"]
    assert docs["meta"]["api_version"] == "2.0"
    assert docs["meta"]["openapi"] == "3.0.1"
    assert docs["meta"]["fetched_at"] == FIXED_TIME
    assert len(docs["meta"]["spec_sha256"]) == 64
    assert set(docs["schemas"]) == {"Cluster", "ProviderSettings"}


def test_endpoints_are_sorted_by_path_and_method(docs: dict[str, Any]) -> None:
    clusters = docs["categories"][0]["endpoints"]

    assert [endpoint["operation_id"] for endpoint in clusters] == [
        "listGroupClusters",
        "createGroupCluster",
    ]
    get_cluster = clusters[0]
    assert get_cluster["method"] == "GET"
    assert get_cluster["path"] == "/api/atlas/v2/groups/{groupId}/clusters"
    assert get_cluster["summary"] == "Return All Clusters"
    assert get_cluster["tags"] == ["Clusters"]


def test_responses_are_captured_in_status_order(docs: dict[str, Any]) -> None:
    list_endpoint = docs["categories"][0]["endpoints"][0]

    assert [response["status"] for response in list_endpoint["responses"]] == ["200", "401"]
    ok = list_endpoint["responses"][0]
    assert ok["description"] == "OK"
    assert ok["content"][0]["content_type"] == "application/vnd.atlas.2024-10-23+json"
    assert ok["content"][0]["schema_ref"] == "Cluster"
    assert ok["content"][0]["schema"] == {"$ref": "#/components/schemas/Cluster"}
    assert list_endpoint["responses"][1]["content"] == []


def test_path_parameters_are_inherited_and_overridden(docs: dict[str, Any]) -> None:
    list_endpoint, create_endpoint = docs["categories"][0]["endpoints"]

    inherited = list_endpoint["parameters"]["path"][0]
    assert inherited["name"] == "groupId"
    assert inherited["description"] == "Project ID (path level)."
    assert inherited["required"] is True
    assert inherited["type"] == "string"

    overridden = create_endpoint["parameters"]["path"][0]
    assert overridden["description"] == "Project ID (operation override)."


def test_query_parameters_resolve_refs(docs: dict[str, Any]) -> None:
    envelope = docs["categories"][0]["endpoints"][0]["parameters"]["query"][0]

    assert envelope["name"] == "envelope"
    assert envelope["type"] == "boolean"
    assert envelope["required"] is False
    assert envelope["description"] == "Wrap the response in an envelope."
    assert envelope["schema"]["default"] is False


def test_body_parameters_carry_type_and_required(docs: dict[str, Any]) -> None:
    create_endpoint = docs["categories"][0]["endpoints"][1]
    body = {parameter["name"]: parameter for parameter in create_endpoint["parameters"]["body"]}

    assert set(body) == {"clusterType", "diskSizeGB", "name", "providerSettings", "tags"}
    assert body["name"]["required"] is True
    assert body["clusterType"]["type"] == "string"
    assert body["diskSizeGB"]["type"] == "number"
    assert body["diskSizeGB"]["required"] is False
    assert body["providerSettings"]["type"] == "ProviderSettings"
    assert body["tags"]["type"] == "array<string>"

    request_body = create_endpoint["request_body"]
    assert request_body["type"] == "object"
    assert request_body["required"] is True
    assert request_body["schema_ref"] == "Cluster"
    assert request_body["content_type"] == "application/vnd.atlas.2024-10-23+json"


def test_untagged_operations_get_their_own_category(docs: dict[str, Any]) -> None:
    untagged = docs["categories"][2]

    assert untagged["name"] == "Untagged"
    assert [endpoint["operation_id"] for endpoint in untagged["endpoints"]] == ["getSystemStatus"]


def test_get_endpoint_has_no_body(docs: dict[str, Any]) -> None:
    list_endpoint = docs["categories"][0]["endpoints"][0]

    assert list_endpoint["parameters"]["body"] == []
    assert list_endpoint["request_body"] is None


def test_load_spec_handles_gzip(tmp_path: Path) -> None:
    path = tmp_path / "spec.json.gz"
    path.write_bytes(gzip.compress(FIXTURE.read_bytes()))

    assert load_spec(path)["info"]["version"] == "2.0"


def test_fetch_spec_rejects_non_http_schemes() -> None:
    with pytest.raises(SpecSourceError, match="scheme"):
        fetch_spec("file:///etc/passwd")


def test_cli_crawl_writes_nested_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "nested" / "api_docs.json"

    assert main(["crawl", "--spec", str(FIXTURE), "-o", str(output)]) == 0

    written = json.loads(output.read_text(encoding="utf-8"))
    assert len(written["categories"]) == 3
    assert written["meta"]["source"] == str(FIXTURE)
    assert "3 categories, 4 endpoints" in capsys.readouterr().out


def test_cli_crawl_reports_invalid_spec(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad_spec = tmp_path / "bad.json"
    bad_spec.write_text("{not json", encoding="utf-8")

    assert main(["crawl", "--spec", str(bad_spec), "-o", str(tmp_path / "out.json")]) == 1
    assert "invalid openapi document" in capsys.readouterr().err.lower()


def test_array_body_parameters_use_item_schema() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.1",
        "info": {"title": "Array API", "version": "2.0"},
        "tags": [{"name": "Access"}],
        "paths": {
            "/api/atlas/v2/groups/{groupId}/accessList": {
                "post": {
                    "operationId": "createGroupAccessListEntriesBulk",
                    "summary": "Create Access List Entries",
                    "tags": ["Access"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["ipAddress"],
                                        "properties": {
                                            "ipAddress": {"type": "string"},
                                            "comment": {"type": "string"},
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    docs = extract_api_docs(spec, source_url="test://array")
    endpoint = docs["categories"][0]["endpoints"][0]

    assert endpoint["request_body"]["type"] == "array<object>"
    body = {parameter["name"]: parameter for parameter in endpoint["parameters"]["body"]}
    assert set(body) == {"comment", "ipAddress"}
    assert body["ipAddress"]["required"] is True
    assert body["comment"]["required"] is False
