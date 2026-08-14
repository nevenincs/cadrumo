"""Canonical empty-profile fixture for Modelo CLI inventory checks."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....tests.secure_sql import isolated_profile_storage_root

__all__ = ["_isolated_backend"]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            yield
        finally:
            dispose_engine()
