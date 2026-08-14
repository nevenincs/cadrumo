"""Canonical empty-storage-root fixture for profile-bootstrap test flows."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .secure_sql import isolated_profile_storage_root


@pytest.fixture(name="profile_storage_root")
def profile_storage_root_fixture(tmp_path: Path) -> Iterator[Path]:
    """Provide a real, empty per-bucket storage root with file-backed custody."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


__all__ = ["profile_storage_root_fixture"]
