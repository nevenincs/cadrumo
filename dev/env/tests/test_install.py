"""The project environment is owned exclusively by locked ``uv`` sync."""

from __future__ import annotations

import pytest

from .._install import sync_command

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
