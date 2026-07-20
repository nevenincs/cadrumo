"""Application-owned custody operations for the profile secret store.

The config CLI calls this module for the recovery-code lifecycle (status,
create, rotate, verify), passphrase change, and recovery. Storage primitives
stay in :mod:`cadrumo.adapters.persistence.storage`; this layer resolves
:class:`~cadrumo.core.config.Settings`, updates the active profile manifest
when recovery is enrolled, and returns typed application result records.

Plaintext recovery words never appear on any result record: enrollment hands
the candidate mnemonic to the caller-supplied ``confirm`` callback exactly
once and returns only the non-secret recovery fingerprint. Verification
failures from
:class:`~cadrumo.adapters.persistence.storage.RecoveryVerificationError` are
rendered as a false verification result rather than leaking backend exception
details.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ...adapters.persistence.storage import RecoveryVerificationError, SecretStoreError
from ...adapters.persistence.storage.master_key import (
    FileFallbackMasterKeyProvider,
    RecoveryEnrollmentOutcome,
    activate_master_key_provider,
    get_master_key_provider,
    recovery_create,
    recovery_recover,
    recovery_rotate,
    recovery_status,
    recovery_verify,
)
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ...core.time import now as utc_now

_RECOVERY_WRAP_FILENAME = "master.recovery.key"
_log = get_logger(__name__)


class CustodyRecoveryEnrollmentResult(BaseModel):
    """Result of a committed recovery ``create`` or ``rotate``.

    Carries only the persisted wrapper path, the non-secret recovery
    fingerprint, and whether a prior enrollment was replaced. The candidate
    mnemonic is never held on this record; the ``confirm`` callback displayed
    it during enrollment.
    """

    model_config = STRICT_FROZEN_CONFIG

    recovery_path: Path
    recovery_fingerprint: str
    rotated: bool


class CustodyRecoveryStatus(BaseModel):
    """Current recovery-wrapper status for the configured secret store."""

    model_config = STRICT_FROZEN_CONFIG

    recovery_path: Path
    recovery_enrolled: bool
    recovery_fingerprint: str | None = None


class CustodyRecoveryVerification(BaseModel):
    """Result of checking an operator-supplied recovery mnemonic."""

    model_config = STRICT_FROZEN_CONFIG

    recovery_path: Path
    verified: bool
    recovery_fingerprint: str | None = None


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
    status = recovery_status(path=path)
    return CustodyRecoveryStatus(
        recovery_path=path,
        recovery_enrolled=status.enrolled,
        recovery_fingerprint=status.recovery_fingerprint,
    )


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


def create_recovery_code(
    *,
    confirm: Callable[[str], str],
    settings: Settings | None = None,
) -> CustodyRecoveryEnrollmentResult:
    """Enroll a first recovery code and return a :class:`CustodyRecoveryEnrollmentResult`.

    ``confirm`` receives the candidate 24-word mnemonic exactly once (the
    caller writes it to the controlling terminal), returns the operator's
    no-echo retype, and may raise to cancel. The wrapper file is written only
    after the retype verifies against the staged envelope; an existing
    enrollment refuses with a typed
    :class:`~cadrumo.adapters.persistence.storage.SecretStoreError` naming the
    rotate path. The plaintext words are never persisted or returned.
    """
    return _enroll_recovery_code(operation=recovery_create, confirm=confirm, settings=settings)


def rotate_recovery_code(
    *,
    confirm: Callable[[str], str],
    settings: Settings | None = None,
) -> CustodyRecoveryEnrollmentResult:
    """Replace the enrolled recovery code and return a :class:`CustodyRecoveryEnrollmentResult`.

    Same two-phase shape as :func:`create_recovery_code`, but requires an
    existing enrollment; the prior envelope survives untouched until the
    operator's retype fully verifies the fresh candidate.
    """
    return _enroll_recovery_code(operation=recovery_rotate, confirm=confirm, settings=settings)


def _enroll_recovery_code(
    *,
    operation: Callable[..., RecoveryEnrollmentOutcome],
    confirm: Callable[[str], str],
    settings: Settings | None,
) -> CustodyRecoveryEnrollmentResult:
    resolved = _settings(settings)
    path = recovery_wrap_path(resolved)
    provider = get_master_key_provider(settings_override=resolved)
    outcome = operation(provider=provider, path=path, created_at=utc_now(), confirm=confirm)
    _mark_active_profile_recovery_enrolled(resolved)
    return CustodyRecoveryEnrollmentResult(
        recovery_path=path,
        recovery_fingerprint=outcome.recovery_fingerprint,
        rotated=outcome.rotated,
    )


def verify_recovery_code(*, mnemonic: str, settings: Settings | None = None) -> CustodyRecoveryVerification:
    """Verify ``mnemonic`` against the configured recovery wrapper and return a :class:`CustodyRecoveryVerification`.

    File custody only: a keyring or unsecured backend raises the facade's
    typed :class:`~cadrumo.adapters.persistence.storage.SecretStoreError`. A
    missing envelope, malformed envelope, or non-matching mnemonic is rendered
    as ``verified=False`` without leaking backend detail.
    """
    resolved = _settings(settings)
    path = recovery_wrap_path(resolved)
    provider = get_master_key_provider(settings_override=resolved)
    try:
        outcome = recovery_verify(provider=provider, path=path, mnemonic=mnemonic)
    except RecoveryVerificationError as exc:
        _log.debug("recovery-code verification failed error_type=%s", type(exc).__name__, exc_info=True)
        return CustodyRecoveryVerification(recovery_path=path, verified=False)
    return CustodyRecoveryVerification(
        recovery_path=path,
        verified=outcome.verified,
        recovery_fingerprint=outcome.recovery_fingerprint,
    )


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
    """Recover the master key from ``mnemonic`` and return a :class:`CustodyRecoverResult`.

    Routes through the storage facade's ``recovery_recover``: the master key is
    unwrapped from the persisted envelope and re-minted under a file provider
    bound to ``new_passphrase``. A non-matching mnemonic raises
    :class:`~cadrumo.adapters.persistence.storage.RecoveryVerificationError`
    and leaves the store untouched.
    """
    resolved = _settings(settings)
    path = recovery_wrap_path(resolved)
    new_provider = _file_provider_with_passphrase(settings=resolved, passphrase=new_passphrase)
    recovery_recover(provider=new_provider, path=path, mnemonic=mnemonic)
    with activate_master_key_provider(new_provider):
        pass
    return CustodyRecoverResult(
        recovery_path=path,
        secret_store_dir=Path(resolved.cadrumo_secret_store_dir),
        recovered=True,
    )


__all__ = [
    "CustodyPassphraseChangeResult",
    "CustodyRecoverResult",
    "CustodyRecoveryEnrollmentResult",
    "CustodyRecoveryStatus",
    "CustodyRecoveryVerification",
    "change_passphrase",
    "create_recovery_code",
    "inspect_recovery_status",
    "recover_secret_store",
    "recovery_wrap_path",
    "rotate_recovery_code",
    "verify_recovery_code",
]
