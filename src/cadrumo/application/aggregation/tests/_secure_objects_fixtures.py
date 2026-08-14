"""Canonical real-storage fixtures for aggregation tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....tests.secure_sql import isolated_runtime_profile


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="test") as profile:
        yield profile.repository


@pytest.fixture
def secure_profile_bucket_id() -> str:
    """The bucket id under test; the importing module overrides this fixture.

    Each consumer's own profile-id constant identifies its test's bucket, so
    the value cannot be fixed here — pytest resolves this name against the
    requesting test's own module first, which is how the override lands.
    """
    raise NotImplementedError("secure_profile_bucket_id must be overridden by the importing test module")


@pytest.fixture
def secure_profile_backend(tmp_path: Path, secure_profile_bucket_id: str) -> Iterator[None]:
    """Real encrypted profile storage scoped to this test's bucket."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=secure_profile_bucket_id):
        yield


__all__ = ["secure_objects", "secure_profile_backend", "secure_profile_bucket_id"]
