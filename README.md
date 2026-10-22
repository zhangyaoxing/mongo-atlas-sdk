[![CI](https://github.com/zhangyaoxing/mongo-atlas-sdk/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/zhangyaoxing/mongo-atlas-sdk/actions/workflows/ci.yml)

# mongo-atlas-sdk

MongoDB Atlas SDK 与命令行工具（Python ≥ 3.10）。

## 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)（依赖与虚拟环境管理）

## 快速开始

```bash
uv sync                              # 创建 .venv 并安装依赖
uv run mongo-atlas --version         # 查看版本
uv run mongo-atlas config            # 查看当前生效配置（密钥自动打码）
uv run mongo-atlas crawl             # 抓取 API 文档到 .data/api_docs.json
uv run mongo-atlas normalize         # 归一化为 .data/normalized_api_docs.json
uv run mongo-atlas generate          # 生成 Python SDK 到 src/mongo_atlas_sdk
uv run python -m mongo_atlas_sdk     # 等价的模块入口
```

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `make install` / `uv sync` | 安装（含 dev 依赖组） |
| `make lint` | ruff 代码检查 |
| `make format` | ruff 格式化并自动修复 |
| `make typecheck` | mypy 严格模式类型检查 |
| `make test` | pytest |
| `make coverage` | pytest + 覆盖率报告 |
| `make check` | 与 CI 一致的全套检查 |
| `make build` | 构建 sdist / wheel 到 `dist/` |
| `make lock` | 更新 `uv.lock` |
| `uv run mongo-atlas crawl` | 抓取 OpenAPI 文档到 `.data/api_docs.json` |
| `uv run mongo-atlas normalize` | 归一化到 `.data/normalized_api_docs.json` |
| `uv run mongo-atlas generate` | 生成 Python SDK（models / resources / client） |

## 抓取 API 文档

Atlas 文档站（`/docs/api/doc/atlas-admin-api-v2`）的正文本身由官方 OpenAPI 文档渲染而来，页面提供了同源下载：

- `https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2.json`（OpenAPI 3.0.1，约 4.7 MB）

因此抓取直接解析这份 JSON，而不是用 Playwright 解析渲染后的 DOM：字段（`type` / `required` / `description`）完全一致，但只需一次请求、结构稳定。实测单次抓取约 2 秒。

```bash
uv run mongo-atlas crawl                       # 下载并写入 .data/api_docs.json
uv run mongo-atlas crawl --spec local.json     # 使用本地 OpenAPI 文件（离线/测试）
uv run mongo-atlas crawl -o /tmp/docs.json     # 自定义输出路径
```

产物 `.data/api_docs.json`（`.data/` 已被 `.gitignore` 忽略）：

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

约定：

- 一级分类对应 spec 的 `tags`，即文档页面的分类标题（未来类名）；`operation_id` 是稳定的方法名来源，`summary` 对应端点页标题。
- Path / Query 参数直接来自 spec；参数级 `$ref` 会解析，同名参数以 operation 级覆盖 path 级。
- Body 参数取 schema 顶层字段；数组 Body 取 `items` 的字段。`schema` 保留原始 `$ref`，供后续归一化阶段展开 `allOf` / `oneOf` 和嵌套对象。
- 少数 `oneOf` 组合的 Body（如 `GroupAlertsConfig`）没有单一字段列表，只保留原始 schema。
- `responses` 按状态码排序（数字升序，`default` 排最后），每个状态码保留全部媒体类型及其原始 schema；错误响应（401/403/404/429/500）也会保留。
- `schemas` 保存 spec 的全部原始 schema 定义，使 `normalize` 只依赖 `api_docs.json` 即可解析 `$ref`。
- `meta.spec_sha256` 用于确认归一化结果对应哪个版本的文档。

## 归一化 API 文档

```bash
uv run mongo-atlas normalize                    # 读取 .data/api_docs.json 并写出
uv run mongo-atlas normalize -i raw.json -o out.json
```

归一化阶段做这些事：

- 解析 `$ref`（含别名链与循环检测），只保留从请求体或响应可达的类型；
- 合并 `allOf` 的属性、`required` 与描述；
- `oneOf` / `anyOf` 转为 `union`，保留 `discriminator`；
- 类型名统一为 PascalCase，同名冲突追加数字后缀；
- 数组、内联对象、`additionalProperties`、`enum`、`nullable`、`format` / `default` 全部转成封闭的类型表达式。

输出结构（`.data/normalized_api_docs.json`）：

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

类型表达式的 `kind` 取值：`primitive`、`enum`、`array`、`object`、`reference`、`union`、`any`。生成器只需处理这一套封闭结构，不再需要理解 OpenAPI 的 `$ref` / `allOf`。

> 注意：`required` 完全忠于 spec。个别 Body schema（如 `ClusterDescription20240805`）在官方 spec 中没有声明 `required` 数组，归一化结果也会是 `false`，不会自行推断。

## 生成 Python SDK

```bash
uv run mongo-atlas generate                                     # 生成到 src/mongo_atlas_sdk
uv run mongo-atlas generate -o /tmp/atlas_sdk --package atlas_sdk
```

生成器读取 `.data/normalized_api_docs.json`，输出三部分：

- `models/`：每个类型一个模块的 pydantic v2 模型（1068 个）
- `resources/`：55 个分类类，每个端点一个方法（526 个）
- `client.py`：`AtlasClient`，聚合所有资源并使用 httpx Digest 认证

生成规则：

- object → `BaseModel`；命名 enum → `str, Enum`；union / alias → `TypeAlias`
- 内联枚举 → `Literal[...]`；内联匿名对象 → 按父类型 + 属性路径合成类名（如 `ApiErrorParametersItem`）
- 字段名转 snake_case，与原字段名不同时自动加 `Field(alias=...)`；`_id`、`2dsphereIndexVersion` 等非法标识符也能正确映射
- 自引用类型在模块末尾调用 `model_rebuild()`
- 枚举成员清洗：`<` → `LT`、`>` → `GT`，非法或重复名追加后缀

使用：

```python
from mongo_atlas_sdk.client import AtlasClient
from mongo_atlas_sdk.models.cluster_description20240805 import ClusterDescription20240805

with AtlasClient(public_key="...", private_key="...") as client:
    cluster = client.clusters.create_group_cluster(
        group_id="...",
        body=ClusterDescription20240805(name="demo", cluster_type="REPLICASET"),
    )
```

说明：

- 生成是幂等的；重复执行结果一致。
- `models/`、`resources/`、`client.py` 归生成器所有，手改会在下次生成时被覆盖。
- 这些目录已在 `pyproject.toml` 中排除出 ruff / mypy（`force-exclude` 让 pre-commit 也遵守该规则）。
- `normalized_api_docs.json` 中缺失 `required` 的字段会生成可选参数，这是 spec 的真实情况，不是生成器推断。

## 目录结构

```
.
├── src/mongo_atlas_sdk/      # 包源码（src 布局，可安装/可发布）
│   ├── __init__.py
│   ├── __main__.py           # python -m mongo_atlas_sdk
│   ├── cli.py                # console script: mongo-atlas
│   ├── config.py             # 环境变量配置
│   ├── crawler/              # OpenAPI → api_docs.json
│   │   ├── loader.py         # 下载 / 读取 / 写出
│   │   └── extract.py        # 抽取分类、端点、参数
│   ├── normalizer/           # api_docs.json → normalized_api_docs.json
│   │   ├── schema.py         # $ref / allOf / oneOf 与类型归一化
│   │   └── api.py            # 端点与参数的归一化
│   ├── generator/            # normalized_api_docs.json → Python 代码
│   │   ├── naming.py         # 类 / 字段 / 枚举成员命名
│   │   ├── schema.py         # 匿名类型提升与注解渲染
│   │   ├── models.py         # pydantic 模型
│   │   ├── resources.py      # 资源类与方法
│   │   └── client.py         # AtlasClient
│   ├── client.py             # 生成：AtlasClient
│   ├── models/               # 生成：1068 个模型模块
│   ├── resources/            # 生成：55 个资源模块
│   └── py.typed              # 自带类型信息（PEP 561）
├── tests/                    # pytest 测试（fixtures/mini_openapi.json）
├── .data/                    # 抓取产物（git-ignored）
├── pyproject.toml            # 元数据 + ruff/mypy/pytest/coverage 配置
├── uv.lock                   # 锁定的依赖版本（需提交）
├── Makefile
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
└── .env.example
```

## 配置

```bash
cp .env.example .env   # .env 已被 .gitignore 忽略
```

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MONGO_ATLAS_PUBLIC_KEY` | – | Atlas API 公钥 |
| `MONGO_ATLAS_PRIVATE_KEY` | – | Atlas API 私钥 |
| `MONGO_ATLAS_BASE_URL` | `https://cloud.mongodb.com/api/atlas/v2` | API 地址 |
| `LOG_LEVEL` | `INFO` | 日志级别，自动转大写 |

当前实现直接读取 `os.environ`，因此运行前需 `export` 或显式加载 `.env`。若希望自动加载 `.env`，可加入 `python-dotenv` 并在 `cli.py` 入口调用 `load_dotenv()`。

## 开发

```bash
uv run pre-commit install   # 安装 git 钩子
uv run pre-commit run --all-files
```

本地 `mypy` / `pytest` 直接通过 `uv run` 调用即可，无需手动激活虚拟环境。

## 发布

```bash
uv build
uv publish   # 需要 PyPI token（或 uv publish --token ...）
```
