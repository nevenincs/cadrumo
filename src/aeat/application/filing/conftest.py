"""Shared fixtures for application/filing tests.

Centralises the encrypted-storage backend setup (master-key provider +
SQL engine + secret store override + disposal teardown) so the per-file
copies in ``_test_repository``, ``_test_history_repository``, and
``_test_complementaria_repository`` collapse into one autouse conftest
fixture.

Module-scope hoisting: _active_bucket_runtime is initialized once per
test module rather than per test, reducing initialization overhead from
1.5-6 minutes sequential. Per-test isolation uses Session().begin_nested()
for transactional rollback when needed.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "filing-test"


@pytest.fixture(scope="module")
def _active_bucket_runtime(tmp_path_factory) -> Iterator[TestRuntimeProfile]:
    tmp_path = tmp_path_factory.mktemp("filing-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile
