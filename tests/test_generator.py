from __future__ import annotations

import importlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

from mongo_atlas_sdk.cli import main
from mongo_atlas_sdk.generator import LANGUAGES, GeneratorError, generate, generate_python
from mongo_atlas_sdk.generator.paths import api_path


def _docs() -> dict[str, Any]:
    return {
        "meta": {"source": "test://spec"},
        "types": {
            "Cluster": {
                "name": "Cluster",
                "kind": "object",
                "description": "A cluster.",
                "properties": {
                    "name": {
                        "required": True,
                        "description": "Cluster name.",
                        "type": {"kind": "primitive", "type": "string"},
                    },
                    "clusterType": {
                        "required": False,
                        "type": {
                            "kind": "enum",
                            "type": "string",
                            "values": ["REPLICASET", "SHARDED"],
                        },
                    },
                    "_id": {
                        "required": False,
                        "type": {"kind": "primitive", "type": "string"},
                    },
                    "diskSizeGB": {
                        "required": False,
                        "type": {"kind": "primitive", "type": "number"},
                    },
                    "tags": {
                        "required": False,
                        "type": {
                            "kind": "array",
                            "items": {"kind": "primitive", "type": "string"},
                        },
                    },
                    "settings": {
                        "required": False,
                        "type": {
                            "kind": "object",
                            "properties": {
                                "encrypted": {
                                    "required": True,
                                    "type": {"kind": "primitive", "type": "boolean"},
                                }
                            },
                            "additional_properties": None,
                        },
                    },
                },
                "additional_properties": None,
            },
            "PaginatedClusters": {
                "name": "PaginatedClusters",
                "kind": "object",
                "properties": {
                    "results": {
                        "required": False,
                        "type": {
                            "kind": "array",
                            "items": {"kind": "reference", "name": "Cluster"},
                        },
                    }
                },
                "additional_properties": None,
            },
            "ClusterType": {
                "name": "ClusterType",
                "kind": "enum",
                "type": "string",
                "values": ["REPLICASET", "SHARDED"],
                "description": "Cluster type.",
            },
            "Node": {
                "name": "Node",
                "kind": "object",
                "properties": {
                    "children": {
                        "required": False,
                        "type": {
                            "kind": "array",
                            "items": {"kind": "reference", "name": "Node"},
                        },
                    }
                },
                "additional_properties": None,
            },
            "Operator": {
                "name": "Operator",
                "kind": "enum",
                "type": "string",
                "values": ["<", ">", "=="],
            },
        },
        "categories": [
            {
                "name": "Clusters",
                "description": "Manage clusters.",
                "endpoints": [
                    {
                        "operation_id": "createGroupCluster",
                        "summary": "Create One Cluster",
                        "description": "Create a cluster.",
                        "method": "POST",
                        "path": "/api/atlas/v2/groups/{groupId}/clusters",
                        "tags": ["Clusters"],
                        "path_parameters": [
                            {
                                "name": "groupId",
                                "required": True,
                                "description": "Project ID.",
                                "type": {"kind": "primitive", "type": "string"},
                            }
                        ],
                        "query_parameters": [
                            {
                                "name": "envelope",
                                "required": False,
                                "description": "Wrap the response.",
                                "type": {"kind": "primitive", "type": "boolean"},
                            }
                        ],
                        "request_body": {
                            "content_type": "application/vnd.atlas.2024-10-23+json",
                            "required": True,
                            "description": "The cluster.",
                            "type": {"kind": "reference", "name": "Cluster"},
                        },
                        "responses": [
                            {
                                "status": "200",
                                "description": "OK",
                                "content": [
                                    {
                                        "content_type": "application/vnd.atlas.2024-08-05+json",
                                        "type": {
                                            "kind": "reference",
                                            "name": "PaginatedClusters",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "operation_id": "getNode",
                        "summary": "Get One Node",
                        "description": "",
                        "method": "GET",
                        "path": "/nodes/{nodeId}",
                        "tags": ["Clusters"],
                        "path_parameters": [
                            {
                                "name": "nodeId",
                                "required": True,
                                "description": "",
                                "type": {"kind": "primitive", "type": "string"},
                            }
                        ],
                        "query_parameters": [],
                        "request_body": None,
                        "responses": [
                            {
                                "status": "200",
                                "description": "OK",
                                "content": [
                                    {
                                        "content_type": "application/vnd.atlas.2024-08-05+json",
                                        "type": {"kind": "reference", "name": "Node"},
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ],
    }


def test_generate_python_writes_models_resources_and_client(tmp_path: Path) -> None:
    package = f"gen_sdk_{uuid.uuid4().hex[:8]}"
    stats = generate_python(_docs(), tmp_path / package, package=package)

    assert stats == {"models": 6, "resources": 1, "methods": 2}
    model = (tmp_path / package / "models" / "cluster.py").read_text(encoding="utf-8")
    assert "class Cluster(BaseModel):" in model
    assert "name: str = Field(description=" in model
    assert 'cluster_type: Literal["REPLICASET", "SHARDED"] | None = Field(' in model
    assert 'alias="clusterType"' in model
    assert 'id: str | None = Field(default=None, alias="_id")' in model
    assert 'disk_size_gb: float | None = Field(default=None, alias="diskSizeGB")' in model
    assert "tags: list[str] | None = None" in model
    assert "settings: ClusterSettings | None = None" in model

    settings = (tmp_path / package / "models" / "cluster_settings.py").read_text(encoding="utf-8")
    assert "class ClusterSettings(BaseModel):" in settings
    assert "encrypted: bool" in settings

    node = (tmp_path / package / "models" / "node.py").read_text(encoding="utf-8")
    assert "Node.model_rebuild()" in node

    operator = (tmp_path / package / "models" / "operator.py").read_text(encoding="utf-8")
    assert 'LT = "<"' in operator
    assert 'GT = ">"' in operator
    assert 'EQ = "=="' in operator

    resource = (tmp_path / package / "resources" / "clusters.py").read_text(encoding="utf-8")
    assert "class Clusters:" in resource
    assert "def create_group_cluster(" in resource
    assert "group_id: str," in resource
    assert "body: Cluster," in resource
    assert "envelope: bool | None = None," in resource
    assert "path = f\"/groups/{quote(str(group_id), safe='')}/clusters\"" in resource
    assert "response_model=PaginatedClusters," in resource
    assert "def get_node(" in resource

    client = (tmp_path / package / "client.py").read_text(encoding="utf-8")
    assert f"from {package}.resources.clusters import Clusters" in client
    assert 'DEFAULT_ACCEPT = "application/vnd.atlas.2024-08-05+json"' in client
    assert 'DEFAULT_CONTENT_TYPE = "application/vnd.atlas.2024-10-23+json"' in client
    assert 'accept="application/vnd.atlas.2024-08-05+json"' in resource
    assert 'content_type="application/vnd.atlas.2024-10-23+json"' in resource
    assert "self.clusters = Clusters(self)" in client


def test_generated_package_imports_and_serializes(tmp_path: Path) -> None:
    package = f"gen_sdk_{uuid.uuid4().hex[:8]}"
    generate_python(_docs(), tmp_path / package, package=package)
    sys.path.insert(0, str(tmp_path))
    try:
        importlib.invalidate_caches()
        client_module = importlib.import_module(f"{package}.client")
        client = client_module.AtlasClient(public_key="public", private_key="private")
        assert client.clusters is not None

        models = importlib.import_module(f"{package}.models.cluster")
        cluster = models.Cluster(
            name="example",
            cluster_type="SHARDED",
            id="abc",
            disk_size_gb=10.0,
            settings={"encrypted": True},
        )
        assert cluster.model_dump(by_alias=True, exclude_none=True) == {
            "name": "example",
            "clusterType": "SHARDED",
            "_id": "abc",
            "diskSizeGB": 10.0,
            "settings": {"encrypted": True},
        }

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={"results": [{"name": "created"}]})

        client._http.close()
        client._http = httpx.Client(
            base_url="https://example.test/api/atlas/v2",
            transport=httpx.MockTransport(handler),
        )
        result = client.clusters.create_group_cluster(
            group_id="g 1",
            body=models.Cluster(name="created"),
            envelope=True,
        )
        assert captured[0].method == "POST"
        assert "/api/atlas/v2/groups/g%201/clusters" in str(captured[0].url)
        assert captured[0].url.params["envelope"] == "true"
        assert json.loads(captured[0].content) == {"name": "created"}
        assert type(result).__name__ == "PaginatedClusters"
        assert result.results[0].name == "created"
    finally:
        sys.path.remove(str(tmp_path))
        for name in list(sys.modules):
            if name == package or name.startswith(f"{package}."):
                del sys.modules[name]


def test_cli_pygen_writes_package(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "normalized.json"
    source.write_text(json.dumps(_docs()), encoding="utf-8")
    output = tmp_path / "pkg"

    assert main(["pygen", "-i", str(source), "-o", str(output), "--package", "demo"]) == 0

    assert (output / "client.py").exists()
    assert "6 models, 1 resources, 2 methods" in capsys.readouterr().out


def _load_generated_client(tmp_path: Path) -> tuple[str, Any]:
    package = f"gen_sdk_{uuid.uuid4().hex[:8]}"
    generate_python(_docs(), tmp_path / package, package=package)
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    return package, importlib.import_module(f"{package}.client")


def _forget_package(package: str, tmp_path: Path) -> None:
    sys.path.remove(str(tmp_path))
    for name in list(sys.modules):
        if name == package or name.startswith(f"{package}."):
            del sys.modules[name]


def test_generated_client_oauth2_token_flow(tmp_path: Path) -> None:
    package, client_module = _load_generated_client(tmp_path)
    try:
        client = client_module.AtlasClient(client_id="cid", client_secret="secret")
        assert client.auth_mode == "oauth2"
        token_requests: list[httpx.Request] = []
        api_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/oauth/token":
                token_requests.append(request)
                return httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
            api_requests.append(request)
            return httpx.Response(200, json={"results": []})

        client._http.close()
        client._http = httpx.Client(
            base_url="https://example.test/api/atlas/v2",
            transport=httpx.MockTransport(handler),
        )
        body = importlib.import_module(f"{package}.models.cluster").Cluster(name="example")
        client.clusters.create_group_cluster(group_id="g1", body=body)
        client.clusters.create_group_cluster(group_id="g1", body=body)

        assert len(token_requests) == 1
        assert len(api_requests) == 2
        assert api_requests[0].headers["authorization"] == "Bearer token-1"
        form = token_requests[0].content.decode()
        assert "grant_type=client_credentials" in form
        assert "client_id=cid" in form
        assert "client_secret=secret" in form
    finally:
        _forget_package(package, tmp_path)


def test_generated_client_refreshes_oauth_token_on_401(tmp_path: Path) -> None:
    package, client_module = _load_generated_client(tmp_path)
    try:
        client = client_module.AtlasClient(client_id="cid", client_secret="secret")
        tokens: list[httpx.Request] = []
        api_requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/oauth/token":
                tokens.append(request)
                return httpx.Response(
                    200,
                    json={"access_token": f"token-{len(tokens)}", "expires_in": 3600},
                )
            api_requests.append(request)
            if len(api_requests) == 1:
                return httpx.Response(401, json={"error": "expired"})
            return httpx.Response(200, json={"results": []})

        client._http.close()
        client._http = httpx.Client(
            base_url="https://example.test/api/atlas/v2",
            transport=httpx.MockTransport(handler),
        )
        body = importlib.import_module(f"{package}.models.cluster").Cluster(name="example")
        client.clusters.create_group_cluster(group_id="g1", body=body)

        assert len(tokens) == 2
        assert len(api_requests) == 2
        assert api_requests[0].headers["authorization"] == "Bearer token-1"
        assert api_requests[1].headers["authorization"] == "Bearer token-2"
    finally:
        _forget_package(package, tmp_path)


def test_generated_client_validates_auth_arguments(tmp_path: Path) -> None:
    package, client_module = _load_generated_client(tmp_path)
    try:
        with pytest.raises(ValueError, match="not both"):
            client_module.AtlasClient(
                public_key="public",
                private_key="private",
                client_id="client",
                client_secret="secret",
            )
        with pytest.raises(ValueError, match="client_id and client_secret"):
            client_module.AtlasClient(client_id="client")
        with pytest.raises(ValueError, match="public_key and private_key"):
            client_module.AtlasClient(public_key="public")
    finally:
        _forget_package(package, tmp_path)


def test_registry_exposes_python_target() -> None:
    target = LANGUAGES["python"]

    assert target.default_package == "pyatlassdk"
    assert str(target.default_output).endswith("pyatlassdk/src/pyatlassdk")


def test_generate_dispatches_by_language(tmp_path: Path) -> None:
    stats = generate("python", _docs(), output_root=tmp_path / "pkg", package="pkg")

    assert stats == {"models": 6, "resources": 1, "methods": 2}
    assert (tmp_path / "pkg" / "client.py").exists()


def test_generate_rejects_unknown_language(tmp_path: Path) -> None:
    with pytest.raises(GeneratorError, match="Unsupported language"):
        generate("ruby", _docs(), output_root=tmp_path / "pkg", package="pkg")


def test_cli_generate_accepts_language(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "normalized.json"
    source.write_text(json.dumps(_docs()), encoding="utf-8")
    output = tmp_path / "pkg"

    assert (
        main(
            [
                "generate",
                "--language",
                "python",
                "-i",
                str(source),
                "-o",
                str(output),
                "--package",
                "demo",
            ]
        )
        == 0
    )

    assert (output / "client.py").exists()
    assert "6 models, 1 resources, 2 methods" in capsys.readouterr().out


def test_api_path_is_relative_to_base_url() -> None:
    assert api_path("/api/atlas/v2/groups/x/clusters") == "/groups/x/clusters"
    assert api_path("/api/atlas/v2") == "/"
    assert api_path("/health") == "/health"
