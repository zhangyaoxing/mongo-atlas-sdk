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
          }
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
- `meta.spec_sha256` 用于确认归一化结果对应哪个版本的文档。

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
