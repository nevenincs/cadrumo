"""Canonical isolated profile-storage fixtures for CLI config tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....tests.secure_sql import isolated_profile_storage_root


@pytest.fixture
def isolated_storage(tmp_path: Path) -> Iterator[Path]:
    """Provide real empty per-bucket storage through the production custody path."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


@pytest.fixture(name="_isolated_backend", autouse=True)
def config_check_isolated_backend(tmp_path: Path) -> Iterator[None]:
    """Autouse isolated storage/locale backend for the ``config check`` suites."""

    with (
        override_settings(cadrumo_local_storage_root=tmp_path / "storage", cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        yield


__all__ = ["config_check_isolated_backend", "isolated_storage"]
