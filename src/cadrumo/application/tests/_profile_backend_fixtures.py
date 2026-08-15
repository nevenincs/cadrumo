"""Canonical real profile backend for application reconciliation tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...tests.profile_capsule import open_test_profile_session
from ...tests.secure_sql import isolated_profile_storage_root
from ...tests.user_profile import register_minimal_profile


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("11111111-1111-4111-8111-111111111111"),
    ):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(
            profile_id="11111111-1111-4111-8111-111111111111",
            overrides={"identity.tax_id": "00000000T"},
        )
        yield


__all__ = ["_isolated_backend"]
