"""Read the Atlas OpenAPI document from the docs site or a local file."""

from __future__ import annotations

import gzip
import json
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SPEC_URL = "https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2.json"
DEFAULT_TIMEOUT_SECONDS = 60.0
USER_AGENT = "mongo-atlas-sdk/0.1 (+https://github.com/zhangyaoxing/mongo-atlas-sdk)"


class SpecSourceError(RuntimeError):
    """Raised when the OpenAPI document cannot be downloaded, read, or parsed."""


def _decode_payload(payload: bytes) -> bytes:
    """Decompress the payload when the server ignores our Accept-Encoding."""
    if payload[:2] == b"\x1f\x8b":
        return gzip.decompress(payload)
    return payload


def _parse(payload: bytes) -> dict[str, Any]:
    try:
        document = json.loads(_decode_payload(payload))
    except (json.JSONDecodeError, OSError) as exc:
        raise SpecSourceError(f"Invalid OpenAPI document: {exc}") from exc
    if not isinstance(document, dict):
        raise SpecSourceError("OpenAPI document must be a JSON object")
    return document


def fetch_spec(url: str = SPEC_URL, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Download and parse an OpenAPI document over HTTP(S)."""
    scheme = urlparse(url).scheme
    if scheme not in {"http", "https"}:
        raise SpecSourceError(f"Unsupported URL scheme: {scheme!r}")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except OSError as exc:
        raise SpecSourceError(f"Failed to download {url}: {exc}") from exc
    return _parse(payload)


def load_spec(path: Path) -> dict[str, Any]:
    """Read and parse an OpenAPI document from disk."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SpecSourceError(f"Failed to read {path}: {exc}") from exc
    return _parse(payload)


def write_api_docs(document: dict[str, Any], path: Path) -> None:
    """Write the intermediate document as UTF-8 JSON, creating parent folders."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")
