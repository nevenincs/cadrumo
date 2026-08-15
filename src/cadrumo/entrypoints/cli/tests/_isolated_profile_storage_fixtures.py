"""Canonical profile-storage isolation fixtures for CLI test modules."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core.config import override_settings
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root, isolated_sessionless_storage_root
from ....tests.user_profile import register_minimal_profile


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


active_profile_isolated_backend = active_profile_isolated_backend_fixture()


@pytest.fixture(name="_isolated_backend", autouse=True)
def llm_profile_isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("00000000-0000-4000-8000-000000000000"),
    ):
        register_minimal_profile(profile_id="00000000-0000-4000-8000-000000000000")
        yield


@pytest.fixture(name="_isolated_backend", autouse=True)
def live_fx_isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_output_language="en",
            cadrumo_live_tests_enabled="1",
        ),
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("00000000-0000-4000-8000-000000000000"),
    ):
        try:
            register_minimal_profile(profile_id="00000000-0000-4000-8000-000000000000")
            yield
        finally:
            dispose_engine()
