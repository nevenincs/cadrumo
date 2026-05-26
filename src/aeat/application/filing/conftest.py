"""Shared fixtures for application/filing tests.

Centralises the encrypted-storage backend setup (master-key provider +
SQL engine + secret store override + disposal teardown) so the per-file
copies in ``_test_repository``, ``_test_history_repository``, and
``_test_complementaria_repository`` collapse into one autouse conftest
fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...tests.secure_sql import isolated_runtime_profile

_BUCKET_ID = "filing-test"


@pytest.fixture(autouse=True)
def _active_bucket_runtime(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield
