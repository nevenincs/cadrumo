"""Canonical real-storage ``SecureObjectRepository`` fixture.

Every consumer needs the same lifecycle -- an isolated, encrypted profile
bucket scoped to the test's own ``tmp_path`` -- but a DIFFERENT bucket id:
each consuming module's own bucket-id constant identifies its test's
bucket, and several modules read that constant again later, in assertions
and repository constructions, so a module that silently inherited another
module's id would still pass while writing to the wrong bucket. Each
importing module supplies its own id by overriding the shared ``bucket_id``
scaffold (:mod:`cadrumo.tests._bucket_id_fixture`) -- the same override point
every other real-storage fixture family in this tree uses, so "this module's
bucket id" is one vocabulary term rather than a per-family alias.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ._bucket_id_fixture import bucket_id
from .secure_sql import isolated_runtime_profile


@pytest.fixture
def secure_objects(tmp_path: Path, bucket_id: str) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        yield profile.repository


__all__ = ["bucket_id", "secure_objects"]
