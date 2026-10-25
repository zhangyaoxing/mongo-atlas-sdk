"""Render the top-level Atlas client module from a template."""

from __future__ import annotations

from collections.abc import Mapping

from mongo_atlas_sdk.generator.errors import GeneratorError
from mongo_atlas_sdk.generator.python.naming import snake_case
from mongo_atlas_sdk.generator.templating import render


def render_client(
    resources: Mapping[str, str],
    *,
    package: str,
    client_class: str,
    base_url: str,
    auth_mode: str,
    default_accept: str,
    default_content_type: str,
) -> str:
    """Render ``client.py`` for the given ``{class: module}`` mapping."""
    imports = [
        f"from {package}.resources.{module} import {name}"
        for name, module in sorted(resources.items())
    ]
    entries = [{"name": name, "attribute": snake_case(name)} for name in sorted(resources)]
    templates = {
        "atlas": "client_atlas.py.j2",
        "bearer": "client_bearer.py.j2",
        "none": "client_public.py.j2",
    }
    try:
        template = templates[auth_mode]
    except KeyError as exc:
        raise GeneratorError(f"unsupported auth mode: {auth_mode!r}") from exc
    return render(
        "python",
        template,
        imports=imports,
        resources=entries,
        package=package,
        client_class=client_class,
        base_url=base_url,
        default_accept=default_accept,
        default_content_type=default_content_type,
    )


__all__ = ["render_client"]
