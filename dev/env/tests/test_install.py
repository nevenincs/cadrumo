"""The project environment is owned exclusively by locked ``uv`` sync."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev._paths import AUTHORITY_ROOT_ENV, DEFAULT_AUTHORITY_ROOT

from .._install import sync_command, sync_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_project_environment_uses_one_locked_uv_sync() -> None:
    """Initialization has no explicit venv creation or pip-compatible path."""
    command = sync_command()

    assert command == (
        "uv",
        "sync",
        "--locked",
        "--extra",
        "workbook-windows",
        "--group",
        "dev",
    )
    assert "pip" not in command
    assert "venv" not in command


def test_sync_environment_removes_the_synthesized_checkout_authority_default() -> None:
    """The first editable build must be allowed to provision its owned default."""
    environment = sync_environment({AUTHORITY_ROOT_ENV: str(DEFAULT_AUTHORITY_ROOT), "KEPT": "value"})

    assert AUTHORITY_ROOT_ENV not in environment
    assert environment["KEPT"] == "value"


def test_sync_environment_preserves_a_relocated_operator_override(tmp_path: Path) -> None:
    """A genuine relocation remains explicit and therefore fail-closed."""
    override = tmp_path / "operator-authority"

    environment = sync_environment({AUTHORITY_ROOT_ENV: str(override)})

    assert environment[AUTHORITY_ROOT_ENV] == str(override)
