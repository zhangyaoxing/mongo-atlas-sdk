# mongo-atlas-sdk developer tasks. Requires uv: https://docs.astral.sh/uv/
.DEFAULT_GOAL := help
UV ?= uv
SDK_LANG ?= python

.PHONY: help install lock lint format format-check typecheck test coverage \
	crawl normalize generate pygen crawl-app normalize-app generate-app pygen-app \
	pipeline pipeline-admin pipeline-app check build clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Create .venv and install all dependencies
	$(UV) sync

lock: ## Refresh uv.lock
	$(UV) lock

lint: ## Lint with ruff
	$(UV) run ruff check .

format: ## Format and auto-fix with ruff
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

format-check: ## Verify formatting without changing files
	$(UV) run ruff format --check .

typecheck: ## Type-check with mypy (strict)
	$(UV) run mypy

test: ## Run the test suite
	$(UV) run pytest

coverage: ## Run tests with a coverage report
	$(UV) run pytest --cov --cov-report=term-missing

crawl: ## Fetch the Atlas Admin API spec into .data/api_docs.json
	$(UV) run mongo-atlas crawl --api admin

normalize: ## Normalize the Admin API spec
	$(UV) run mongo-atlas normalize --api admin

generate: ## Generate the Admin SDK (SDK_LANG=python by default)
	$(UV) run mongo-atlas generate --language $(SDK_LANG) --api admin

pygen: ## Alias for `generate --language python --api admin`
	$(UV) run mongo-atlas pygen --api admin

crawl-app: ## Fetch the App Services Admin API spec
	$(UV) run mongo-atlas crawl --api app

normalize-app: ## Normalize the App Services Admin API spec
	$(UV) run mongo-atlas normalize --api app

generate-app: ## Generate the App Services SDK (SDK_LANG=python by default)
	$(UV) run mongo-atlas generate --language $(SDK_LANG) --api app

pygen-app: ## Alias for `generate --language python --api app`
	$(UV) run mongo-atlas pygen --api app

pipeline: pipeline-admin pipeline-app ## Run both API pipelines

pipeline-admin: crawl normalize pygen ## Admin API: crawl -> normalize -> generate

pipeline-app: crawl-app normalize-app pygen-app ## App Services API: crawl -> normalize -> generate

check: lint format-check typecheck test ## Run every check used by CI

build: ## Build sdist and wheel into dist/
	$(UV) build

clean: ## Remove local caches and build artefacts
	rm -rf dist build htmlcov .coverage .pytest_cache .mypy_cache .ruff_cache
