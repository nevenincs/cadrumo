"""Application-owned custody operations for the profile secret store.

The config CLI calls this module for recovery-code minting,
verification, passphrase change, and recovery. Storage primitives stay in
:mod:`cadrumo.adapters.persistence.storage`; this layer resolves
:class:`~cadrumo.core.config.Settings`, updates the active profile manifest
when recovery is enrolled, and returns typed application result records.

Plaintext recovery words are returned only from
:func:`mint_recovery_code`. They are never persisted by this module; the
secret store keeps only wrapped recovery material. Verification failures
from :class:`~cadrumo.adapters.persistence.storage.RecoveryVerificationError`
and related storage errors are rendered as a false verification result
rather than leaking backend exception details.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ...adapters.persistence.storage import RecoveryVerificationError, SecretStoreError, StorageValidationError
from ...adapters.persistence.storage.master_key import (
    FileFallbackMasterKeyProvider,
    activate_master_key_provider,
    get_master_key_provider,
    load_recovery_envelope,
    mint_recovery_envelope,
    save_recovery_envelope,
    unwrap_recovery_envelope,
    verify_recovery_mnemonic,
)
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ...core.time import now as utc_now

_RECOVERY_WRAP_FILENAME = "master.recovery.key"
_log = get_logger(__name__)


class CustodyRecoveryEnrollment(BaseModel):
    """Result of minting or rotating the persisted recovery wrapper."""

    model_config = STRICT_FROZEN_CONFIG

    recovery_path: Path
    mnemonic: str
    rotated: bool


class CustodyRecoveryStatus(BaseModel):
    """Current recovery-wrapper status for the configured secret store."""

    model_config = STRICT_FROZEN_CONFIG

    recovery_path: Path
    recovery_enrolled: bool


class CustodyRecoveryVerification(BaseModel):
    """Result of checking an operator-supplied recovery mnemonic."""

    model_config = STRICT_FROZEN_CONFIG

    recovery_path: Path
    verified: bool


class CustodyPassphraseChangeResult(BaseModel):
    """Result of rotating the file secret store's passphrase.

    Carries only the non-secret store location and a completion flag; neither
    the current nor the new passphrase is ever held on this record.
    """

    model_config = STRICT_FROZEN_CONFIG

    secret_store_dir: Path
    changed: bool


class CustodyRecoverResult(BaseModel):
    """Result of recovering the master key from the recovery wrapper."""

    model_config = STRICT_FROZEN_CONFIG

    recovery_path: Path
    secret_store_dir: Path
    recovered: bool


def _settings(settings: Settings | None = None) -> Settings:
    return settings if settings is not None else load_settings()


def recovery_wrap_path(settings: Settings | None = None) -> Path:
    """Return the configured persisted recovery-wrapper path."""
    return Path(_settings(settings).cadrumo_secret_store_dir) / _RECOVERY_WRAP_FILENAME


def inspect_recovery_status(settings: Settings | None = None) -> CustodyRecoveryStatus:
    """Inspect whether the configured recovery wrapper exists and return a :class:`CustodyRecoveryStatus`."""
    path = recovery_wrap_path(settings)
    return CustodyRecoveryStatus(recovery_path=path, recovery_enrolled=path.is_file())


def _mark_active_profile_recovery_enrolled(settings: Settings) -> None:
    """Mirror recovery enrollment into the active profile manifest."""
    from ...adapters.persistence.storage.bucket import bucket_paths, read_manifest, write_manifest
    from ...core import resolve_active_bucket_id

    active_profile = resolve_active_bucket_id()
    if active_profile is None:
        return
    paths = bucket_paths(Path(settings.cadrumo_local_storage_root), active_profile)
    manifest = read_manifest(paths)
    if manifest.recovery_enrolled:
        return
    write_manifest(paths, manifest.model_copy(update={"recovery_enrolled": True}))


def mint_recovery_code(settings: Settings | None = None) -> CustodyRecoveryEnrollment:
    """Mint a new recovery mnemonic and return a :class:`CustodyRecoveryEnrollment`.

    The mnemonic is returned exactly once. The plaintext words are not
    persisted; only the wrapped master key lands in the secret-store
    directory.
    """
    resolved = _settings(settings)
    path = recovery_wrap_path(resolved)
    rotated = path.exists()
    provider = get_master_key_provider(settings_override=resolved)
    with activate_master_key_provider(provider):
        master_key = provider.get_master_key()
    minted = mint_recovery_envelope(dek=master_key, created_at=utc_now())
    save_recovery_envelope(minted.envelope, path)
    _mark_active_profile_recovery_enrolled(resolved)
    return CustodyRecoveryEnrollment(recovery_path=path, mnemonic=minted.mnemonic, rotated=rotated)


def verify_recovery_code(*, mnemonic: str, settings: Settings | None = None) -> CustodyRecoveryVerification:
    """Verify ``mnemonic`` against the configured recovery wrapper and return a :class:`CustodyRecoveryVerification`."""
    path = recovery_wrap_path(settings)
    try:
        envelope = load_recovery_envelope(path)
        verified = verify_recovery_mnemonic(envelope=envelope, mnemonic=mnemonic)
    except (OSError, RecoveryVerificationError, SecretStoreError, StorageValidationError) as exc:
        _log.debug("recovery-code verification failed error_type=%s", type(exc).__name__, exc_info=True)
        return CustodyRecoveryVerification(recovery_path=path, verified=False)
    return CustodyRecoveryVerification(recovery_path=path, verified=verified)


def _file_provider_with_passphrase(
    *,
    settings: Settings,
    passphrase: str,
) -> FileFallbackMasterKeyProvider:
    return FileFallbackMasterKeyProvider(
        store_dir=Path(settings.cadrumo_secret_store_dir),
        passphrase_callback=lambda: passphrase,
    )


def _require_file_custody(settings: Settings) -> None:
    """Refuse a passphrase-change on a non-file secret-store backend.

    A passphrase change rewraps the master key under a new file passphrase, which
    only the encrypted-file backend supports. Keyring and unsecured custody are
    refused with a typed, remediating :class:`SecretStoreError` rather than
    crashing later against absent ``master.key`` / ``master.kdf`` artefacts.
    """
    provider = get_master_key_provider(settings_override=settings)
    if not isinstance(provider, FileFallbackMasterKeyProvider):
        raise SecretStoreError(
            "passphrase change requires the file secret-store backend; the resolved "
            f"backend {type(provider).__name__} is unsupported. Set "
            "CADRUMO_SECRET_STORE_BACKEND=file and retry.",
        )


def change_passphrase(
    *,
    current_passphrase: str,
    new_passphrase: str,
    settings: Settings | None = None,
) -> CustodyPassphraseChangeResult:
    """Rotate the file secret store's passphrase after verifying the current one.

    File custody only. The current passphrase is verified by unwrapping the master
    key under it; a wrong current passphrase raises
    :class:`~cadrumo.adapters.persistence.storage.MasterKeyPassphraseMismatchError`
    and the stored key is left untouched. Only after a successful unwrap is the
    store rewrapped under ``new_passphrase``. Neither passphrase is persisted or
    returned.

    Raises:
        SecretStoreError: When the resolved backend is not file custody.
        MasterKeyPassphraseMismatchError: When ``current_passphrase`` does not
            unwrap the stored master key.
        MasterKeyMaterialMissingError: When the store is unprovisioned or torn.
    """
    resolved = _settings(settings)
    _require_file_custody(resolved)
    verifying_provider = _file_provider_with_passphrase(settings=resolved, passphrase=current_passphrase)
    master_key = verifying_provider.get_master_key()
    new_provider = _file_provider_with_passphrase(settings=resolved, passphrase=new_passphrase)
    new_provider.complete_recovery(master_key)
    with activate_master_key_provider(new_provider):
        pass
    return CustodyPassphraseChangeResult(
        secret_store_dir=Path(resolved.cadrumo_secret_store_dir),
        changed=True,
    )


def recover_secret_store(
    *,
    mnemonic: str,
    new_passphrase: str,
    settings: Settings | None = None,
) -> CustodyRecoverResult:
    """Recover the master key from ``mnemonic`` and return a :class:`CustodyRecoverResult`."""
    resolved = _settings(settings)
    path = recovery_wrap_path(resolved)
    envelope = load_recovery_envelope(path)
    master_key = unwrap_recovery_envelope(envelope=envelope, mnemonic=mnemonic)
    new_provider = _file_provider_with_passphrase(settings=resolved, passphrase=new_passphrase)
    new_provider.complete_recovery(master_key)
    with activate_master_key_provider(new_provider):
        pass
    return CustodyRecoverResult(
        recovery_path=path,
        secret_store_dir=Path(resolved.cadrumo_secret_store_dir),
        recovered=True,
    )


def recover_secret_store_with_callback(
    *,
    mnemonic: str,
    passphrase_callback: Callable[[], str],
    settings: Settings | None = None,
) -> CustodyRecoverResult:
    """Recover the master key using a caller-owned passphrase callback and return a :class:`CustodyRecoverResult`."""
    return recover_secret_store(
        mnemonic=mnemonic,
        new_passphrase=passphrase_callback(),
        settings=settings,
    )


__all__ = [
    "CustodyPassphraseChangeResult",
    "CustodyRecoverResult",
    "CustodyRecoveryEnrollment",
    "CustodyRecoveryStatus",
    "CustodyRecoveryVerification",
    "change_passphrase",
    "inspect_recovery_status",
    "mint_recovery_code",
    "recover_secret_store",
    "recover_secret_store_with_callback",
    "recovery_wrap_path",
    "verify_recovery_code",
]
