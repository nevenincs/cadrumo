"""Shared bucket-id override scaffold for isolated real-storage test fixtures.

Several test suites open an isolated, real secure-storage bucket scoped to the
test's own ``tmp_path``, keyed by a bucket id the CONSUMING module must supply
-- some modules read their own module-level bucket-id constant again later, in
assertions and collector calls, so a module that silently inherited another
module's id would still pass while asserting against the wrong bucket. Each
consuming module therefore overrides ``bucket_id`` with its own value; the
default here raises so a module that forgets the override fails loudly
instead of silently inheriting one.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def bucket_id() -> str:
    raise NotImplementedError("bucket_id must be overridden by the importing test module")
