"""Adverse-condition tests for bucket session activation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.config import SecretStoreBackend, Settings, override_settings
from ...bucket import (
    BucketLockedError,
)
from .._active_session import (
    NoActiveBucketSessionError,
    activate_session,
    get_active_master_key,
)
from .._bucket_session import BucketSession
from ._master_key_support import _publish_registration_capsule

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_OPENED_AT = datetime(2026, 6, 2, 8, 0, 0, tzinfo=UTC)
_KEK = bytes(range(32))
_DEK = bytes(range(32, 64))


def test_missing_bucket_session_raises_translated_storage_error() -> None:
    with pytest.raises(NoActiveBucketSessionError) as exc_info:
        get_active_master_key()

    assert exc_info.value.translated_message == "errors.refused.refused_storage_master_key_no_active_session"
    assert "aeat config login" in str(exc_info.value)


def test_locked_bucket_session_refuses_active_master_key_reads() -> None:
    session = BucketSession.open(
        bucket_id="locked",
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=_OPENED_AT,
    )
    session.close()

    with activate_session(session), pytest.raises(BucketLockedError) as exc_info:
        get_active_master_key()

    assert exc_info.value.bucket_id == "locked"
    assert session.sealed is True


def test_expired_bucket_session_seals_before_refusing_active_master_key_reads() -> None:
    session = BucketSession.open(
        bucket_id="expired",
        kek=_KEK,
        dek=_DEK,
        idle_minutes=1,
        opened_at=_OPENED_AT - timedelta(days=1),
    )

    with activate_session(session), pytest.raises(BucketLockedError) as exc_info:
        get_active_master_key()

    assert exc_info.value.bucket_id == "expired"
    assert session.sealed is True


def test_bucket_session_close_disposes_by_bucket_identity_under_explicit_database_url(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Close seals cleanly under an explicit database URL, disposing by bucket id.

    Engine disposal keys on the session's bucket identity, so it never
    re-derives a database route from live settings. An explicit database
    URL — which cannot be resolved to a bucket route — therefore no longer
    forces a broad fallback dispose; the close is a clean bucket-scoped
    disposal that seals the session and leaks no storage-root path.
    """
    session = BucketSession.open(
        bucket_id="explicit-route",
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=_OPENED_AT,
    )
    explicit_db = tmp_path / "explicit.db"

    with (
        override_settings(
            cadrumo_local_storage_root=tmp_path / "state",
            cadrumo_database_url=f"sqlite:///{explicit_db.as_posix()}",
        ),
        caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.persistence.storage.master_key._bucket_session"),
    ):
        session.close()

    assert session.sealed is True
    assert str(tmp_path) not in caplog.text


def _settings_with_store(tmp_path: Path) -> Settings:
    with override_settings(
        cadrumo_local_storage_root=tmp_path / "state",
        cadrumo_secret_store_dir=tmp_path / "fallback-store",
        cadrumo_secret_store_backend=SecretStoreBackend.AUTO,
    ) as settings:
        return settings


def _write_registered_bucket(root: Path, bucket_id: str) -> None:
    # Publication owns the bucket directory: it arrives by the capsule's
    # no-replace rename, never by provisioning it first. The plaintext manifest
    # this also wrote is retired, and nothing in production read it back.
    _publish_registration_capsule(root, bucket_id)
