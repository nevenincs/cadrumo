"""Canonical isolated active-profile fixture for local live-read CLI suites."""

from __future__ import annotations

from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture

__all__ = ["_ACTIVE_TEST_BUCKET_ID", "_isolated_backend"]

_ACTIVE_TEST_BUCKET_ID = "00000000-0000-4000-8000-000000000000"

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_ACTIVE_TEST_BUCKET_ID,
    settings_overrides=lambda tmp_path: {"cadrumo_live_state_dir": tmp_path / "probe-live-state"},
)
