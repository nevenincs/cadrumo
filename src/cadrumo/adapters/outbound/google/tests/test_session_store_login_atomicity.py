"""Sign-in is an encrypted transaction that survives process replacement.

These tests use synthetic custody and credentials with real encrypted SQL.
They do not establish native desktop authentication or provider acceptance.
"""

from __future__ import annotations

import multiprocessing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from .....core.config import override_settings
from .....core.storage_taxonomy import StorageCategory
from .....tests.storage_scope import storage_overrides
from ....persistence.storage.errors import RepositoryError
from ....persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from .. import session_store
from ..records import REQUIRED_SCOPES, DriveConfig, OAuthMetadata, OAuthToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_PROFILE = "a690aa03-a33f-4998-92d7-6ee02c7b2d08"


def _records(version: str) -> tuple[OAuthToken, OAuthMetadata, DriveConfig]:
    return (
        OAuthToken(
            refresh_token=f"synthetic-refresh-{version}",
            client_id="synthetic.apps.googleusercontent.com",
            token_uri="https://oauth2.googleapis.com/token",
        ),
        OAuthMetadata(
            account_email=f"{version}@example.invalid",
            granted_scopes=REQUIRED_SCOPES,
            issued_at=datetime(2026, 10, 5, tzinfo=UTC),
        ),
        DriveConfig(root_folder_id=f"synthetic-root-{version}"),
    )


def _read_in_fresh_process(tmp_path: Path, expected: str | None) -> None:
    with (
        override_settings(
            cadrumo_local_storage_root=tmp_path / "cadrumo-storage",
            cadrumo_active_profile=_PROFILE,
            **storage_overrides(tmp_path, StorageCategory.SECRETS),
        ),
        open_test_profile_session(_PROFILE),
    ):
        actual = (
            session_store.load_token(_PROFILE),
            session_store.load_metadata(_PROFILE),
            session_store.load_drive_config(_PROFILE),
        )
        assert actual == (_records(expected) if expected is not None else (None, None, None))


def _assert_reopened(tmp_path: Path, expected: str | None) -> None:
    child = multiprocessing.get_context("spawn").Process(target=_read_in_fresh_process, args=(tmp_path, expected))
    child.start()
    try:
        child.join(timeout=None)
        assert child.exitcode == 0, "fresh process could not read the complete expected sign-in"
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=10)
        child.close()


def test_login_commit_is_encrypted_and_readable_in_a_fresh_process(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as runtime:
        session_store.save_session(_PROFILE, *_records("new"))
        database_name = runtime.repository._engine.url.database
        assert database_name is not None
        database = Path(database_name)
        at_rest = read_db_at_rest_bytes(database)
        for plaintext in (b"synthetic-refresh-new", b"new@example.invalid", b"synthetic-root-new"):
            assert plaintext not in at_rest
    _assert_reopened(tmp_path, "new")


@pytest.mark.parametrize("existing", [False, True], ids=["first-sign-in", "replace-sign-in"])
def test_failure_on_last_record_rolls_back_the_whole_login(tmp_path: Path, existing: bool) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as runtime:
        if existing:
            session_store.save_session(_PROFILE, *_records("old"))
        # Fail at SQL execution, after the earlier records have been written
        # inside the transaction. Pre-validation alone would not prove rollback.
        with runtime.repository._engine.begin() as connection:
            for action in ("INSERT", "UPDATE"):
                connection.execute(
                    text(
                        f"CREATE TRIGGER reject_config_{action} BEFORE {action} ON secure_objects "
                        "WHEN NEW.namespace = 'cadrumo.google.drive.config' "
                        "BEGIN SELECT RAISE(ABORT, 'synthetic config failure'); END"
                    )
                )
        with pytest.raises(RepositoryError):
            session_store.save_session(_PROFILE, *_records("new"))
    _assert_reopened(tmp_path, "old" if existing else None)
