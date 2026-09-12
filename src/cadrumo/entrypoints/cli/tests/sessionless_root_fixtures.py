"""Canonical pristine sessionless storage-root fixture."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_sessionless_storage_root


@pytest.fixture
def _sessionless_root(tmp_path: Path) -> Iterator[Path]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


__all__ = ["_sessionless_root"]
