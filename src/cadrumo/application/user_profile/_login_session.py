"""Profile login orchestration over the persisted-session substrate.

``aeat config login`` is the single door through which a taxpayer
authenticates a profile. This module composes the already-canonical
primitives — it owns no crypto and no second write path:

- the UUID-or-exact-label profile resolver
  (:func:`~cadrumo.application.workflow.read_profile_bucket_by_id` /
  :func:`~cadrumo.application.workflow.read_profile_bucket`),
- the pointer transaction
  (:func:`active_profile_pointer_transaction`, entered FIRST so the
  project-wide pointer-then-bucket lock order is preserved),
- the failed-login throttle
  (:func:`~cadrumo.adapters.persistence.storage.master_key.evaluate_login_throttle`,
  evaluated BEFORE any Argon2id derivation so the key-derivation function
  can never become a passphrase-testing oracle),
- the master-key provider (:class:`MasterKeyProvider`), whose
  ``get_master_key`` unwrap IS the authentication: the outcome derives
  solely from AEAD success, so a wrong passphrase surfaces as an unwrap
  failure rather than any comparison of secret strings. This module then
  opens the
  :class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`
  itself rather than through the provider's ``with`` block, because a
  login session must outlive this call, and
- the session-wrapped-DEK record
  (:func:`~cadrumo.adapters.persistence.storage.master_key.mint_profile_session`
  / :func:`~cadrumo.adapters.persistence.storage.master_key.resume_profile_session`)
  that carries the "logged in" state across CLI processes.

Login is idempotent-guarded: a login for a profile whose persisted
session is still valid resumes that session as a no-op — no re-prompt, no
second record, no re-stamped ``authenticated_at``. A login naming a
DIFFERENT profile first tears the previous profile's session down.

:func:`resume_active_profile_session` is the read-side counterpart and the
SINGLE resume authority: both the login no-op path and the CLI root
callback call it, so the two surfaces cannot drift.

See Also:
    :mod:`cadrumo.adapters.persistence.storage.master_key._persisted_session`
        The split-knowledge session record this module mints and resumes.
    :func:`~cadrumo.application.user_profile.logout_active_profile`
        The symmetric strong close, which reuses
        :func:`close_profile_session_artefacts` from here.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...adapters.persistence.storage.master_key import (
    BucketSession,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    advance_profile_session_idle_deadline,
    bind_active_bucket_session,
    close_active_bucket_session,
    current_active_bucket_session,
    delete_profile_session,
    evaluate_login_throttle,
    idle_minutes_for_bucket,
    load_profile_session_key,
    mint_profile_session,
    record_login_failure,
    reset_login_throttle,
    resume_profile_session,
    session_absolute_minutes_for_bucket,
    write_profile_session,
)
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BucketPointer, ProfileSessionRefusalReason
from ...core.config import SecretStoreBackend, load_settings
from ...core.logging import get_logger
from ...core.time import now as _now
from ...domain.user_profile import ProfileNotFoundError, UserProfileError
from ._profile_pointer_transaction import ActiveProfilePointerTransaction, active_profile_pointer_transaction

if TYPE_CHECKING:
    from ...adapters.persistence.storage.master_key import MasterKeyProvider, PassphraseCallback
    from ..workflow import ProfileBucketPointer

_log = get_logger(__name__)


class ProfileLoginThrottledError(UserProfileError):
    """Refuse a login attempt while the failed-attempt backoff is in force.

    Raised BEFORE any Argon2id derivation runs, so a caller hammering
    passphrases cannot use the key-derivation function as a timing
    oracle. The remaining wait rides in ``context`` so the CLI can render
    it without re-parsing the message.
    """

    def __init__(self, *, remaining_seconds: int) -> None:
        """Initialise the refusal with the operator's remaining wait."""
        super().__init__(
            translated_message="errors.refused.refused_profile_login_throttled",
            context={"seconds": str(remaining_seconds)},
        )
        self.remaining_seconds = remaining_seconds


class ProfileLoginOutcome(BaseModel):
    """Typed result of one ``login`` invocation.

    Carries no key material: the unlocked
    :class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`
    is bound to the process through the active-session context variable,
    never to this record.

    Attributes:
        bucket_id: Immutable UUID identity of the authenticated profile.
        label: Operator-facing display label of that profile.
        backend_kind: Custody backend that performed the authentication.
        authenticated_at: UTC instant the session was established. On an
            idempotent no-op this is the ORIGINAL login instant, never
            re-stamped.
        idle_deadline: Current sliding idle deadline.
        absolute_deadline: Immutable absolute session cap.
        session_persisted: ``False`` when the host has no usable OS
            keychain, so the session is process-scoped only.
        already_authenticated: ``True`` when a still-valid persisted
            session was resumed as a no-op (no re-prompt, no new record).
        closed_previous_bucket_id: Bucket whose session this login closed
            during a cross-profile handover, or ``None``.
    """

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    label: str
    backend_kind: SecretStoreBackend
    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    session_persisted: bool
    already_authenticated: bool
    closed_previous_bucket_id: str | None = None


def _storage_root() -> Path:
    return load_settings().cadrumo_local_storage_root


def _backend_kind(provider: MasterKeyProvider) -> SecretStoreBackend:
    """Map a live provider instance to its closed backend-kind member."""
    if isinstance(provider, KeyringMasterKeyProvider):
        return SecretStoreBackend.KEYRING
    if isinstance(provider, FileFallbackMasterKeyProvider):
        return SecretStoreBackend.FILE
    return SecretStoreBackend.UNSECURED


def _session_windows(*, storage_root: Path, bucket_id: str) -> tuple[int, int]:
    """Return ``(idle_minutes, absolute_minutes)`` for one bucket.

    Reads through the same manifest-then-settings resolvers the provider
    enter path uses, so the persisted record's deadlines are identical to
    the live session's rather than independently re-derived.
    """
    settings = load_settings()
    idle_minutes = idle_minutes_for_bucket(
        storage_root=storage_root,
        bucket_id=bucket_id,
        default_minutes=settings.cadrumo_bucket_default_idle_lock_minutes,
    )
    absolute_minutes = session_absolute_minutes_for_bucket(
        storage_root=storage_root,
        bucket_id=bucket_id,
        default_minutes=settings.cadrumo_bucket_default_session_absolute_minutes,
    )
    return idle_minutes, absolute_minutes


def close_profile_session_artefacts(*, storage_root: Path, bucket_id: str) -> None:
    """Tear down every session artefact owned by ``bucket_id`` (idempotent).

    The single authority for "this profile is no longer logged in":
    deletes the on-disk session record AND its OS-keychain session key
    (split knowledge, so either alone is already useless) and clears the
    failed-login backoff. Composed by both the cross-profile handover in
    :func:`login_profile` and the strong close in
    :func:`~cadrumo.application.user_profile.logout_active_profile`, so
    neither surface owns a second teardown path.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the profile whose session to tear down.
    """
    delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)
    reset_login_throttle(storage_root=storage_root, bucket_id=bucket_id)


def resume_active_profile_session(
    *,
    bucket_id: str,
    now: datetime | None = None,
) -> ProfileSessionRefusalReason | None:
    """Resume ``bucket_id``'s persisted session and bind it to this process.

    The SINGLE resume authority, shared by the login idempotence guard and
    the CLI root callback so the two can never drift. Fail-closed
    throughout: the adapter deletes stale artefacts and reports a typed
    refusal, and this function opens NOTHING on any refusal branch.

    On success the sliding idle deadline is advanced and re-persisted
    exactly once, so activity in a later process keeps the session alive
    without re-writing the record on every storage access.

    Args:
        bucket_id: Identifier of the profile whose session to resume.
        now: UTC evaluation instant; the canonical clock when omitted.

    Returns:
        ``None`` when the session resumed and is now the active
        :class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`,
        otherwise the typed
        :class:`~cadrumo.core.ProfileSessionRefusalReason` naming why not.
    """
    instant = _now() if now is None else now
    storage_root = _storage_root()
    outcome, dek = resume_profile_session(storage_root=storage_root, bucket_id=bucket_id, now=instant)
    if not outcome.resumed or outcome.record is None or dek is None:
        return outcome.refusal if outcome.refusal is not None else ProfileSessionRefusalReason.ABSENT

    record = outcome.record
    dek_buffer = bytearray(dek)
    try:
        idle_minutes, _ = _session_windows(storage_root=storage_root, bucket_id=bucket_id)
        session = BucketSession.open_resumed(
            bucket_id=bucket_id,
            dek=bytes(dek_buffer),
            idle_minutes=idle_minutes,
            opened_at=record.authenticated_at,
            idle_deadline=record.idle_deadline,
            absolute_deadline=record.absolute_deadline,
            storage_root=storage_root,
        )
    finally:
        from ...adapters.persistence.storage.master_key import zeroise

        zeroise(dek_buffer)

    session.touch(instant)
    bind_active_bucket_session(session)
    _persist_advanced_idle_deadline(
        storage_root=storage_root,
        bucket_id=bucket_id,
        record=record,
        new_idle_deadline=session.idle_deadline,
    )
    return None


def _persist_advanced_idle_deadline(
    *,
    storage_root: Path,
    bucket_id: str,
    record: object,
    new_idle_deadline: datetime,
) -> None:
    """Re-persist the record once with its idle deadline rolled forward.

    Best-effort by design: the live session is already open and correct,
    so a keychain or disk hiccup here must not fail the operator's verb —
    it only costs an earlier idle expiry, which is the fail-closed
    direction.
    """
    from ...adapters.persistence.storage.master_key import PersistedProfileSession

    if not isinstance(record, PersistedProfileSession):  # pragma: no cover - typed at the call site
        return
    if new_idle_deadline <= record.idle_deadline:
        return
    session_key = load_profile_session_key(bucket_id=bucket_id)
    if session_key is None:
        return
    key_buffer = bytearray(session_key)
    del session_key
    try:
        advanced = advance_profile_session_idle_deadline(
            record=record,
            session_key=bytes(key_buffer),
            new_idle_deadline=new_idle_deadline,
        )
        write_profile_session(storage_root=storage_root, bucket_id=bucket_id, record=advanced)
    except (OSError, ValueError) as exc:
        _log.debug(
            "profile-session idle-deadline re-persist skipped bucket_id=%s error_type=%s",
            bucket_id,
            type(exc).__name__,
        )
    finally:
        from ...adapters.persistence.storage.master_key import zeroise

        zeroise(key_buffer)


def _resolve_login_target(name: str) -> ProfileBucketPointer:
    """Resolve a ``login NAME`` target from an unambiguous UUID or exact label.

    Mirrors the accepted profile-selector contract: the immutable bucket
    UUID, or the exact operator label including a sandbox's canonical
    ``sandbox:<name>`` label. A bare sandbox short name carries no
    ``sandbox:`` prefix, so it matches no bucket and is refused rather
    than implicitly namespaced. A tombstoned UUID falls through to the
    label resolver, which excludes tombstoned profiles.
    """
    from ...domain.user_profile import UserProfileStatus
    from ..workflow import read_profile_bucket, read_profile_bucket_by_id

    trimmed = name.strip()
    if not trimmed:
        raise ProfileNotFoundError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        )
    by_id = read_profile_bucket_by_id(trimmed)
    if by_id is not None and by_id.status is not UserProfileStatus.TOMBSTONED:
        return by_id
    pointer = read_profile_bucket(trimmed)
    if pointer is None:
        raise ProfileNotFoundError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": trimmed},
        )
    return pointer


def _resolve_selected_target(pointer: BucketPointer | None) -> ProfileBucketPointer:
    """Resolve the already-selected profile for a bare ``login``."""
    from ..workflow import read_profile_bucket_by_id

    if pointer is None:
        raise ProfileNotFoundError(
            translated_message="application.user_profile.errors.no_active_profile_selected",
        )
    resolved = read_profile_bucket_by_id(pointer.bucket_id)
    if resolved is None:
        raise ProfileNotFoundError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": pointer.bucket_id},
        )
    return resolved


def login_profile(
    *,
    name: str | None = None,
    now: datetime | None = None,
    passphrase_callback: PassphraseCallback | None = None,
) -> ProfileLoginOutcome:
    """Select, authenticate, and mint the persisted session for one profile.

    The whole operation runs inside the active-profile pointer
    transaction, entered before any bucket or session work so the
    project-wide pointer-then-bucket lock order holds.

    Ordering is load-bearing:

    1. resolve the target (``NAME`` by UUID-or-exact-label, else the
       already-selected profile; no selection refuses naming ``login NAME``);
    2. close the previous profile's session when the target differs;
    3. return the existing session as a no-op when the target's persisted
       session is still valid (idempotent guard — no re-prompt, no second
       record, no re-stamped ``authenticated_at``);
    4. evaluate the failed-login backoff BEFORE any Argon2id derivation;
    5. write the pointer, then authenticate by unwrapping (the provider's
       enter path), restoring the prior pointer bytes and recording the
       failure if the unwrap refuses;
    6. clear the backoff and mint the session-wrapped-DEK record.

    Args:
        name: Optional profile UUID or exact display label to select. When
            omitted the already-selected profile is authenticated.
        now: UTC evaluation instant; the canonical clock when omitted.
        passphrase_callback: Optional passphrase resolver for the file
            backend (the CLI injects its ``--secrets-stdin`` channel).

    Returns:
        The typed :class:`ProfileLoginOutcome`.

    Raises:
        ProfileNotFoundError: When no target resolves.
        ProfileLoginThrottledError: While the failed-attempt backoff holds.
        MasterKeyPassphraseMismatchError: When the passphrase does not
            unwrap the master key (uniform across buckets by construction).
    """
    from ...adapters.persistence.storage.master_key import get_master_key_provider

    instant = _now() if now is None else now
    storage_root = _storage_root()

    with active_profile_pointer_transaction() as pointer_transaction:
        selected = pointer_transaction.read()
        target = _resolve_login_target(name) if name is not None else _resolve_selected_target(selected)

        closed_previous: str | None = None
        if selected is not None and selected.bucket_id != target.bucket_id:
            close_active_bucket_session()
            close_profile_session_artefacts(storage_root=storage_root, bucket_id=selected.bucket_id)
            closed_previous = selected.bucket_id

        prior_pointer = pointer_transaction.capture()
        if selected is None or selected.bucket_id != target.bucket_id:
            pointer_transaction.write(BucketPointer(bucket_id=target.bucket_id, schema_version=1))

        resumed = _resume_for_idempotent_login(bucket_id=target.bucket_id, now=instant)
        if resumed is not None:
            return ProfileLoginOutcome(
                bucket_id=target.bucket_id,
                label=target.label,
                backend_kind=resumed.backend_kind,
                authenticated_at=resumed.authenticated_at,
                idle_deadline=resumed.idle_deadline,
                absolute_deadline=resumed.absolute_deadline,
                session_persisted=True,
                already_authenticated=True,
                closed_previous_bucket_id=closed_previous,
            )

        evaluation = evaluate_login_throttle(
            storage_root=storage_root,
            bucket_id=target.bucket_id,
            now=instant,
        )
        if evaluation.throttled:
            pointer_transaction.restore(prior_pointer)
            raise ProfileLoginThrottledError(remaining_seconds=evaluation.remaining_seconds)

        provider = get_master_key_provider(passphrase_callback=passphrase_callback)
        session = _authenticate_or_record_failure(
            provider=provider,
            bucket_id=target.bucket_id,
            storage_root=storage_root,
            now=instant,
            pointer_transaction=pointer_transaction,
            prior_pointer=prior_pointer,
        )
        reset_login_throttle(storage_root=storage_root, bucket_id=target.bucket_id)

        backend_kind = _backend_kind(provider)
        idle_minutes, absolute_minutes = _session_windows(storage_root=storage_root, bucket_id=target.bucket_id)
        persisted = _mint_or_warn(
            storage_root=storage_root,
            bucket_id=target.bucket_id,
            backend_kind=backend_kind,
            session=session,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
        )
        return ProfileLoginOutcome(
            bucket_id=target.bucket_id,
            label=target.label,
            backend_kind=backend_kind,
            authenticated_at=session.opened_at,
            idle_deadline=session.idle_deadline,
            absolute_deadline=session.absolute_deadline,
            session_persisted=persisted,
            already_authenticated=False,
            closed_previous_bucket_id=closed_previous,
        )


def _resume_for_idempotent_login(*, bucket_id: str, now: datetime):
    """Return the resumed record when the idempotent-login guard applies.

    A live session already bound to this bucket is itself the no-op
    signal; otherwise the persisted record is resumed through the shared
    :func:`resume_active_profile_session` authority. Returns ``None`` when
    the profile is genuinely logged out and must authenticate.
    """
    from ...adapters.persistence.storage.master_key import resume_profile_session as _peek

    live = current_active_bucket_session()
    if live is not None and live.bucket_id == bucket_id and not live.is_expired(now):
        peeked, _ = _peek(storage_root=_storage_root(), bucket_id=bucket_id, now=now)
        return peeked.record if peeked.resumed else None
    if resume_active_profile_session(bucket_id=bucket_id, now=now) is not None:
        return None
    peeked, _ = _peek(storage_root=_storage_root(), bucket_id=bucket_id, now=now)
    return peeked.record if peeked.resumed else None


def _authenticate_or_record_failure(
    *,
    provider: MasterKeyProvider,
    bucket_id: str,
    storage_root: Path,
    now: datetime,
    pointer_transaction: ActiveProfilePointerTransaction,
    prior_pointer: bytes | None,
) -> BucketSession:
    """Unwrap the key material and bind the session for the whole process.

    ``provider.get_master_key()`` IS the authentication: the outcome
    derives solely from AEAD unwrap success, so verification is
    constant-time by construction and no secret strings are compared. A
    refusal increments the backoff and restores the pointer bytes captured
    before the write, so a failed login never leaves a profile selected
    that could not be unlocked.

    The session is opened and bound here rather than through the provider
    context manager because a login session is deliberately UNSCOPED: it
    must outlive this call and every later process, and is evicted only by
    ``logout``, by expiry, or at interpreter exit. The scoped
    provider-activation path stays the authority for ``with``-bound
    callers; both compose the identical primitives (the same DEK unwrap,
    window resolvers, and unsecured-backend NIF canary), so neither owns a
    divergent open.
    """
    from ...adapters.persistence.storage.errors import (
        KeyringUnavailableError,
        MasterKeyKeychainLockedError,
        MasterKeyMaterialMissingError,
        MasterKeyPassphraseMismatchError,
    )
    from ...adapters.persistence.storage.master_key import (
        UnsecuredMasterKeyProvider,
        load_or_mint_bucket_dek,
        refuse_unsecured_bucket_with_real_profile,
        zeroise,
    )

    try:
        key_bytes = provider.get_master_key()
    except (
        MasterKeyPassphraseMismatchError,
        MasterKeyKeychainLockedError,
        KeyringUnavailableError,
        MasterKeyMaterialMissingError,
    ):
        record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)
        pointer_transaction.restore(prior_pointer)
        raise
    except BaseException:
        pointer_transaction.restore(prior_pointer)
        raise

    kek_buffer = bytearray(key_bytes)
    del key_bytes
    try:
        unsecured = isinstance(provider, UnsecuredMasterKeyProvider)
        dek_buffer = bytearray(
            bytes(kek_buffer)
            if unsecured
            else load_or_mint_bucket_dek(
                kek=bytes(kek_buffer),
                storage_root=storage_root,
                bucket_id=bucket_id,
                allow_bootstrap_mint=False,
            ),
        )
        try:
            idle_minutes, absolute_minutes = _session_windows(storage_root=storage_root, bucket_id=bucket_id)
            session = BucketSession.open(
                bucket_id=bucket_id,
                kek=bytes(kek_buffer),
                dek=bytes(dek_buffer),
                idle_minutes=idle_minutes,
                absolute_minutes=absolute_minutes,
                opened_at=now,
                unsecured_backend=unsecured,
                storage_root=storage_root,
            )
        finally:
            zeroise(dek_buffer)
    except BaseException:
        pointer_transaction.restore(prior_pointer)
        raise
    finally:
        zeroise(kek_buffer)

    bind_active_bucket_session(session)
    try:
        if session.unsecured_backend:
            refuse_unsecured_bucket_with_real_profile(session)
    except BaseException:
        close_active_bucket_session()
        pointer_transaction.restore(prior_pointer)
        raise
    return session


def _mint_or_warn(
    *,
    storage_root: Path,
    bucket_id: str,
    backend_kind: SecretStoreBackend,
    session: BucketSession,
    idle_minutes: int,
    absolute_minutes: int,
) -> bool:
    """Mint the persisted session, or report a process-scoped login.

    A host with no usable OS keychain has nowhere secure to custody the
    session key, so no persisted artefact is written at all — failing
    closed beats writing key material to disk. The login still succeeds
    for this process; the caller surfaces the warning.
    """
    from ...adapters.persistence.storage.errors import KeyringUnavailableError

    try:
        mint_profile_session(
            storage_root=storage_root,
            bucket_id=bucket_id,
            backend_kind=backend_kind,
            dek=session.dek,
            now=session.opened_at,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
        )
    except KeyringUnavailableError:
        _log.info(
            "profile session not persisted (no usable OS keychain); login is process-scoped bucket_id=%s",
            bucket_id,
        )
        return False
    return True


__all__ = [
    "ProfileLoginOutcome",
    "ProfileLoginThrottledError",
    "close_profile_session_artefacts",
    "login_profile",
    "resume_active_profile_session",
]
