"""Render the top-level Atlas client module from a template."""

from __future__ import annotations

from collections.abc import Mapping

from mongo_atlas_sdk.generator.python.naming import snake_case
from mongo_atlas_sdk.generator.templating import render


def render_client(resources: Mapping[str, str], *, package: str) -> str:
    """Render ``client.py`` for the given ``{class: module}`` mapping."""
    imports = [
        f"from {package}.resources.{module} import {name}"
        for name, module in sorted(resources.items())
    ]
    entries = [{"name": name, "attribute": snake_case(name)} for name in sorted(resources)]
    return render("python", "client.py.j2", imports=imports, resources=entries)


__all__ = ["render_client"]
