"""Canonical active-profile fixture for CLI surface suites."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ._cli_surface_support import create_cli_surface_profile, isolated_cli_surface_backend

__all__ = ["_isolated_backend"]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_cli_surface_backend(tmp_path):
        create_cli_surface_profile()
        yield
