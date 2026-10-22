"""Python-specific rendering helpers and Jinja2 filters."""

from __future__ import annotations

from mongo_atlas_sdk.generator.templating import environment


def docstring_text(text: object, fallback: str) -> str:
    """Escape a description so it can be embedded in a triple-quoted docstring."""
    raw = text if isinstance(text, str) and text.strip() else fallback
    return raw.strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


def _docblock(text: str, indent: int) -> str:
    """Render a triple-quoted docstring, keeping single-line ones on one line."""
    if not text:
        return ""
    pad = " " * indent
    lines = text.splitlines()
    if len(lines) == 1:
        return f'{pad}"""{lines[0]}"""'
    return (
        f'{pad}"""\n' + "\n".join(f"{pad}{line}" if line else "" for line in lines) + f'\n{pad}"""'
    )


def _blockdoc(text: str, indent: int) -> str:
    """Render a triple-quoted docstring that always opens on its own line."""
    if not text:
        return ""
    pad = " " * indent
    return (
        f'{pad}"""\n'
        + "\n".join(f"{pad}{line}" if line else "" for line in text.splitlines())
        + f'\n{pad}"""'
    )


_environment = environment("python")
_environment.filters["docblock"] = _docblock
_environment.filters["blockdoc"] = _blockdoc

__all__ = ["docstring_text"]
