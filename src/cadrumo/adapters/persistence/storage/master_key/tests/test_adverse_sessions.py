"""Adverse-condition tests for bucket session activation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.config import SecretStoreBackend, Settings, override_settings
from ......core.external_constants import UTF_8_ENCODING
from ...bucket import (
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketKeySchedule,
    BucketLockedError,
    BucketManifest,
    ManifestKdfParams,
    bucket_paths,
    manifest_path,
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
from .._master_key_bucket_dek import load_or_mint_bucket_dek
from ._master_key_support import _ALPHA, _TORN, _publish_registration_capsule

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


def test_wrong_passphrase_activation_fails_without_opening_bucket_session(tmp_path: Path) -> None:
    settings = _settings_with_store(tmp_path)
    _write_registered_bucket(settings.cadrumo_local_storage_root, _ALPHA)
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
        activate_master_key_provider(wrong_provider, fallback_bucket_id=_ALPHA),
    ):
        pass

    assert wrong_provider._session is None
    assert has_active_bucket_session() is False


def test_torn_bucket_manifest_activation_fails_without_opening_bucket_session(tmp_path: Path) -> None:
    settings = _settings_with_store(tmp_path)
    provider = FileFallbackMasterKeyProvider(
        store_dir=settings.cadrumo_secret_store_dir,
        passphrase_callback=lambda: "right-passphrase",
    )
    provider.provision_master_key()
    # Mint the wrapped key while the bucket is still unregistered, then
    # register it, so activation gets past key resolution and reaches the
    # manifest-backed session policy this test tears.
    load_or_mint_bucket_dek(
        kek=provider.get_master_key(),
        storage_root=settings.cadrumo_local_storage_root,
        bucket_id=_TORN,
        allow_bootstrap_mint=True,
    )
    _write_registered_bucket(settings.cadrumo_local_storage_root, _TORN)
    paths = bucket_paths(settings.cadrumo_local_storage_root, _TORN)
    manifest_path(paths).write_text('bucket_id = "torn', encoding=UTF_8_ENCODING)

    with (
        override_settings(
            cadrumo_local_storage_root=settings.cadrumo_local_storage_root,
            cadrumo_secret_store_dir=settings.cadrumo_secret_store_dir,
            cadrumo_secret_store_backend=SecretStoreBackend.FILE,
        ),
        pytest.raises(StorageValidationError),
        activate_master_key_provider(provider, fallback_bucket_id=_TORN),
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
        cadrumo_secret_store_dir=tmp_path / "fallback-store",
        cadrumo_secret_store_backend=SecretStoreBackend.FILE,
    ) as settings:
        return settings


def _write_registered_bucket(root: Path, bucket_id: str) -> None:
    # Publication owns the bucket directory: it arrives by the capsule's
    # no-replace rename, never by provisioning it first.
    _publish_registration_capsule(root, bucket_id)
    paths = bucket_paths(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            # Derived, never the bare id: ProfileLabel refuses a UUID-shaped
            # label so an operator label can never be read as a machine id.
            label=f"profile-{bucket_id}",
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
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
            schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
        ),
    )
