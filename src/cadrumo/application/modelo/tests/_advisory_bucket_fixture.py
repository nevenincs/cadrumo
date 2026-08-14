"""Shared wizard-registered profile bucket for the mínimo advisory suite.

Every advisory test in this cluster does the same setup: open an isolated,
wizard-registered profile bucket scoped to the test's own ``tmp_path``. What
must NOT be shared is which bucket id each module opens -- some modules read
their own module-level ``_BUCKET_ID`` again later, in assertions and collector
calls, so a module that silently inherited another module's id would still
pass while asserting against the wrong bucket. Each consuming module supplies
its own id by overriding ``_bucket_id``; the default here raises so a module
that forgets the override fails loudly instead of inheriting one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...workflow import workflow_state_repository


@pytest.fixture
def _bucket_id() -> str:
    raise NotImplementedError(
        "a module importing _bucket from _advisory_bucket_fixture must override "
        "the _bucket_id fixture with its own bucket id"
    )


@pytest.fixture(autouse=True)
def _bucket(tmp_path: Path, _bucket_id: str) -> Iterator[None]:
    from ... import wizard as _wizard

    assert _wizard.WIZARD_FLOWS
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_bucket_id):
        workflow_state_repository().update(lambda s: register_minimal_profile(s, profile_id=_bucket_id))
        yield
