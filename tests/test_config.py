from __future__ import annotations

from mongo_atlas_sdk.config import DEFAULT_BASE_URL, Settings, mask_secret


def test_defaults_without_env() -> None:
    settings = Settings.from_env({})

    assert settings.base_url == DEFAULT_BASE_URL
    assert settings.log_level == "INFO"
    assert settings.public_key is None
    assert settings.is_configured is False


def test_reads_and_normalises_env() -> None:
    settings = Settings.from_env(
        {
            "MONGO_ATLAS_PUBLIC_KEY": "pub",
            "MONGO_ATLAS_PRIVATE_KEY": "priv",
            "MONGO_ATLAS_BASE_URL": "https://example.test",
            "LOG_LEVEL": "debug",
        }
    )

    assert settings.is_configured is True
    assert settings.base_url == "https://example.test"
    assert settings.log_level == "DEBUG"


def test_empty_env_values_fall_back_to_defaults() -> None:
    settings = Settings.from_env({"MONGO_ATLAS_BASE_URL": "", "LOG_LEVEL": ""})

    assert settings.base_url == DEFAULT_BASE_URL
    assert settings.log_level == "INFO"


def test_mask_secret() -> None:
    assert mask_secret(None) == "not set"
    assert mask_secret("") == "not set"
    assert mask_secret("ab") == "**"
    assert mask_secret("abcdefgh") == "****efgh"


def test_describe_masks_secrets_by_default() -> None:
    settings = Settings(public_key="abcdefgh", private_key="ijklmnop")

    text = settings.describe()

    assert "abcdefgh" not in text
    assert "ijklmnop" not in text
    assert "****efgh" in text
    assert "****mnop" in text


def test_describe_can_show_secrets() -> None:
    settings = Settings(public_key="abcdefgh")

    text = settings.describe(show_secrets=True)

    assert "public_key: abcdefgh" in text
