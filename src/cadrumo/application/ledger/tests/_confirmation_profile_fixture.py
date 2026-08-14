"""Canonical runtime-profile fixture for confirmation-review tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Provide a real isolated runtime profile with its encrypted SQLite engine."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as resolved:
        yield resolved


__all__ = ["profile"]
