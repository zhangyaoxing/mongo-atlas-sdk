[![CI](https://github.com/zhangyaoxing/mongo-atlas-sdk/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/zhangyaoxing/mongo-atlas-sdk/actions/workflows/ci.yml)

# mongo-atlas-sdk

MongoDB Atlas SDK generator and CLI (Python ≥ 3.10). It generates Python SDKs for the Atlas Administration API v2 and the App Services Admin API v3; both are published together as [pyatlassdk](https://pypi.org/project/pyatlassdk/).

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency and virtualenv management

## Quick start

```bash
uv sync                # create .venv and install dependencies
make pipeline          # both APIs: crawl -> normalize -> generate
# or run one API at a time:
make pipeline-admin    # .data/api_docs.json -> pyatlassdk/admin
make pipeline-app      # .data/api_docs.app.json -> pyatlassdk/app
```

## Common commands

| Command | Description |
| --- | --- |
| `make install` / `uv sync` | Install dependencies (including the dev group) |
| `make lint` | Run ruff |
| `make format` | Format and auto-fix with ruff |
| `make typecheck` | Run mypy in strict mode |
| `make test` | Run pytest |
| `make coverage` | Run pytest with a coverage report |
| `make check` | Run the same checks as CI |
| `make build` | Build sdist / wheel into `dist/` |
| `make lock` | Refresh `uv.lock` |
| `make crawl` / `make crawl-app` | Fetch the Admin API / App Services spec |
| `make normalize` / `make normalize-app` | Normalize the Admin / App Services spec |
| `make pygen` / `make pygen-app` | Generate the Admin / App Services SDK |
| `make pipeline` | Run both API pipelines |
| `make pipeline-admin` / `make pipeline-app` | Run one API pipeline |
| `uv run mongo-atlas crawl --api app` | CLI: crawl a specific API (`admin` or `app`) |
| `uv run mongo-atlas normalize --api app` | CLI: normalize a specific API |
| `uv run mongo-atlas pygen --api app` | CLI: generate a specific API |

## Crawling the API docs

Both documentation sites render their content from official OpenAPI documents, which are offered as downloads at the same sources:

| API | OpenAPI document | Version | Raw output |
| --- | --- | --- | --- |
| Atlas Administration API v2 | `https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2.json` | 3.0.1 | `.data/api_docs.json` |
| App Services Admin API v3 | `https://www.mongodb.com/docs/api/doc/atlas-app-services-admin-api-v3.json` | 3.1.0 | `.data/api_docs.app.json` |

The crawler therefore parses these JSON documents directly instead of rendering the pages with Playwright: the fields (`type` / `required` / `description`) are identical, but only one request is needed and the structure is stable. A full crawl takes about 2 seconds.

```bash
uv run mongo-atlas crawl                       # Admin API -> .data/api_docs.json
uv run mongo-atlas crawl --api app             # App Services -> .data/api_docs.app.json
uv run mongo-atlas crawl --api app --spec local.json   # local OpenAPI file
uv run mongo-atlas crawl --api app -o /tmp/docs.json   # custom output path
```

Output `.data/api_docs.json` (`.data/` is git-ignored):

```json
{
  "meta": {
    "source": "https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2.json",
    "fetched_at": "2026-10-22T12:22:00+00:00",
    "title": "MongoDB Atlas Administration API",
    "api_version": "2.0",
    "openapi": "3.0.1",
    "spec_sha256": "..."
  },
  "schemas": {
    "ClusterDescription20240805": {"type": "object", "properties": {"...": "..."}}
  },
  "categories": [
    {
      "name": "Clusters",
      "description": "...",
      "endpoints": [
        {
          "operation_id": "createGroupCluster",
          "summary": "Create One Cluster in One Project",
          "description": "...",
          "method": "POST",
          "path": "/api/atlas/v2/groups/{groupId}/clusters",
          "tags": ["Clusters"],
          "parameters": {
            "path": [{"name": "groupId", "type": "string", "required": true, "description": "...", "schema": {}}],
            "query": [],
            "body": [{"name": "name", "type": "string", "required": false, "description": "...", "schema": {}}]
          },
          "request_body": {
            "content_type": "application/vnd.atlas.2024-10-23+json",
            "type": "object",
            "required": true,
            "description": "...",
            "schema_ref": "ClusterDescription20240805",
            "schema": {"$ref": "#/components/schemas/ClusterDescription20240805"}
          },
          "responses": [
            {
              "status": "200",
              "description": "OK",
              "content": [
                {
                  "content_type": "application/vnd.atlas.2024-08-05+json",
                  "schema_ref": "PaginatedClusterDescription20240805",
                  "schema": {"$ref": "#/components/schemas/PaginatedClusterDescription20240805"}
                }
              ]
            },
            {"status": "401", "description": "Unauthorized.", "content": []}
          ]
        }
      ]
    }
  ]
}
```

Conventions:

- The top-level categories mirror the spec `tags`, which are the section titles on the docs site (and the future class names); `operation_id` is the stable source for method names and `summary` matches the endpoint page title.
- Path and query parameters come straight from the spec; parameter-level `$ref` values are resolved and operation-level parameters override path-level ones with the same name.
- Body parameters are the top-level schema properties; for array bodies they come from `items`. The original `$ref` is kept in `schema` so the normalization stage can expand `allOf` / `oneOf` and nested objects later.
- A few `oneOf` bodies (such as `GroupAlertsConfig`) have no single property list, so only the raw schema is kept.
- `responses` are sorted by status code (numeric ascending, `default` last). Every status keeps all media types and their original schemas; error responses (401/403/404/429/500) are included.
- `schemas` holds every raw schema definition from the spec, so `normalize` can resolve `$ref` from `api_docs.json` alone.
- `meta.spec_sha256` ties the normalized output to the exact version of the docs.

## Normalizing the API docs

```bash
uv run mongo-atlas normalize                    # read .data/api_docs.json and write the result
uv run mongo-atlas normalize -i raw.json -o out.json
```

The normalization stage:

- resolves `$ref` (including alias chains and cycle detection) and keeps only types reachable from request bodies or responses;
- merges `allOf` properties, `required` flags, and descriptions;
- turns `oneOf` / `anyOf` into `union` types and preserves `discriminator`;
- normalizes type names to PascalCase and appends a numeric suffix on collisions;
- converts arrays, inline objects, `additionalProperties`, `enum`, `nullable`, `format` / `default` into closed type expressions.

`--api app` normalizes the App Services document into `.data/normalized_api_docs.app.json`. That spec is OpenAPI 3.1, so the normalizer also handles `const`, `type: "null"`, and nested `$ref` targets such as `#/components/schemas/Logs/API`.

Output structure (`.data/normalized_api_docs.json`, Admin API):

```json
{
  "meta": {
    "source": "...",
    "spec_sha256": "...",
    "normalized_at": "2026-10-22T12:32:00+00:00",
    "stats": {"categories": 55, "endpoints": 526, "types": 1024},
    "warnings": []
  },
  "types": {
    "ClusterDescription20240805": {
      "name": "ClusterDescription20240805",
      "kind": "object",
      "description": "...",
      "properties": {
        "name": {
          "required": false,
          "description": "...",
          "type": {"kind": "primitive", "type": "string"}
        },
        "clusterType": {
          "required": false,
          "type": {
            "kind": "enum",
            "type": "string",
            "values": ["REPLICASET", "SHARDED", "GEOSHARDED"]
          }
        }
      },
      "additional_properties": null
    }
  },
  "categories": [
    {
      "name": "Clusters",
      "endpoints": [
        {
          "operation_id": "createGroupCluster",
          "method": "POST",
          "path": "/api/atlas/v2/groups/{groupId}/clusters",
          "path_parameters": [
            {"name": "groupId", "required": true, "description": "...", "type": {"kind": "primitive", "type": "string"}}
          ],
          "query_parameters": [],
          "request_body": {
            "content_type": "application/vnd.atlas.2024-10-23+json",
            "required": true,
            "description": "...",
            "type": {"kind": "reference", "name": "ClusterDescription20240805"}
          },
          "responses": [
            {
              "status": "200",
              "description": "OK",
              "content": [
                {
                  "content_type": "application/vnd.atlas.2024-08-05+json",
                  "type": {"kind": "reference", "name": "PaginatedClusterDescription20240805"}
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

The `kind` of a type expression is one of `primitive`, `enum`, `array`, `object`, `reference`, `union`, `any`. The generator only has to understand this closed set and no longer needs to know about OpenAPI `$ref` / `allOf`.

> Note: `required` follows the spec exactly. A few body schemas (such as `ClusterDescription20240805`) do not declare a `required` array in the official spec, so their normalized fields are `false`. The normalizer does not infer them.

## Supported languages

| Language | Status | Default output | Generator |
| --- | --- | --- | --- |
| Python | supported | `pyatlassdk/admin`, `pyatlassdk/app` | `generator/python/` |
| JavaScript | planned | – | – |
| Rust | planned | – | – |

## Generating SDKs

Both SDKs live in the separate [pyatlassdk](https://github.com/zhangyaoxing/pyatlassdk) repository (a submodule of this repo), one subpackage per API:

| API | Package | Client | Authentication |
| --- | --- | --- | --- |
| Atlas Administration API v2 | `pyatlassdk.admin` | `AtlasAdminClient` | Digest API keys or OAuth 2.0 service accounts |
| App Services Admin API v3 | `pyatlassdk.app` | `AtlasAppAdminClient` | Bearer access token, or `AtlasAppAdminClient.login(username, api_key)` |

The root package re-exports both clients:

```python
from pyatlassdk import AtlasAdminClient, AtlasAppAdminClient
```

```bash
git clone --recurse-submodules git@github.com:zhangyaoxing/mongo-atlas-sdk.git
make pygen                                               # Admin SDK -> pyatlassdk/admin
make pygen-app                                           # App Services SDK -> pyatlassdk/app
make pipeline                                            # both API pipelines
uv run mongo-atlas pygen --api app -o /tmp/sdk --package sdk
```

Generation is fully driven by Jinja2 templates in `src/mongo_atlas_sdk/generator/python/templates/`, with the normalized document as the only input. The same input produces byte-identical output; there is no model inference or manual editing involved.

Output:

- Admin (`pyatlassdk/admin/`): 1027 pydantic models, 55 resource classes and 526 methods; `client.py` defines `AtlasAdminClient`
- App Services (`pyatlassdk/app/`): 253 pydantic models, 30 resource classes and 181 methods; `client.py` defines `AtlasAppAdminClient`

Generation rules:

- object → `BaseModel`; named enum → `str, Enum`; union / alias → `TypeAlias`
- pure map schemas (`object` with only `additionalProperties`) → `dict[str, T]`; for example `awsPrivateLink` is `dict[str, str]`, not an empty class
- inline enums → `Literal[...]`; inline anonymous objects get a synthesized class name based on the parent type and property path (for example `ApiErrorParametersItem`)
- field names become snake_case and automatically get `Field(alias=...)` when they differ from the wire name; invalid identifiers such as `_id` and `2dsphereIndexVersion` are mapped correctly
- endpoint paths are emitted relative to each client's `base_url`; the Admin client strips `/api/atlas/v2`, while App Services paths are already relative to `/api/admin/v3.0`
- request bodies are serialized with pydantic's JSON mode, so `datetime` / `date` fields become ISO 8601 strings before httpx encodes them
- Admin methods send the versioned `Accept` header declared by each endpoint's successful responses; App Services methods use `application/json`
- self-referencing types call `model_rebuild()` at the end of the module
- enum members are sanitized: `<` → `LT`, `>` → `GT`, and invalid or duplicate names get a suffix
- all-uppercase string enums accept any casing and normalize to the canonical value (`"secondary"` → `"SECONDARY"`); mixed-case enums stay strict

Admin usage:

```python
from pyatlassdk import AtlasAdminClient
from pyatlassdk.admin.models.cluster_description20240805 import ClusterDescription20240805

# Digest authentication with Atlas API keys
with AtlasAdminClient(public_key="...", private_key="...") as client:
    cluster = client.clusters.create_group_cluster(
        group_id="...",
        body=ClusterDescription20240805(name="demo", cluster_type="REPLICASET"),
    )

# OAuth 2.0 client credentials with Atlas service account credentials
with AtlasAdminClient(client_id="...", client_secret="...") as client:
    cluster = client.clusters.create_group_cluster(
        group_id="...",
        body=ClusterDescription20240805(name="demo", cluster_type="REPLICASET"),
    )
```

App Services usage:

```python
from pyatlassdk import AtlasAppAdminClient

# Exchange API-key credentials for an access token
client = AtlasAppAdminClient.login(username="...", api_key="...")
apps = client.apps.admin_list_applications(group_id="...")

# Or reuse an existing access token
with AtlasAppAdminClient(access_token="...") as client:
    apps = client.apps.admin_list_applications(group_id="...")
```

Notes:

- Generation is idempotent; repeated runs produce the same result.
- `pyatlassdk/admin/` and `pyatlassdk/app/` are owned by the generator; `pyatlassdk/__init__.py` is hand-maintained and re-exports both clients.
- `AtlasClient` remains as an alias for `AtlasAdminClient` for backwards compatibility.
- The `pyatlassdk` `pyproject.toml` excludes both generated packages from ruff; build and publish happen in that repository too.
- Commit order: commit and push in `pyatlassdk/` first, then commit the new submodule pointer here.
- Fields without `required` in the normalized document become optional parameters. That reflects the spec, not a generator assumption.

### Adding a language

Crawling and normalization are language-agnostic; only the rendering stage changes. The generator is laid out so a new target is a self-contained subpackage:

```
src/mongo_atlas_sdk/
├── apis.py           # API targets: spec URL, package, client class, auth, base URL
└── generator/
    ├── ir.py         # shared type-graph transforms (inline hoisting, references)
    ├── naming.py     # shared PascalCase normalization
    ├── templating.py # Jinja2 environment factory (one per language package)
    ├── registry.py   # language -> default output/package + orchestrator
    └── python/       # the Python target
        ├── orchestrator.py
        ├── models.py / resources.py / client.py
        ├── naming.py / schema.py / templating.py
        └── templates/  # .atlas/ bearer client templates + model/resource templates
```

To add JavaScript, Rust, or another language:

1. Create `generator/<language>/` with an `orchestrator.py` that exposes `generate_<language>(docs, output_root, *, api)` and returns the same stats dict as the Python backend.
2. Add the language's templates under `generator/<language>/templates/`; `generator.templating.render(language, template, **context)` loads them.
3. Register a `LanguageTarget` in `registry.py` with the default output path, package name, and orchestrator.
4. Add Makefile targets that pass the API key (`admin` or `app`). Add generator tests for the new backend.

The crawler, normalizer, API targets, and CLI plumbing stay unchanged.

## Project layout

```
.
├── pyatlassdk/               # submodule: generated SDKs (published to PyPI)
│   ├── __init__.py           # hand-maintained: exports both clients
│   ├── admin/               # generated Atlas Admin API v2 SDK
│   └── app/                 # generated App Services Admin API v3 SDK
├── src/mongo_atlas_sdk/      # generator (CLI + crawl + normalize + code generation)
│   ├── __init__.py
│   ├── __main__.py           # python -m mongo_atlas_sdk
│   ├── apis.py               # API targets (spec, package, client, auth, base URL)
│   ├── cli.py                # console script: mongo-atlas
│   ├── config.py             # environment-based settings
│   ├── crawler/              # OpenAPI -> api_docs*.json
│   │   ├── loader.py
│   │   └── extract.py
│   ├── normalizer/           # api_docs.json -> normalized_api_docs.json
│   │   ├── schema.py
│   │   └── api.py
│   ├── generator/            # normalized_api_docs.json -> SDK code
│   │   ├── ir.py             # shared type-graph transforms
│   │   ├── naming.py         # shared PascalCase normalization
│   │   ├── templating.py     # Jinja2 environment factory
│   │   ├── registry.py       # language -> target defaults
│   │   └── python/           # Python backend
│   │       ├── orchestrator.py
│   │       ├── models.py
│   │       ├── resources.py
│   │       ├── client.py
│   │       ├── naming.py
│   │       ├── schema.py
│   │       ├── templating.py
│   │       └── templates/    # model/resource/atlas & bearer client .j2
│   └── py.typed              # PEP 561 typing marker
├── tests/                    # pytest tests (fixtures/mini_openapi.json)
├── .data/                    # crawl artifacts (git-ignored)
├── pyproject.toml            # metadata + ruff/mypy/pytest/coverage config
├── uv.lock                   # locked dependency versions (commit this)
├── Makefile
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
└── .env.example
```

## Configuration

```bash
cp .env.example .env   # .env is git-ignored
```

| Variable | Default | Description |
| --- | --- | --- |
| `MONGO_ATLAS_PUBLIC_KEY` | – | Atlas API public key |
| `MONGO_ATLAS_PRIVATE_KEY` | – | Atlas API private key |
| `MONGO_ATLAS_BASE_URL` | `https://cloud.mongodb.com/api/atlas/v2` | API base URL |
| `LOG_LEVEL` | `INFO` | Log level, normalized to uppercase |

The current implementation reads `os.environ` directly, so values must be exported or `.env` must be loaded explicitly. To load `.env` automatically, add `python-dotenv` and call `load_dotenv()` at the start of `cli.py`.

## Development

```bash
uv run pre-commit install   # install the git hooks
uv run pre-commit run --all-files
```

Run `mypy` / `pytest` through `uv run`; there is no need to activate the virtualenv manually.

## Publishing

The SDK is built and published from the `pyatlassdk/` submodule:

```bash
cd pyatlassdk
uv build
uv publish   # requires a PyPI token (or uv publish --token ...)
```

The main repository only publishes the generator CLI, if desired:

```bash
uv build
```
