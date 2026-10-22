"""Orchestrate Python SDK generation from the normalized API document."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mongo_atlas_sdk.generator.errors import GeneratorError
from mongo_atlas_sdk.generator.ir import hoist_inline_objects
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


def _package_init(package: str) -> str:
    return render("python", "package_init.py.j2", package=package)


def generate_python(
    docs: Mapping[str, Any],
    output_root: Path,
    *,
    package: str = DEFAULT_PACKAGE,
) -> dict[str, int]:
    """Generate models, resources, and ``client.py`` under ``output_root``."""
    raw_types = docs.get("types")
    if not isinstance(raw_types, Mapping):
        raise GeneratorError("normalized document has no 'types' section")
    categories = docs.get("categories")
    if not isinstance(categories, list):
        raise GeneratorError("normalized document has no 'categories' section")

    types = hoist_inline_objects(raw_types)

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
            render_resource(category, package=package),
            encoding="utf-8",
        )
        method_count += len(category.get("endpoints") or [])

    (resources_dir / "__init__.py").write_text(
        _resources_init(resource_modules, package),
        encoding="utf-8",
    )
    (output_root / "client.py").write_text(
        render_client(resource_modules, package=package),
        encoding="utf-8",
    )
    (output_root / "__init__.py").write_text(_package_init(package), encoding="utf-8")
    (output_root / "py.typed").write_text("", encoding="utf-8")

    return {
        "models": len(model_modules),
        "resources": len(resource_modules),
        "methods": method_count,
    }


__all__ = ["DEFAULT_PACKAGE", "GeneratorError", "generate_python"]
