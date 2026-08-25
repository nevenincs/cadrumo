"""Canonical real-storage fixtures for aggregation tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....tests import bucket_id
from ....tests.secure_sql import isolated_runtime_profile

#: The bucket the ``secure_objects`` fixture makes ACTIVE. A test that builds a
#: repository for any other bucket id gets a route that is not attached to the
#: active bucket, so every self-loading repository inside a resolver degrades
#: instead of reading -- silently, as a storage_degraded diagnostic rather than
#: a refusal. Consumers must address this bucket, not a literal of their own.
SECURE_OBJECTS_BUCKET_ID = "78804f92-b6f7-4daf-9ddf-a8ce3829dbb1"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=SECURE_OBJECTS_BUCKET_ID) as profile:
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


__all__ = ["SECURE_OBJECTS_BUCKET_ID", "bucket_id", "secure_objects", "secure_profile_backend"]
