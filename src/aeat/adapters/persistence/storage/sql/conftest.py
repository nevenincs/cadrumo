"""Shared fixtures for storage/sql tests.

Module-scope hoisting: secure storage runtime is initialized once per
test module rather than per test, reducing initialization overhead.
Per-test isolation uses Session().begin_nested() for transactional
rollback when needed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "sql-test"


@pytest.fixture(scope="module")
def _active_bucket_runtime(tmp_path_factory) -> Iterator[TestRuntimeProfile]:
    tmp_path = tmp_path_factory.mktemp("sql-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile
