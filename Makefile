# mongo-atlas-sdk developer tasks. Requires uv: https://docs.astral.sh/uv/
.DEFAULT_GOAL := help
UV ?= uv
SDK_LANG ?= python

.PHONY: help install lock lint format format-check typecheck test crawl normalize generate pygen pipeline coverage check build clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

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

crawl: ## Fetch the latest Atlas docs into .data/api_docs.json
	$(UV) run mongo-atlas crawl

normalize: ## Clean api_docs.json into normalized_api_docs.json
	$(UV) run mongo-atlas normalize

generate: ## Generate an SDK for a target language (LANG=python by default)
	$(UV) run mongo-atlas generate --language $(SDK_LANG)

pygen: ## Alias for `generate --language python`
	$(UV) run mongo-atlas pygen

pipeline: crawl normalize generate ## Run the full crawl -> normalize -> generate pipeline

check: lint format-check typecheck test ## Run every check used by CI

build: ## Build sdist and wheel into dist/
	$(UV) build

clean: ## Remove local caches and build artefacts
	rm -rf dist build htmlcov .coverage .pytest_cache .mypy_cache .ruff_cache
