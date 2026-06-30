"""Application-owned custody operations for the profile secret store.

The config CLI calls this module for recovery-code minting,
verification, rekey, and recovery. Storage primitives stay in
:mod:`aeat.adapters.persistence.storage`; this layer resolves
:class:`~aeat.core.config.Settings`, updates the active profile manifest
when recovery is enrolled, and returns typed application result records.

Plaintext recovery words are returned only from
:func:`mint_recovery_code`. They are never persisted by this module; the
secret store keeps only wrapped recovery material. Verification failures
from :class:`~aeat.adapters.persistence.storage.RecoveryVerificationError`
and related storage errors are rendered as a false verification result
rather than leaking backend exception details.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ...adapters.persistence.storage import RecoveryVerificationError
from ...adapters.persistence.storage.errors import SecretStoreError, StorageValidationError
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


class CustodyRekeyResult(BaseModel):
    """Result of rewrapping the master key under a new file-backend passphrase."""

    model_config = STRICT_FROZEN_CONFIG

    secret_store_dir: Path
    rekeyed: bool


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
    return Path(_settings(settings).aeat_secret_store_dir) / _RECOVERY_WRAP_FILENAME


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
    paths = bucket_paths(Path(settings.aeat_local_storage_root), active_profile)
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


def _file_provider_for_new_passphrase(
    *,
    settings: Settings,
    new_passphrase: str,
) -> FileFallbackMasterKeyProvider:
    return FileFallbackMasterKeyProvider(
        store_dir=Path(settings.aeat_secret_store_dir),
        passphrase_callback=lambda: new_passphrase,
    )


def rekey_secret_store(
    *,
    new_passphrase: str,
    settings: Settings | None = None,
) -> CustodyRekeyResult:
    """Rewrap the current master key under ``new_passphrase`` and return a :class:`CustodyRekeyResult`."""
    resolved = _settings(settings)
    current_provider = get_master_key_provider(settings_override=resolved)
    with activate_master_key_provider(current_provider):
        master_key = current_provider.get_master_key()
    new_provider = _file_provider_for_new_passphrase(settings=resolved, new_passphrase=new_passphrase)
    new_provider.complete_recovery(master_key)
    with activate_master_key_provider(new_provider):
        pass
    return CustodyRekeyResult(secret_store_dir=Path(resolved.aeat_secret_store_dir), rekeyed=True)


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
    new_provider = _file_provider_for_new_passphrase(settings=resolved, new_passphrase=new_passphrase)
    new_provider.complete_recovery(master_key)
    with activate_master_key_provider(new_provider):
        pass
    return CustodyRecoverResult(
        recovery_path=path,
        secret_store_dir=Path(resolved.aeat_secret_store_dir),
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
    "CustodyRecoverResult",
    "CustodyRecoveryEnrollment",
    "CustodyRecoveryStatus",
    "CustodyRecoveryVerification",
    "CustodyRekeyResult",
    "inspect_recovery_status",
    "mint_recovery_code",
    "recover_secret_store",
    "recover_secret_store_with_callback",
    "recovery_wrap_path",
    "rekey_secret_store",
    "verify_recovery_code",
]
