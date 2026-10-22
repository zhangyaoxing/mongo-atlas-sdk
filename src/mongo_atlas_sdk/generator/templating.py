"""Jinja2 environment for the Python code generator."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

_environment = Environment(
    loader=PackageLoader("mongo_atlas_sdk.generator", "templates"),
    autoescape=False,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


def render(template_name: str, **context: Any) -> str:
    """Render one template with the given context."""
    return _environment.get_template(template_name).render(**context)


def _docblock(text: str, indent: int) -> str:
    """Render a triple-quoted docstring, keeping single-line ones on one line."""
    if not text:
        return ""
    pad = " " * indent
    lines = text.splitlines()
    if len(lines) == 1:
        return f'{pad}"""{lines[0]}"""'
    body = "\n".join(f"{pad}{line}" if line else "" for line in lines)
    return f'{pad}"""\n{body}\n{pad}"""'


def _blockdoc(text: str, indent: int) -> str:
    """Render a triple-quoted docstring that always opens on its own line."""
    if not text:
        return ""
    pad = " " * indent
    body = "\n".join(f"{pad}{line}" if line else "" for line in text.splitlines())
    return f'{pad}"""\n{body}\n{pad}"""'


_environment.filters["docblock"] = _docblock
_environment.filters["blockdoc"] = _blockdoc


def docstring_text(text: object, fallback: str) -> str:
    """Escape a description so it can be embedded in a triple-quoted docstring."""
    raw = text if isinstance(text, str) and text.strip() else fallback
    return raw.strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


__all__ = ["docstring_text", "render"]
