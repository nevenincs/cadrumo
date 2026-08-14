"""Canonical direct fixture objects for the remaining strict CLI clusters."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ._cli_surface_support import isolated_cli_surface_backend
from ._english_locale_fixture import english_locale_fixture

_DIAGNOSTICS_BUCKET_ID = "22222222-3333-4444-8555-666666666666"

__all__ = ["english_locale_fixture"]


@pytest.fixture(name="_isolated_backend")
def diagnostics_isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_DIAGNOSTICS_BUCKET_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_DIAGNOSTICS_BUCKET_ID),
        )
        yield


@pytest.fixture(name="_isolated_backend", autouse=True)
def binding_isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("11111111-1111-4111-8111-111111111111"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(
                    state,
                    profile_id="11111111-1111-4111-8111-111111111111",
                ),
            )
            yield
        finally:
            dispose_engine()


@pytest.fixture(name="_isolated_backend", autouse=True)
def cli_surface_isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_cli_surface_backend(tmp_path):
        yield


@pytest.fixture(name="_isolated_backend", autouse=True)
def inventory_isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="00000000-0000-4000-8000-000000000000",
            ),
        )
        yield
