"""Canonical profile-storage isolation fixtures for CLI test modules."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_profile_storage_root


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(autouse=True)
def _isolated_source(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield
