"""Canonical isolated profile-storage fixture for CLI config tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....tests.secure_sql import isolated_profile_storage_root


@pytest.fixture
def isolated_storage(tmp_path: Path) -> Iterator[Path]:
    """Provide real empty per-bucket storage through the production custody path."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


__all__ = ["isolated_storage"]
