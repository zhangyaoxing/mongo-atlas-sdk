"""Language registry and default generation targets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mongo_atlas_sdk.generator.errors import GeneratorError
from mongo_atlas_sdk.generator.python.orchestrator import generate_python


@dataclass(frozen=True, slots=True)
class LanguageTarget:
    """One supported output language and its default repository location."""

    name: str
    default_output: Path
    default_package: str
    generator: Callable[..., dict[str, int]]


LANGUAGES: dict[str, LanguageTarget] = {
    "python": LanguageTarget(
        name="python",
        default_output=Path("pyatlassdk/src/pyatlassdk"),
        default_package="pyatlassdk",
        generator=generate_python,
    ),
}


def get_target(language: str) -> LanguageTarget:
    """Return the target for ``language`` or raise a clear error."""
    try:
        return LANGUAGES[language]
    except KeyError as exc:
        supported = ", ".join(sorted(LANGUAGES))
        raise GeneratorError(
            f"Unsupported language: {language!r} (supported: {supported})"
        ) from exc


def generate(
    language: str,
    docs: Mapping[str, Any],
    *,
    output_root: Path | None = None,
    package: str | None = None,
) -> dict[str, int]:
    """Generate an SDK for ``language`` using the target's defaults when omitted."""
    target = get_target(language)
    return target.generator(
        docs,
        output_root if output_root is not None else target.default_output,
        package=package or target.default_package,
    )


__all__ = ["LANGUAGES", "LanguageTarget", "generate", "get_target"]
