"""Environment based configuration for the SDK and CLI."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://cloud.mongodb.com/api/atlas/v2"
DEFAULT_LOG_LEVEL = "INFO"

PUBLIC_KEY_ENV = "MONGO_ATLAS_PUBLIC_KEY"
PRIVATE_KEY_ENV = "MONGO_ATLAS_PRIVATE_KEY"
BASE_URL_ENV = "MONGO_ATLAS_BASE_URL"
LOG_LEVEL_ENV = "LOG_LEVEL"


def mask_secret(value: str | None) -> str:
    """Return a display-safe representation of ``value``."""
    if not value:
        return "not set"
    if len(value) <= 4:
        return "*" * len(value)
    return f"****{value[-4:]}"


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved runtime settings."""

    public_key: str | None = None
    private_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``env`` (``os.environ`` by default)."""
        source = os.environ if env is None else env
        return cls(
            public_key=source.get(PUBLIC_KEY_ENV) or None,
            private_key=source.get(PRIVATE_KEY_ENV) or None,
            base_url=source.get(BASE_URL_ENV) or DEFAULT_BASE_URL,
            log_level=(source.get(LOG_LEVEL_ENV) or DEFAULT_LOG_LEVEL).upper(),
        )

    @property
    def is_configured(self) -> bool:
        """Whether both Atlas API keys are present."""
        return bool(self.public_key and self.private_key)

    def describe(self, *, show_secrets: bool = False) -> str:
        """Render the settings as key/value lines, masked unless asked otherwise."""
        public_key = self.public_key if show_secrets else mask_secret(self.public_key)
        private_key = self.private_key if show_secrets else mask_secret(self.private_key)
        return "\n".join(
            [
                f"base_url: {self.base_url}",
                f"log_level: {self.log_level}",
                f"public_key: {public_key}",
                f"private_key: {private_key}",
            ]
        )
