"""Orchestrate Python SDK generation from the normalized API document."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mongo_atlas_sdk.generator.errors import GeneratorError
from mongo_atlas_sdk.generator.ir import hoist_inline_objects
from mongo_atlas_sdk.generator.media import latest_media_type
from mongo_atlas_sdk.generator.naming import pascal_case
from mongo_atlas_sdk.generator.python.client import render_client
from mongo_atlas_sdk.generator.python.models import render_model
from mongo_atlas_sdk.generator.python.naming import snake_case
from mongo_atlas_sdk.generator.python.resources import render_resource
from mongo_atlas_sdk.generator.templating import render

DEFAULT_PACKAGE = "pyatlassdk"


def _reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _models_init(modules: Mapping[str, str]) -> str:
    entries = [{"name": name, "module": modules[name]} for name in sorted(modules)]
    return render("python", "models_init.py.j2", modules=entries)


def _resources_init(modules: Mapping[str, str], package: str) -> str:
    entries = [{"name": name, "module": modules[name]} for name in sorted(modules)]
    return render("python", "resources_init.py.j2", package=package, resources=entries)


def _package_init(package: str, client_class: str) -> str:
    return render(
        "python",
        "package_init.py.j2",
        package=package,
        client_class=client_class,
    )


def _response_media_types(categories: list[Any]) -> list[str]:
    media_types: list[str] = []
    for category in categories:
        if not isinstance(category, Mapping):
            continue
        for endpoint in category.get("endpoints") or []:
            if not isinstance(endpoint, Mapping):
                continue
            for response in endpoint.get("responses") or []:
                if not str(response.get("status") or "").startswith("2"):
                    continue
                for content in response.get("content") or []:
                    media_type = content.get("content_type")
                    if isinstance(media_type, str):
                        media_types.append(media_type)
    return media_types


def _request_media_types(categories: list[Any]) -> list[str]:
    media_types: list[str] = []
    for category in categories:
        if not isinstance(category, Mapping):
            continue
        for endpoint in category.get("endpoints") or []:
            if not isinstance(endpoint, Mapping):
                continue
            body = endpoint.get("request_body")
            if isinstance(body, Mapping):
                media_type = body.get("content_type")
                if isinstance(media_type, str):
                    media_types.append(media_type)
    return media_types


def generate_python(
    docs: Mapping[str, Any],
    output_root: Path,
    *,
    package: str = DEFAULT_PACKAGE,
    client_class: str = "AtlasClient",
    base_url: str = "https://cloud.mongodb.com/api/atlas/v2",
    auth_mode: str = "atlas",
    path_prefix: str | None = "/api/atlas/v2",
) -> dict[str, int]:
    """Generate models, resources, and ``client.py`` under ``output_root``."""
    raw_types = docs.get("types")
    if not isinstance(raw_types, Mapping):
        raise GeneratorError("normalized document has no 'types' section")
    categories = docs.get("categories")
    if not isinstance(categories, list):
        raise GeneratorError("normalized document has no 'categories' section")

    types = hoist_inline_objects(raw_types)
    default_accept = latest_media_type(_response_media_types(categories)) or "application/json"
    default_content_type = latest_media_type(_request_media_types(categories)) or default_accept

    model_modules: dict[str, str] = {}
    for name in sorted(types):
        module = snake_case(name)
        if module in model_modules.values():
            raise GeneratorError(f"model module name collision for {name!r}")
        model_modules[name] = module

    resource_modules: dict[str, str] = {}
    for category in categories:
        if not isinstance(category, Mapping):
            continue
        class_name = pascal_case(str(category.get("name") or "Untagged"))
        module = snake_case(class_name)
        if module in resource_modules.values():
            raise GeneratorError(f"resource module name collision for {class_name!r}")
        resource_modules[class_name] = module

    models_dir = output_root / "models"
    resources_dir = output_root / "resources"
    _reset_directory(models_dir)
    _reset_directory(resources_dir)

    for name, module in model_modules.items():
        (models_dir / f"{module}.py").write_text(
            render_model(types[name], package=package),
            encoding="utf-8",
        )
    (models_dir / "__init__.py").write_text(_models_init(model_modules), encoding="utf-8")

    method_count = 0
    for category in categories:
        if not isinstance(category, Mapping):
            continue
        class_name = pascal_case(str(category.get("name") or "Untagged"))
        module = resource_modules[class_name]
        (resources_dir / f"{module}.py").write_text(
            render_resource(
                category,
                package=package,
                client_class=client_class,
                path_prefix=path_prefix,
            ),
            encoding="utf-8",
        )
        method_count += len(category.get("endpoints") or [])

    (resources_dir / "__init__.py").write_text(
        _resources_init(resource_modules, package),
        encoding="utf-8",
    )
    (output_root / "client.py").write_text(
        render_client(
            resource_modules,
            package=package,
            client_class=client_class,
            base_url=base_url,
            auth_mode=auth_mode,
            default_accept=default_accept,
            default_content_type=default_content_type,
        ),
        encoding="utf-8",
    )
    (output_root / "_enums.py").write_text(render("python", "enums.py.j2"), encoding="utf-8")
    (output_root / "_errors.py").write_text(render("python", "errors.py.j2"), encoding="utf-8")
    (output_root / "__init__.py").write_text(_package_init(package, client_class), encoding="utf-8")
    (output_root / "py.typed").write_text("", encoding="utf-8")

    return {
        "models": len(model_modules),
        "resources": len(resource_modules),
        "methods": method_count,
    }


__all__ = ["DEFAULT_PACKAGE", "GeneratorError", "generate_python"]
