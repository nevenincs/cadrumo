"""Canonical isolated active-profile fixture for local live-read CLI suites."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

__all__ = ["_ACTIVE_TEST_BUCKET_ID", "_isolated_backend"]

_ACTIVE_TEST_BUCKET_ID = "00000000-0000-4000-8000-000000000000"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(cadrumo_live_state_dir=tmp_path / "probe-live-state"),
        open_test_profile_session(_ACTIVE_TEST_BUCKET_ID),
    ):
        register_minimal_profile(profile_id=_ACTIVE_TEST_BUCKET_ID)
        yield
