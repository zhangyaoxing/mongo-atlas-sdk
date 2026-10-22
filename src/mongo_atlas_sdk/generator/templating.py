"""Shared Jinja2 environment factory for language backends."""

from __future__ import annotations

from functools import cache
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined


@cache
def environment(language: str) -> Environment:
    return Environment(
        loader=PackageLoader(f"mongo_atlas_sdk.generator.{language}", "templates"),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )


def render(language: str, template_name: str, **context: Any) -> str:
    """Render a template from ``generator/<language>/templates``."""
    return environment(language).get_template(template_name).render(**context)


__all__ = ["environment", "render"]
