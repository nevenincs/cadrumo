"""Canonical runtime-profile fixture for off-host consent test flows."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(name="profile")
def consent_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Provide the real bucket-backed profile used by consent workflows."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as resolved:
        yield resolved


__all__ = ["consent_profile"]
