"""Canonical opt-in profile storage fixture for selected CLI classes."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_profile_storage_root


@pytest.fixture
def isolated_profile_storage(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


__all__ = ["isolated_profile_storage"]
