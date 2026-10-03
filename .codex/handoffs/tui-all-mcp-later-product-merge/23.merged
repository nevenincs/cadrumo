"""Isolate storage-management tests from the runner's explicit storage paths.

Reclaim deletes beneath whatever the declaration resolves, and the inventory and
tree check read it, so these tests must start from a settings baseline in which
no category is explicitly placed outside the root they repoint.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.env_scope import derived_storage_settings


@pytest.fixture(autouse=True)
def derived_storage_baseline(tmp_path: Path) -> Iterator[None]:
    """Resolve every category from the root, independently of the runner's explicit paths."""
    with derived_storage_settings(tmp_path / "ambient-storage"):
        yield
