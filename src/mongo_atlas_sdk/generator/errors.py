"""Errors raised by the SDK generators."""

from __future__ import annotations


class GeneratorError(RuntimeError):
    """Raised when a normalized document cannot be rendered safely."""


__all__ = ["GeneratorError"]
