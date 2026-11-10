"""Pytest fixtures for registry CLI tests.

Every storage member resolves beneath the storage root, so the one
``CADRUMO_STORAGE_ROOT`` the CLI subprocesses below share with
:func:`~cadrumo.adapters.persistence.storage.tests.secure_sql.isolated_runtime_profile`
is all they need to find the secret store that fixture already minted the
master key under and unlock the profile it created.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile

from ....adapters.persistence.storage.master_key.active_session import activate_session
from ....adapters.persistence.storage.master_key.bucket_session import BucketSession
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....adapters.persistence.storage.tests.secure_sql import dev_test_database_password, isolated_runtime_profile
from ....core.config import override_settings
from ....core.time.clock import now
from .registry_cli_support import BUCKET_ID, clear_cli_env, set_cli_env


@pytest.fixture(scope="module", autouse=True)
def _isolated_registry_cli_backend(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    tmp_path = tmp_path_factory.mktemp("registry-cli")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as runtime:
        set_cli_env(
            {
                "CADRUMO_STORAGE_ROOT": str(runtime.storage_root),
                "CADRUMO_ACTIVE_PROFILE": runtime.bucket_id,
                "CADRUMO_SECRET_PASSPHRASE": dev_test_database_password(runtime.settings),
                "CADRUMO_OUTPUT_LANGUAGE": "en",
            },
        )
        yield
    clear_cli_env()


@pytest.fixture(autouse=True)
def _isolated_secure_backend(tmp_path: Path) -> Iterator[None]:
    """Point encrypted SQL runtime at a per-test active bucket."""

    with (
        override_settings(cadrumo_storage_root=tmp_path, cadrumo_active_profile=BUCKET_ID) as settings,
        activate_session(_session()),
    ):
        dispose_engine(settings)
        # A bucket exists only once its profile capsule is published: opening an
        # engine against a bare session now refuses rather than materialising a
        # directory for a profile that was never registered.
        register_minimal_profile(profile_id=BUCKET_ID)
        try:
            yield
        finally:
            dispose_engine(settings)


def _session() -> BucketSession:
    # Deadlines are measured against the live clock, so the session opens now.
    opened_at = now()
    return BucketSession.open_resumed(
        bucket_id=BUCKET_ID,
        dek=b"d" * 32,
        idle_minutes=15,
        opened_at=opened_at,
        idle_deadline=opened_at + timedelta(minutes=15),
        absolute_deadline=opened_at + timedelta(minutes=240),
    )
