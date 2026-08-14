"""Canonical active empty-profile fixture for ledger read-verb suites."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.workflow import WorkflowState
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

__all__ = ["_isolated_backend"]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_BUCKET_ID),
    ):
        register_minimal_profile(WorkflowState(), profile_id=_BUCKET_ID)
        yield
