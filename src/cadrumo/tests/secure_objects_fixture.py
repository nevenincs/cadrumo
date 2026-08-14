"""Canonical real-storage ``SecureObjectRepository`` fixture.

Every consumer needs the same lifecycle -- an isolated, encrypted profile
bucket scoped to the test's own ``tmp_path`` -- but a DIFFERENT bucket id:
each consuming module's own bucket-id constant identifies its test's
bucket, and several modules read that constant again later, in assertions
and repository constructions, so a module that silently inherited another
module's id would still pass while writing to the wrong bucket. Each
importing module supplies its own id by overriding ``secure_objects_bucket_id``;
the default here raises so a module that forgets the override fails loudly
at fixture setup instead of inheriting one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..adapters.persistence.storage import SecureObjectRepository
from .secure_sql import isolated_runtime_profile


@pytest.fixture
def secure_objects_bucket_id() -> str:
    raise NotImplementedError(
        "a module importing secure_objects from secure_objects_fixture must "
        "override the secure_objects_bucket_id fixture with its own bucket id"
    )


@pytest.fixture
def secure_objects(tmp_path: Path, secure_objects_bucket_id: str) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=secure_objects_bucket_id) as profile:
        yield profile.repository


__all__ = ["secure_objects", "secure_objects_bucket_id"]
