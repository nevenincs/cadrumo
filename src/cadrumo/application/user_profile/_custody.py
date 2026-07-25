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

Every operation here resolves the secret-store passphrase through an explicit
callback rather than letting the storage substrate pick its own: the
interactive door supplies a guarded terminal prompt, a programmatic driver
supplies a fixed value or accepts the non-interactive resolver below. The
substrate's own resolver ends in an unguarded terminal read, so inheriting it
would put a blocking, potentially echoing prompt behind a custody mutation.

These operations run without a login session and without the failed-attempt
backoff that guards profile login. That exemption is deliberate, not an
oversight. Any caller able to invoke them already holds same-user read access
to the ``master.key`` and ``master.kdf`` artefacts and can mount the identical
Argon2id attack offline at the same cost, so throttling this surface would
confer no protection at all; and the recovery mnemonic carries 256 bits of
entropy drawn from :func:`secrets.token_bytes`, which is not guessable at any
rate. The tripwire is reachability: if these operations ever become remotely
or cross-user reachable, the offline-equivalence argument collapses and the
failed-attempt backoff MUST be extended to cover them.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import (
    RecoveryVerificationError,
    SecretStoreError,
    StorageValidationError,
)
from ...adapters.persistence.storage.master_key import (
    FileFallbackMasterKeyProvider,
    PassphraseCallback,
    RecoveryEnrollmentOutcome,
    activate_master_key_provider,
    get_master_key_provider,
    recovery_create,
    recovery_recover,
    recovery_rotate,
    recovery_status,
    recovery_verify,
    zeroise,
)
from ...core import STRICT_FROZEN_CONFIG, resolve_active_bucket_id
from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ...core.time import now as utc_now
from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)

_RECOVERY_WRAP_FILENAME = "master.recovery.key"
_CUSTODY_ACTOR = "operator"
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
    """Inspect whether the configured recovery wrapper exists and return a :class:`CustodyRecoveryStatus`.

    The envelope file on disk is the single source of truth for whether
    recovery is enrolled. The active profile manifest also carries a
    ``recovery_enrolled`` mirror of that fact, written in a separate,
    necessarily non-atomic step after the envelope is installed — so a
    process killed between the two writes leaves the mirror disagreeing
    with disk. Reading the status reconciles the mirror against the
    envelope, in both directions, so the drift is self-healing on the
    natural read path rather than persisting until the next enrollment.
    """
    path = recovery_wrap_path(settings)
    status = recovery_status(path=path)
    _reconcile_active_profile_recovery_flag(settings=_settings(settings), enrolled=status.enrolled)
    return CustodyRecoveryStatus(
        recovery_path=path,
        recovery_enrolled=status.enrolled,
        recovery_fingerprint=status.recovery_fingerprint,
    )


def _emit_custody_event(
    *,
    event_type: BucketEventType,
    payload: dict[str, str],
) -> None:
    """Append one non-secret custody audit event to the active bucket's history.

    Passphrase rotation and the recovery-code lifecycle govern access to
    everything else the vault holds, so each durable mutation leaves a
    queryable trail an operator (or an investigator after a suspected
    compromise) can read back through ``aeat config profile history``.

    ``payload`` MUST carry only non-secret witnesses — the recovery
    fingerprint, the store location. No passphrase, mnemonic, or key
    material is ever recorded.

    The trail records the mutation; it never gates it. The event history is
    per-bucket encrypted storage, so it is only reachable while a profile is
    unlocked — and ``recover_secret_store`` runs precisely when the operator
    *cannot* unlock one. A missing profile selection or an unready storage
    runtime therefore degrades to a logged no-op: refusing here would fail an
    already-durable custody mutation, and would make the recovery path depend
    on the very access it exists to restore. Any other failure still raises.
    """
    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        _log.debug("custody audit event %s not recorded: no active profile", event_type.value)
        return
    occurred_at = utc_now()
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=_CUSTODY_ACTOR,
            object_type=BucketEventObjectType.BUCKET,
            object_id=bucket_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=_CUSTODY_ACTOR,
        object_type=BucketEventObjectType.BUCKET,
        object_id=bucket_id,
        payload_version=1,
        payload=payload,
    )
    try:
        events = BucketEventHistoryRepository()
        events.save(append_bucket_event(events.load(), event))
    except StorageValidationError:
        _log.debug(
            "custody audit event %s not recorded: profile storage is locked",
            event_type.value,
            exc_info=True,
        )


def _reconcile_active_profile_recovery_flag(*, settings: Settings, enrolled: bool) -> None:
    """Align the active profile manifest's ``recovery_enrolled`` mirror with ``enrolled``.

    ``enrolled`` is the ground truth read from the recovery envelope on
    disk. The manifest flag is only a mirror: it is written in a separate
    step from the envelope install, and two files in different directories
    cannot be written atomically together, so the mirror can drift in
    either direction — a process killed after the envelope lands leaves it
    reading false while a genuinely enrolled envelope exists, and an
    envelope removed out of band leaves it reading true with nothing behind
    it. Reconciling from the envelope repairs both, and does so no matter
    what caused the drift.

    Writes only on an actual mismatch, so the common path is a read.

    Best-effort by design. The mirror feeds operator-facing status display,
    never a security gate — the recovery status and verify authorities both
    read the envelope directly — so a locked, absent, or unreadable profile
    store must never turn a read-only status query into a failure. Any such
    condition is logged and the reported status still stands on the
    envelope.
    """
    from ...adapters.persistence.storage.bucket import bucket_paths, read_manifest, write_manifest

    active_profile = resolve_active_bucket_id()
    if active_profile is None:
        return
    try:
        paths = bucket_paths(Path(settings.cadrumo_local_storage_root), active_profile)
        manifest = read_manifest(paths)
        if manifest.recovery_enrolled is enrolled:
            return
        write_manifest(paths, manifest.model_copy(update={"recovery_enrolled": enrolled}))
    except (OSError, StorageValidationError):
        _log.debug(
            "recovery-enrollment manifest mirror not reconciled to %s: profile storage unavailable",
            enrolled,
            exc_info=True,
        )


def _mark_active_profile_recovery_enrolled(settings: Settings) -> None:
    """Mirror recovery enrollment into the active profile manifest."""
    _reconcile_active_profile_recovery_flag(settings=settings, enrolled=True)


def _configured_passphrase_callback(settings: Settings) -> PassphraseCallback:
    """Return a resolver for the configured secret-store passphrase that never prompts.

    Bound to the ``settings`` the calling operation already resolved, so a
    caller-supplied override is honoured instead of being silently re-read from
    the process environment.

    Deliberately incapable of prompting. Enrollment must unwrap the master key
    before it can mint a candidate envelope, and the storage substrate's own
    resolver ends in a bare terminal read carrying no real-console precondition
    and no promotion of an echo-suppression failure to a refusal. A programmatic
    driver that configures no passphrase therefore gets a typed refusal here
    rather than a prompt it cannot answer; an interactive caller supplies its
    own guarded prompt and never reaches this resolver.
    """

    def _resolve() -> str:
        configured = settings.cadrumo_secret_passphrase
        if configured is None:
            raise SecretStoreError(
                "no secret-store passphrase is available for this custody operation; "
                "pass an explicit passphrase_callback, or configure the secret-store "
                "passphrase in the settings environment before enrolling a recovery code.",
            )
        return configured.get_secret_value().rstrip("\r\n")

    return _resolve


def create_recovery_code(
    *,
    confirm: Callable[[str], str],
    passphrase_callback: PassphraseCallback | None = None,
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

    ``passphrase_callback`` resolves the existing secret-store passphrase that
    unwraps the master key. An interactive caller MUST supply one — the CLI
    supplies its hardened no-echo terminal prompt — so the enrollment never
    inherits the storage substrate's unguarded terminal read. Omitting it
    selects :func:`_configured_passphrase_callback`, which reads the configured
    passphrase and refuses when none is set; it never prompts, so a
    programmatic driver cannot silently acquire an interactive prompt.
    """
    return _enroll_recovery_code(
        operation=recovery_create,
        confirm=confirm,
        passphrase_callback=passphrase_callback,
        settings=settings,
        event_type=BucketEventType.CUSTODY_RECOVERY_CODE_CREATED,
    )


def rotate_recovery_code(
    *,
    confirm: Callable[[str], str],
    passphrase_callback: PassphraseCallback | None = None,
    settings: Settings | None = None,
) -> CustodyRecoveryEnrollmentResult:
    """Replace the enrolled recovery code and return a :class:`CustodyRecoveryEnrollmentResult`.

    Same two-phase shape as :func:`create_recovery_code`, including the same
    ``passphrase_callback`` contract; but requires an existing enrollment, and
    the prior envelope survives untouched until the operator's retype fully
    verifies the fresh candidate.
    """
    return _enroll_recovery_code(
        operation=recovery_rotate,
        confirm=confirm,
        passphrase_callback=passphrase_callback,
        settings=settings,
        event_type=BucketEventType.CUSTODY_RECOVERY_CODE_ROTATED,
    )


def _enroll_recovery_code(
    *,
    operation: Callable[..., RecoveryEnrollmentOutcome],
    confirm: Callable[[str], str],
    passphrase_callback: PassphraseCallback | None,
    settings: Settings | None,
    event_type: BucketEventType,
) -> CustodyRecoveryEnrollmentResult:
    resolved = _settings(settings)
    path = recovery_wrap_path(resolved)
    # The callback is threaded explicitly rather than left to the provider's own
    # default, which resolves the passphrase through a bare terminal read: on a
    # console-less host that read blocks forever, and where echo suppression
    # cannot be established it degrades to an echoing read. Neither outcome is
    # acceptable behind a custody mutation, so no enrollment inherits it.
    provider = get_master_key_provider(
        settings_override=resolved,
        passphrase_callback=(
            passphrase_callback if passphrase_callback is not None else _configured_passphrase_callback(resolved)
        ),
    )
    outcome = operation(provider=provider, path=path, created_at=utc_now(), confirm=confirm)
    # The envelope is durably installed here; the audit trail is recorded before
    # the separate, non-atomic manifest-flag write so a crash between the two
    # still leaves evidence of the enrollment that actually happened.
    _emit_custody_event(
        event_type=event_type,
        payload={
            "recovery_fingerprint": outcome.recovery_fingerprint,
            "rotated": str(outcome.rotated).lower(),
        },
    )
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
    # Verification reads the envelope and unwraps it with the mnemonic alone, so
    # this provider is only narrowed to the file backend and never asked for the
    # master key — no passphrase is resolved on this path today. The explicit
    # non-interactive callback keeps that true by construction: a later change
    # that does reach the master key gets a typed refusal rather than silently
    # inheriting the substrate's unguarded terminal read.
    provider = get_master_key_provider(
        settings_override=resolved,
        passphrase_callback=_configured_passphrase_callback(resolved),
    )
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

    The probe provider is narrowed and discarded without ever being asked for
    the master key; the explicit non-interactive callback keeps it that way,
    so a backend check can never turn into a prompt.
    """
    provider = get_master_key_provider(
        settings_override=settings,
        passphrase_callback=_configured_passphrase_callback(settings),
    )
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
    # The unwrapped master key is copied into a wipeable buffer and zeroed as
    # soon as it has been rewrapped, so the plaintext DEK does not linger in an
    # immutable object for the garbage collector to release at its leisure. A
    # passphrase change is one of the three recovery-surface operations that
    # opens this window, alongside recovery mint and unwrap.
    master_key = bytearray(verifying_provider.get_master_key())
    try:
        new_provider = _file_provider_with_passphrase(settings=resolved, passphrase=new_passphrase)
        new_provider.complete_recovery(bytes(master_key))
    finally:
        zeroise(master_key)
    with activate_master_key_provider(new_provider):
        pass
    _emit_custody_event(
        event_type=BucketEventType.CUSTODY_PASSPHRASE_CHANGED,
        payload={"secret_store_dir": str(resolved.cadrumo_secret_store_dir)},
    )
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
    _emit_custody_event(
        event_type=BucketEventType.CUSTODY_SECRET_STORE_RECOVERED,
        payload={"secret_store_dir": str(resolved.cadrumo_secret_store_dir)},
    )
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
