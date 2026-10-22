"""Crawl the Atlas API documentation into an intermediate JSON document."""

from __future__ import annotations

from mongo_atlas_sdk.crawler.extract import extract_api_docs
from mongo_atlas_sdk.crawler.loader import (
    SPEC_URL,
    SpecSourceError,
    fetch_spec,
    load_spec,
    write_api_docs,
)

__all__ = [
    "SPEC_URL",
    "SpecSourceError",
    "extract_api_docs",
    "fetch_spec",
    "load_spec",
    "write_api_docs",
]
