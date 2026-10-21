"""Canonical direct fixture objects for the remaining strict CLI clusters."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import override_settings

from ._cli_surface_support import isolated_cli_surface_backend
from .modelo_profile_seed import ProfileSeeder
from .runtime_profile_backend import runtime_profile_backend_fixture

_DIAGNOSTICS_BUCKET_ID = "22222222-3333-4444-8555-666666666666"


@pytest.fixture(name="_isolated_backend")
def diagnostics_isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_DIAGNOSTICS_BUCKET_ID),
    ):
        register_minimal_profile(profile_id=_DIAGNOSTICS_BUCKET_ID)
        yield


@pytest.fixture(name="_isolated_backend", autouse=True)
def seeded_runtime_backend(seed_profile: ProfileSeeder) -> Iterator[None]:
    """Register one password-custodied operator profile whose joined runtime admits each command.

    Commands that submit registered operations reach records the test plants in
    this profile's encrypted catalogues through the same runtime an operator's
    command reaches. A module using this fixture also imports ``seed_profile``.
    """
    dispose_engine()
    try:
        seed_profile(label="operator", facts={})
        yield
    finally:
        dispose_engine()


@pytest.fixture(name="_isolated_backend", autouse=True)
def cli_surface_isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_cli_surface_backend(tmp_path):
        yield


#: One password-custodied operator profile whose runtime admits every command.
inventory_isolated_backend = runtime_profile_backend_fixture()
