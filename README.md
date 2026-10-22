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

## 目录结构

```
.
├── src/mongo_atlas_sdk/      # 包源码（src 布局，可安装/可发布）
│   ├── __init__.py
│   ├── __main__.py           # python -m mongo_atlas_sdk
│   ├── cli.py                # console script: mongo-atlas
│   ├── config.py             # 环境变量配置
│   └── py.typed              # 自带类型信息（PEP 561）
├── tests/                    # pytest 测试
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
