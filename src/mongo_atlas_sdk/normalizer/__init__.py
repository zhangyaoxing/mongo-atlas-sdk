"""Normalize crawled Atlas API docs into a generator-facing document."""

from __future__ import annotations

from mongo_atlas_sdk.normalizer.api import normalize_api_docs
from mongo_atlas_sdk.normalizer.schema import SchemaNormalizer, pascal_case

__all__ = ["SchemaNormalizer", "normalize_api_docs", "pascal_case"]
