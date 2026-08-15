"""Persistence-owned lifecycle contracts for shared runtime test contexts."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import keyring
import pytest

from .....core import StorageCategory, storage_location
from .....core.time import now as _now
from .....tests.secure_sql import (
    isolated_cli_runtime_profile,
    isolated_ephemeral_secure_sql,
    isolated_profile_storage_root,
    isolated_runtime_profile,
)
from ..custody import (
    PROFILE_SESSION_KEYCHAIN_SERVICE,
    mint_profile_session,
)
from ..master_key import has_active_bucket_session
from ..sql.engine import get_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_isolated_ephemeral_secure_sql_releases_its_bucket_session(tmp_path: Path) -> None:
    with isolated_ephemeral_secure_sql(tmp_path=tmp_path):
        assert has_active_bucket_session()
        with get_engine().connect() as connection:
            database_rows = connection.exec_driver_sql("PRAGMA database_list").fetchall()

    assert not has_active_bucket_session()
    database_paths = {Path(str(row[2])).resolve() for row in database_rows if row[2]}
    expected = (tmp_path / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath).resolve()
    assert expected in database_paths


def test_isolated_runtime_profile_releases_its_bucket_session(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        assert has_active_bucket_session()
        fallback_database = profile.storage_root / storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath

    assert not has_active_bucket_session()
    assert not fallback_database.exists()


def test_isolated_cli_runtime_profile_releases_its_bucket_session(tmp_path: Path) -> None:
    with isolated_cli_runtime_profile(tmp_path=tmp_path):
        assert has_active_bucket_session()

    assert not has_active_bucket_session()


@pytest.mark.os_keychain
def test_isolated_profile_storage_root_reaps_a_discovered_bucket_key(tmp_path: Path) -> None:
    profile_id = UUID("11111111-1111-4111-8111-111111111111")
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        record = mint_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=1,
            dek_epoch="test-epoch",
            dek=b"d" * 32,
            now=_now(),
            idle_minutes=15,
            absolute_minutes=240,
        )
        account = f"{profile_id}:{record.session_id}"
        assert keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account) is not None

    assert keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account) is None
