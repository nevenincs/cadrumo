"""Adverse-condition tests for bucket session activation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.config import SecretStoreBackend, Settings, override_settings
from ......core.external_constants import UTF_8_ENCODING
from ......domain.user_profile import UserProfileStatus
from ...bucket import (
    BucketKeySchedule,
    BucketLockedError,
    BucketManifest,
    ManifestKdfParams,
    manifest_path,
    provision_bucket_directory,
    write_manifest,
)
from ...errors import (
    MasterKeyPassphraseMismatchError,
    StorageValidationError,
)
from .. import (
    FileFallbackMasterKeyProvider,
    activate_master_key_provider,
)
from .._active_session import (
    NoActiveBucketSessionError,
    activate_session,
    get_active_master_key,
    has_active_bucket_session,
)
from .._bucket_session import BucketSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_OPENED_AT = datetime(2026, 6, 2, 8, 0, 0, tzinfo=UTC)
_KEK = bytes(range(32))
_DEK = bytes(range(32, 64))


def test_missing_bucket_session_raises_translated_storage_error() -> None:
    with pytest.raises(NoActiveBucketSessionError) as exc_info:
        get_active_master_key()

    assert exc_info.value.translated_message == "errors.refused.refused_storage_master_key_no_active_session"
    assert "aeat config switch" in str(exc_info.value)


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


def test_wrong_passphrase_activation_fails_without_opening_bucket_session(tmp_path: Path) -> None:
    settings = _settings_with_store(tmp_path)
    _write_registered_bucket(settings.cadrumo_local_storage_root, "alpha")
    FileFallbackMasterKeyProvider(
        store_dir=settings.cadrumo_secret_store_dir,
        passphrase_callback=lambda: "right-passphrase",
    ).provision_master_key()
    wrong_provider = FileFallbackMasterKeyProvider(
        store_dir=settings.cadrumo_secret_store_dir,
        passphrase_callback=lambda: "wrong-passphrase",
    )

    with (
        override_settings(
            cadrumo_local_storage_root=settings.cadrumo_local_storage_root,
            cadrumo_secret_store_dir=settings.cadrumo_secret_store_dir,
            cadrumo_secret_store_backend=SecretStoreBackend.FILE,
        ),
        pytest.raises(MasterKeyPassphraseMismatchError),
        activate_master_key_provider(wrong_provider, fallback_bucket_id="alpha"),
    ):
        pass

    assert wrong_provider._session is None
    assert has_active_bucket_session() is False


def test_torn_bucket_manifest_activation_fails_without_opening_bucket_session(tmp_path: Path) -> None:
    settings = _settings_with_store(tmp_path)
    paths = provision_bucket_directory(settings.cadrumo_local_storage_root, "torn")
    manifest_path(paths).write_text('bucket_id = "torn', encoding=UTF_8_ENCODING)
    provider = FileFallbackMasterKeyProvider(
        store_dir=settings.cadrumo_secret_store_dir,
        passphrase_callback=lambda: "right-passphrase",
    )
    provider.provision_master_key()

    with (
        override_settings(
            cadrumo_local_storage_root=settings.cadrumo_local_storage_root,
            cadrumo_secret_store_dir=settings.cadrumo_secret_store_dir,
            cadrumo_secret_store_backend=SecretStoreBackend.FILE,
        ),
        pytest.raises(StorageValidationError),
        activate_master_key_provider(provider, fallback_bucket_id="torn"),
    ):
        pass

    assert provider._session is None
    assert has_active_bucket_session() is False


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
        cadrumo_secret_store_dir=tmp_path / "secrets",
        cadrumo_secret_store_backend=SecretStoreBackend.FILE,
    ) as settings:
        return settings


def _write_registered_bucket(root: Path, bucket_id: str) -> None:
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=bucket_id,
            created_at=_OPENED_AT,
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=19,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=b"0123456789abcdef",
                output_length=32,
            ),
            recovery_enrolled=False,
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
            schema_version=1,
            status=UserProfileStatus.ACTIVE,
        ),
    )
