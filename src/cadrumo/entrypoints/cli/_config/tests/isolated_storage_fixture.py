"""Canonical isolated profile-storage fixtures for CLI config tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....tests.secure_sql import isolated_profile_storage_root


@pytest.fixture
def config_check_backend(tmp_path: Path) -> Iterator[None]:
    """Isolated storage/locale backend for the ``config check`` suites."""

    with (
        override_settings(cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        yield


@pytest.fixture(name="_isolated_backend", autouse=True)
def config_check_isolated_backend(config_check_backend: None) -> None:
    """Autouse variant of :func:`config_check_backend` for the ``config check`` suites."""

    return config_check_backend


__all__ = ["config_check_backend", "config_check_isolated_backend"]
