"""Canonical isolated runtime fixtures for persistence adapter tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

__all__ = ["_runtime_profile", "bucket_scoped_runtime_profile_fixture"]


@pytest.fixture(name="_runtime_profile", autouse=True)
def _runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Install and tear down the real default-bucket runtime for one test."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile


def bucket_scoped_runtime_profile_fixture(
    bucket_id: str,
) -> Callable[[Path], Iterator[TestRuntimeProfile]]:
    """Build an autouse ``_runtime_profile`` fixture pinned to ``bucket_id``.

    A distinct ``bucket_id`` per test module keeps the bucket-scoped
    master-key session from colliding with other modules sharing a bucket in
    the same run. Assign the return value to ``_runtime_profile`` at module
    scope so the fixture stays autouse for that module only.
    """

    @pytest.fixture(name="_runtime_profile", autouse=True)
    def _bucket_scoped_runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
            yield profile

    return _bucket_scoped_runtime_profile
