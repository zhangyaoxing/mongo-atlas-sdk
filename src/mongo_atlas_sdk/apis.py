"""Definitions of the Atlas APIs this project can generate SDKs for."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AtlasApi:
    """One source API and where its generated SDK lives."""

    key: str
    title: str
    spec_url: str
    raw_document: Path
    normalized_document: Path
    output_root: Path
    package: str
    client_class: str
    base_url: str
    auth_mode: str
    path_prefix: str | None


APIS: dict[str, AtlasApi] = {
    "admin": AtlasApi(
        key="admin",
        title="MongoDB Atlas Administration API",
        spec_url="https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2.json",
        raw_document=Path(".data/api_docs.json"),
        normalized_document=Path(".data/normalized_api_docs.json"),
        output_root=Path("pyatlassdk/src/pyatlassdk/admin"),
        package="pyatlassdk.admin",
        client_class="AtlasAdminClient",
        base_url="https://cloud.mongodb.com/api/atlas/v2",
        auth_mode="atlas",
        path_prefix="/api/atlas/v2",
    ),
    "app": AtlasApi(
        key="app",
        title="MongoDB Atlas App Services Admin API",
        spec_url="https://www.mongodb.com/docs/api/doc/atlas-app-services-admin-api-v3.json",
        raw_document=Path(".data/api_docs.app.json"),
        normalized_document=Path(".data/normalized_api_docs.app.json"),
        output_root=Path("pyatlassdk/src/pyatlassdk/app"),
        package="pyatlassdk.app",
        client_class="AtlasAppAdminClient",
        base_url="https://services.cloud.mongodb.com/api/admin/v3.0",
        auth_mode="bearer",
        path_prefix=None,
    ),
}


def get_api(key: str) -> AtlasApi:
    """Return the API definition for ``key`` or raise a clear error."""
    try:
        return APIS[key]
    except KeyError as exc:
        supported = ", ".join(sorted(APIS))
        raise ValueError(f"Unknown API {key!r} (supported: {supported})") from exc


__all__ = ["APIS", "AtlasApi", "get_api"]
