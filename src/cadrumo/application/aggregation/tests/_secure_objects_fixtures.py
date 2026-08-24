"""Canonical real-storage fixtures for aggregation tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....tests import bucket_id
from ....tests.secure_sql import isolated_runtime_profile


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="78804f92-b6f7-4daf-9ddf-a8ce3829dbb1") as profile:
        yield profile.repository


@pytest.fixture
def secure_profile_backend(tmp_path: Path, bucket_id: str) -> Iterator[None]:
    """Real encrypted profile storage scoped to this test's bucket.

    The bucket id comes from the shared ``bucket_id`` override scaffold
    (:mod:`cadrumo.tests._bucket_id_fixture`) — each consumer's own profile-id
    constant identifies its test's bucket, so the value cannot be fixed here.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        yield


__all__ = ["bucket_id", "secure_objects", "secure_profile_backend"]
