"""Shared fixtures for storage/master_key tests.

Module-scope hoisting: secure storage runtime is initialized once per
test module rather than per test, reducing initialization overhead.
Per-test isolation uses Session().begin_nested() for transactional
rollback when needed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "master-key-test"


@pytest.fixture(scope="module")
def _active_bucket_runtime(tmp_path_factory) -> Iterator[TestRuntimeProfile]:
    tmp_path = tmp_path_factory.mktemp("master-key-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile
