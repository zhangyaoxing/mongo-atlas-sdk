from __future__ import annotations

import subprocess
import sys

import pytest

from mongo_atlas_sdk import __version__
from mongo_atlas_sdk.__main__ import main as module_main
from mongo_atlas_sdk.cli import main


def test_main_module_delegates_to_cli() -> None:
    assert module_main is main


def test_python_dash_m_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mongo_atlas_sdk", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "mongo-atlas" in result.stdout


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])

    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_config_command_masks_keys(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MONGO_ATLAS_PUBLIC_KEY", "public-key-value")

    assert main(["config"]) == 0

    out = capsys.readouterr().out
    assert "public_key: ****alue" in out
    assert "public-key-value" not in out


def test_config_command_show_secrets(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MONGO_ATLAS_PUBLIC_KEY", "public-key-value")

    assert main(["config", "--show-secrets"]) == 0

    assert "public_key: public-key-value" in capsys.readouterr().out


def test_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    assert "usage:" in capsys.readouterr().out
