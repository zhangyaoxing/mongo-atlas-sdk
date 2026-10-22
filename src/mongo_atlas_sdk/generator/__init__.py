"""Generate SDK source code from the normalized API document.

Each language lives in its own subpackage with its own templates and
orchestrator; shared transformations live directly under ``generator``.
"""

from __future__ import annotations

from mongo_atlas_sdk.generator.errors import GeneratorError
from mongo_atlas_sdk.generator.python.orchestrator import generate_python
from mongo_atlas_sdk.generator.registry import LANGUAGES, LanguageTarget, generate, get_target

__all__ = [
    "LANGUAGES",
    "GeneratorError",
    "LanguageTarget",
    "generate",
    "generate_python",
    "get_target",
]
