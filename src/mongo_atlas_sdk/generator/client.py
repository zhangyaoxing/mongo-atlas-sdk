"""Render the top-level Atlas client module."""

from __future__ import annotations

from collections.abc import Mapping

from mongo_atlas_sdk.generator.naming import snake_case

_TEMPLATE = '''"""Generated Atlas API client. Do not edit manually."""

from __future__ import annotations

from typing import Any, Mapping

import httpx
from pydantic import BaseModel, TypeAdapter

{{RESOURCE_IMPORTS}}

DEFAULT_BASE_URL = "https://cloud.mongodb.com/api/atlas/v2"


class AtlasApiError(Exception):
    """Raised when the Atlas API returns a non-successful response."""

    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.payload = payload


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(by_alias=True, exclude_none=True)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


class AtlasClient:
    """Synchronous client for the MongoDB Atlas Administration API."""

    def __init__(
        self,
        public_key: str | None = None,
        private_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        auth = (
            httpx.DigestAuth(public_key, private_key)
            if public_key and private_key
            else None
        )
        self._http = httpx.Client(base_url=base_url, auth=auth, timeout=timeout)
{{RESOURCE_ASSIGNMENTS}}

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> AtlasClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        response_model: Any = None,
    ) -> Any:
        """Send one request and validate the response into ``response_model``."""
        response = self._http.request(
            method,
            path,
            params={
                key: value for key, value in (params or {}).items() if value is not None
            },
            json=_serialize(json),
        )
        if response.status_code >= 400:
            raise AtlasApiError(
                response.status_code, response.text, _payload(response)
            )
        if response_model is None:
            return None
        return TypeAdapter(response_model).validate_python(response.json())
'''


def render_client(resources: Mapping[str, str], *, package: str) -> str:
    """Render ``client.py`` for the given ``{class: module}`` mapping."""
    imports = "\n".join(
        f"from {package}.resources.{module} import {name}"
        for name, module in sorted(resources.items())
    )
    assignments = "\n".join(
        f"        self.{snake_case(name)} = {name}(self)" for name in sorted(resources)
    )
    return _TEMPLATE.replace("{{RESOURCE_IMPORTS}}", imports).replace(
        "{{RESOURCE_ASSIGNMENTS}}", assignments
    )


__all__ = ["render_client"]
