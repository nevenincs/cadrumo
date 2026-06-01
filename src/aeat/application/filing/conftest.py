"""Shared fixtures for application/filing tests.

Centralises the encrypted-storage backend setup (master-key provider +
SQL engine + secret store override + disposal teardown) so the per-file
copies in ``_test_repository``, ``_test_history_repository``, and
``_test_complementaria_repository`` collapse into one autouse conftest
fixture.

Per-test scope is intentional: filing-repository tests persist
encrypted records and assert against per-test ``tmp_path`` filesystem
state. A module-scoped hoist (attempted in peer commit 4f83fefb9 as a
W30.P64.S804 perf win) is incompatible with these tests because they
do not use Session().begin_nested() for transactional rollback; the
hoist let one test's persisted records bleed into another's list+iter
assertions and broke the encrypted-payload-path lookup which uses the
per-test tmp_path. The proper hoist would also need a per-test
rollback teardown, which is tracked separately. Until that lands,
function-scope autouse is the correct shape.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "filing-test"


@pytest.fixture(autouse=True)
def _active_bucket_runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile
