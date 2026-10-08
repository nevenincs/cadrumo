"""Local password custody and runtime-owned receipt admission.

Explicit password authentication binds process-local custody without changing
profile selection. Borrowed candidates leave publication to their runtime owner.
Shared receipt minting and supplied-proof admission belong to the authenticated
runtime lifecycle; custody deletion retains its exact-profile cleanup boundary.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from uuid import UUID

from pydantic import BaseModel

from ...core.config import load_settings
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.bucket import BucketId
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.paths import effective_storage_root
from ...core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal
from ...core.time.clock import now as _now
from ...domain.user_profile.errors import ProfileNotFoundError, UserProfileError
from .authentication import ProfilePasswordProofOperation
from .capsule_record import ProfileRecordSession
from .custody_ports import (
    ProfileCustodyPasswordMaterialPort,
    load_profile_custody_password_material,
    map_profile_authentication_proof_failure,
    profile_is_keyring_unavailable,
    refuse_profile_login_without_password_channel,
    unlock_profile_custody_password,
    verify_profile_custody_dek_against_sentinel,
)
from .language_resolver import refresh_active_profile_output_language
from .login_session_port import (
    ProfileBucketSessionPort,
    ProfileLoginSessionPort,
    ProfileSignInGenerationPort,
    profile_login_session_port,
)
from .profile_pointer import (
    ActiveProfilePointerTransactionError,
    active_profile_pointer_transaction,
)
from .profile_record_repository import (
    activate_profile_record_session,
    bind_active_profile_record_session,
    close_active_profile_record_session,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from ..workflow.profile_bucket_models import ProfileBucketPointer
    from .access_contracts import ProfileAccessBinding

_log = get_logger(__name__)


def _profile_login_sessions() -> ProfileLoginSessionPort:
    """Resolve the login-session aggregate composed for this host context."""
    return profile_login_session_port()


def _refuse_login_candidate(reason: str) -> NoReturn:
    """Fail closed when a candidate differs from the requested profile identity."""
    raise ActiveProfilePointerTransactionError(
        translated_message="errors.integrity.integrity_storage_profile_custody_record",
        context={"owner": "profile-login-candidate", "reason": reason},
    )


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


class ProfileCustodySessionOwnerEffect(StrEnum):
    """Verified outcome of one local custody session-owner operation."""

    REVOKED = "revoked"
    REMOVED = "removed"
    VERIFIED_ABSENT = "verified_absent"


class ProfileLoginOutcome(BaseModel):
    """Typed result of one ``login`` invocation.

    Carries no key material: the unlocked
    :class:`~cadrumo.adapters.persistence.storage.master_key.bucket_session.BucketSession`
    is bound to the process through the active-session context variable,
    never to this record.

    Attributes:
        bucket_id: Immutable UUID identity of the authenticated profile.
        label: Operator-facing display label of that profile.
        authenticated_at: UTC instant the session was established. On an
            idempotent no-op this is the ORIGINAL login instant, never
            re-stamped.
        idle_deadline: Current sliding idle deadline.
        absolute_deadline: Immutable absolute session cap.
        session_persisted: ``False`` when the host has no usable OS
            keychain, or the login ran in-process with no runtime-observed
            OS login to bind, so the session is process-scoped only.
        already_authenticated: ``True`` when a still-valid persisted
            session was resumed as a no-op (no re-prompt, no new record).
        closed_previous_bucket_id: Retained result field, always ``None`` for
            the supported candidate and invocation authentication doors. These
            doors do not retire another profile's shared runtime sign-in.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    label: str
    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    session_persisted: bool
    already_authenticated: bool
    closed_previous_bucket_id: BucketId | None = None


@dataclass(slots=True)
class _CandidateProfileLogin:
    """Unbound B material owned by one login transaction until promotion."""

    bucket_id: str
    session: ProfileBucketSessionPort
    record_session: ProfileRecordSession
    material: ProfileCustodyPasswordMaterialPort
    windows: tuple[int, int]
    closed: bool = False
    receipt_persisted: bool | None = None

    def close(self) -> None:
        """Destroy an unpromoted candidate without touching active A."""
        if self.closed:
            return
        self.closed = True
        self.record_session.close()
        self.session.close()


@dataclass(frozen=True, slots=True)
class ProfileLoginCandidate:
    """Borrowed password-proven material, never a frontend result or durable receipt.

    A trusted profile worker may copy the session's key into its exact custody
    after its session authority admits the accompanying outcome. The enclosing
    authentication context always destroys this candidate on exit.
    """

    outcome: ProfileLoginOutcome
    session: ProfileBucketSessionPort = field(repr=False)
    _publish_receipt: Callable[[str, ProfileAccessBinding, ProfileSignInGenerationPort], bool] | None = field(
        default=None, repr=False, compare=False
    )

    @property
    def mints_receipt(self) -> bool:
        """Whether publication mints a new receipt; a resumed receipt keeps its record."""
        return self._publish_receipt is not None

    def persist_acceleration_receipt(
        self, *, login_id: str, binding: ProfileAccessBinding, sign_in: ProfileSignInGenerationPort
    ) -> bool:
        """Publish bounded human acceleration from this still-live password proof.

        The receipt binds ``login_id``, the admitted session's originating OS
        login, and ``sign_in``: the generation of ``binding``'s custody that
        the runtime captured when it published that session. Return ``False``,
        with nothing written, when that generation is no longer current or no
        keychain can custody the key. Receipt candidates retain their original
        record without minting another. Publication never selects a profile or
        installs ambient custody.
        """
        _require_live_receipt_candidate(self.session)
        if self._publish_receipt is None:
            return self.outcome.session_persisted
        return self._publish_receipt(login_id, binding, sign_in)


class ProfileHumanLoginReceipt(BaseModel):
    """Nonsecret acknowledgement of human proof and optional bounded acceleration."""

    model_config = _STRICT_FROZEN

    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime
    session_persisted: bool
    resumed: bool


class ProfileReceiptRefusedError(CadrumoError):
    """A human receipt did not prove the exact current capsule and deadline."""

    def __init__(self, reason: ProfileSessionRefusalReason, *, binding: ReceiptBindingRefusal | None = None) -> None:
        """Preserve the core refusal without exposing receipt material."""
        self.reason = reason
        self.binding = binding
        super().__init__(reason.value)


def _bucket_session_windows() -> tuple[int, int]:
    """Return the bounded session windows for current capsules.

    Current capsules deliberately have no plaintext manifest.  Session
    lifetimes are therefore resolved only from the configured current defaults,
    not through the removed manifest/provider route.
    """
    settings = load_settings()
    return (
        settings.cadrumo_bucket_default_idle_lock_minutes,
        settings.cadrumo_bucket_default_session_absolute_minutes,
    )


def _revoke_profile_session_artefacts(*, storage_root: Path, bucket_id: str) -> None:
    """Delete receipt bytes and keychain material for journalled custody removal.

    The custody transaction fences the durable human generation first. This
    physical cleanup does not own admission, minting or ordinary sign-out.
    The caller separately closes local secrets and verifies receipt absence.
    """
    _profile_login_sessions().delete_acceleration_receipt(storage_root=storage_root, profile_id=UUID(bucket_id))


def close_profile_session_artefacts(*, storage_root: Path, bucket_id: str) -> None:
    """Close process record custody without mutating the runtime's shared receipt."""
    close_active_profile_record_session()


def revoke_live_profile_secret_for_custody_delete(*, bucket_id: str) -> ProfileCustodySessionOwnerEffect:
    """Zeroise this process's live DEK only when it serves ``bucket_id``.

    This is deliberately narrower than logout: a custody deletion must never
    tear down an unrelated profile's active session.  The active-session
    owner performs both the identity query and the zeroisation; callers only
    receive a durable, non-secret outcome they can receipt.
    """
    session = _profile_login_sessions().current_session()
    if not _profile_login_sessions().session_serves_bucket(session, bucket_id):
        return ProfileCustodySessionOwnerEffect.VERIFIED_ABSENT
    _profile_login_sessions().close_active_session()
    if _profile_login_sessions().session_serves_bucket(_profile_login_sessions().current_session(), bucket_id):
        raise UserProfileError(
            translated_message="errors.integrity.integrity_storage_profile_custody_record",
            context={"bucket_id": bucket_id, "owner": "process-secret-revocation"},
        )
    return ProfileCustodySessionOwnerEffect.REVOKED


def remove_profile_session_acceleration_for_custody_delete(
    *,
    storage_root: Path,
    bucket_id: str,
) -> ProfileCustodySessionOwnerEffect:
    """Remove the actual persisted session acceleration and verify its absence.

    Deletion also retires the profile's failed-attempt backoff, which a mere
    revocation deliberately keeps: it lives outside the capsule, so leaving it
    would charge a later profile reusing the identity for attempts against one
    that no longer exists.
    """
    path = _profile_login_sessions().acceleration_receipt_path(storage_root=storage_root, profile_id=UUID(bucket_id))
    was_present = os.path.lexists(path)
    close_profile_session_artefacts(storage_root=storage_root, bucket_id=bucket_id)
    _revoke_profile_session_artefacts(storage_root=storage_root, bucket_id=bucket_id)
    _profile_login_sessions().reset_throttle(storage_root=storage_root, bucket_id=bucket_id)
    if os.path.lexists(path):
        raise UserProfileError(
            translated_message="errors.integrity.integrity_storage_profile_custody_record",
            context={"bucket_id": bucket_id, "owner": "local-session-acceleration"},
        )
    return ProfileCustodySessionOwnerEffect.REMOVED if was_present else ProfileCustodySessionOwnerEffect.VERIFIED_ABSENT


def publish_created_profile_session(
    *,
    bucket_id: str,
    dek: bytes,
    now: datetime | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> None:
    """Publish a newly created profile's session exactly as a login would.

    Registration already proves the operator's credential -- it CHOSE the
    passphrase and the create span unlocked the bucket with it -- so requiring
    that same passphrase again before the new profile can be used is asking a
    question already answered. The session was simply never published: the
    create span held its DEK locally and dropped it, so every surface that
    asked afterwards was correctly told nobody was logged in.

    This is deliberately the same publication login performs, and not a
    second, weaker one: one live bucket session bound process-wide, and the
    record authority derived beside it from the capsule's COMMITTED envelope
    rather than from the in-memory one, so a fact read after registration
    proves the same two things it proves after a login.

    No acceleration receipt is minted. A receipt is what carries a session
    into the NEXT process, which is a separate decision about how long a
    credential should last, and creating a profile does not settle it. The
    operator's next process therefore authenticates normally.

    Args:
        bucket_id: The newly created profile's UUID.
        dek: The unlocked data-encryption key the create span established.
            Copied into the session's own buffer; the caller keeps ownership
            of the bytes it passed.
        now: UTC evaluation instant; the canonical clock when omitted.
        profile_decode_context: Decode context of the pinned authority
            operation the registration ran under.
    """
    instant = _now() if now is None else now
    storage_root = effective_storage_root()
    idle_minutes, absolute_minutes = _bucket_session_windows()
    absolute_deadline = instant + timedelta(minutes=absolute_minutes)
    dek_buffer = bytearray(dek)
    try:
        session = _profile_login_sessions().open_resumed_session(
            bucket_id=bucket_id,
            dek=bytes(dek_buffer),
            idle_minutes=idle_minutes,
            opened_at=instant,
            idle_deadline=min(instant + timedelta(minutes=idle_minutes), absolute_deadline),
            absolute_deadline=absolute_deadline,
            storage_root=storage_root,
        )
    finally:
        _profile_login_sessions().zeroise_owned_buffer(dek_buffer)
    # Selection changes only this process's custody. Seal the displaced local
    # key without changing its runtime-owned receipt.
    previous = _profile_login_sessions().current_session()
    if previous is not None and previous.bucket_id != bucket_id:
        previous.close()
    try:
        _profile_login_sessions().bind_session(session)
        _activate_record_authority(
            bucket_id=bucket_id,
            dek=session.dek,
            storage_root=storage_root,
            profile_decode_context=profile_decode_context,
        )
    except BaseException:
        session.close()
        raise
    refresh_active_profile_output_language()


def _activate_record_authority(
    *,
    bucket_id: str,
    dek: bytes,
    storage_root: Path,
    profile_decode_context: ProfileDecodeContext,
) -> None:
    """Bind the record codec to the same live custody session as the bucket.

    A profile record is authenticated with envelope-bound AAD, not merely with
    a bucket UUID.  Loading the committed envelope after the custody session
    has opened therefore makes every fact consumer prove both the session and
    the exact capsule it reads.
    """
    material = load_profile_custody_password_material(UUID(bucket_id), root=storage_root)
    activate_profile_record_session(
        ProfileRecordSession.from_envelope(
            envelope=material.envelope,
            dek=dek,
            profile_decode_context=profile_decode_context,
        )
    )


def resolve_login_target(name: str) -> ProfileBucketPointer:
    """Resolve a ``login NAME`` target from an unambiguous UUID or exact label.

    Delegates to the workflow's one live-profile resolver. That authority
    accepts the immutable bucket UUID or the exact operator label (including
    a sandbox's canonical ``sandbox:<name>`` label) and excludes tombstoned
    buckets for both forms. A bare sandbox short name carries no
    ``sandbox:`` prefix, so it remains an unknown profile rather than being
    implicitly namespaced.

    Public because the login SCREEN must resolve the same named target to
    preselect its row, and must refuse an unknown one identically. Left
    private, that arm would have had to re-derive the resolution — and a
    second derivation is a second refusal wording and a second answer to
    "is a bare sandbox name a profile?", for one question that has one
    answer.
    """
    from ..workflow.profile_bucket_scan import resolve_profile_bucket

    trimmed = name.strip()
    if not trimmed:
        raise ProfileNotFoundError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": name},
        )
    pointer = resolve_profile_bucket(trimmed)
    if pointer is None:
        raise ProfileNotFoundError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": trimmed},
        )
    return pointer


@contextmanager
def authenticate_profile_candidate(
    *,
    bucket_id: UUID,
    passphrase_callback: Callable[[], str],
    profile_decode_context: ProfileDecodeContext,
    now: datetime | None = None,
) -> Generator[ProfileLoginCandidate]:
    """Prove an exact profile without replacing another connection's live custody.

    Reuse login throttling, envelope/sentinel proof and configured human windows.
    No active pointer, process binding, acceleration receipt or human session is
    published here. Only the runtime authority can promote the borrowed result.
    """
    instant = _now() if now is None else now
    storage_root = effective_storage_root()
    target = resolve_login_target(str(bucket_id))
    if target.bucket_id != str(bucket_id):
        _refuse_login_candidate("candidate target differs from the requested profile")
    evaluation = _profile_login_sessions().evaluate_throttle(
        storage_root=storage_root,
        bucket_id=target.bucket_id,
        now=instant,
    )
    if evaluation.throttled:
        raise ProfileLoginThrottledError(remaining_seconds=evaluation.remaining_seconds)
    candidate = _authenticate_candidate_or_record_failure(
        bucket_id=target.bucket_id,
        storage_root=storage_root,
        now=instant,
        passphrase_callback=passphrase_callback,
        profile_decode_context=profile_decode_context,
    )
    try:
        _profile_login_sessions().reset_throttle(storage_root=storage_root, bucket_id=target.bucket_id)
        yield ProfileLoginCandidate(
            outcome=ProfileLoginOutcome(
                bucket_id=target.bucket_id,
                label=target.label,
                authenticated_at=candidate.session.opened_at,
                idle_deadline=candidate.session.idle_deadline,
                absolute_deadline=candidate.session.absolute_deadline,
                session_persisted=False,
                already_authenticated=False,
                closed_previous_bucket_id=None,
            ),
            session=candidate.session,
            _publish_receipt=lambda login_id, binding, sign_in: _persist_candidate_receipt(
                candidate, storage_root=storage_root, login_id=login_id, binding=binding, sign_in=sign_in
            ),
        )
    finally:
        candidate.close()


def _require_live_receipt_candidate(session: ProfileBucketSessionPort) -> None:
    """Refuse retired or expired proof, including time spent acquiring custody."""
    instant = _now()
    if session.sealed or instant < session.opened_at:
        raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.CUSTODY_CHANGED)
    if instant >= session.absolute_deadline:
        raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.EXPIRED_ABSOLUTE)
    if instant >= session.idle_deadline:
        raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.EXPIRED_IDLE)


def _persist_candidate_receipt(
    candidate: _CandidateProfileLogin,
    *,
    storage_root: Path,
    login_id: str,
    binding: ProfileAccessBinding,
    sign_in: ProfileSignInGenerationPort,
) -> bool:
    """Recheck the proven capsule while holding its canonical publication lock."""
    with active_profile_pointer_transaction(storage_root):
        if candidate.closed or candidate.session.sealed:
            raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.CUSTODY_CHANGED)
        _require_live_receipt_candidate(candidate.session)
        pinned = candidate.material
        current = load_profile_custody_password_material(UUID(candidate.bucket_id), root=storage_root)
        if (
            current.envelope.canonical_json_bytes() != pinned.envelope.canonical_json_bytes()
            or current.sentinel.canonical_json_bytes() != pinned.sentinel.canonical_json_bytes()
            or current.commit.transaction_id != pinned.commit.transaction_id
        ):
            raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.CUSTODY_CHANGED)
        if candidate.receipt_persisted is None:
            candidate.receipt_persisted = _mint_or_warn(
                storage_root=storage_root,
                material=pinned,
                session=candidate.session,
                windows=candidate.windows,
                login_id=login_id,
                binding=binding,
                sign_in=sign_in,
            )
        return candidate.receipt_persisted


@contextmanager
def borrow_profile_receipt_key(*, bucket_id: UUID) -> Generator[bytearray]:
    """Borrow only the keychain-held proof that the receipt locator names.

    This is a frontend's whole share of a sign-in: it reads no custody
    envelope, never unwraps or decrypts the receipt, and never deletes either
    half. The runtime verifies the proof, and deletes a refused receipt. The
    proof is a secret capability for a protected IPC frame, never a public
    result. Its buffer is wiped even when the caller's exchange fails.
    """
    outcome, key = _profile_login_sessions().borrow_acceleration_receipt_key(
        storage_root=effective_storage_root(), profile_id=bucket_id
    )
    if not outcome.resumed or key is None:
        if key is not None:
            _profile_login_sessions().zeroise_owned_buffer(key)
        raise ProfileReceiptRefusedError(outcome.refusal or ProfileSessionRefusalReason.ABSENT, binding=outcome.binding)
    try:
        yield key
    finally:
        _profile_login_sessions().zeroise_owned_buffer(key)


@contextmanager
def resume_profile_candidate(
    *,
    bucket_id: UUID,
    receipt_key: bytearray,
    profile_decode_context: ProfileDecodeContext,
    login_id: str,
    sign_in_binding: ProfileAccessBinding,
    now: datetime | None = None,
) -> Generator[ProfileLoginCandidate]:
    """Prove a supplied human receipt without binding or selecting a profile.

    The runtime composes this with ``login_id``, the originating OS login of
    the connection presenting the proof, and ``sign_in_binding``, its worker's
    custody binding. The receipt must name that login and the current sign-in
    generation; a receipt refused for its binding or its own metadata is
    deleted by the reader, never by the presenting frontend. A valid proof
    inherits the receipt's original deadlines. It never reads the OS keyring
    for a key, renews human life, or changes the active frontend context.
    """
    instant = _now() if now is None else now
    storage_root = effective_storage_root()
    material = load_profile_custody_password_material(bucket_id, root=storage_root)
    outcome, dek = _profile_login_sessions().resume_acceleration_receipt_with_key(
        storage_root=storage_root,
        profile_id=bucket_id,
        custody_generation=material.envelope.password_generation,
        dek_epoch=material.envelope.dek_epoch,
        now=instant,
        receipt_key=receipt_key,
        login_id=login_id,
        sign_in_binding=sign_in_binding,
    )
    if not outcome.resumed or outcome.record is None or dek is None:
        if dek is not None:
            _profile_login_sessions().zeroise_owned_buffer(dek)
        raise ProfileReceiptRefusedError(outcome.refusal or ProfileSessionRefusalReason.ABSENT, binding=outcome.binding)
    record = outcome.record
    with ExitStack() as cleanup:
        cleanup.callback(_profile_login_sessions().zeroise_owned_buffer, dek)
        try:
            verify_profile_custody_dek_against_sentinel(
                dek=bytes(dek),
                profile_id=bucket_id,
                dek_epoch=material.envelope.dek_epoch,
                sentinel=material.sentinel,
            )
        except CadrumoError as error:
            raise ProfileReceiptRefusedError(ProfileSessionRefusalReason.TAMPERED) from error
        idle_minutes, _ = _bucket_session_windows()
        session = _profile_login_sessions().open_resumed_session(
            bucket_id=str(bucket_id),
            dek=bytes(dek),
            idle_minutes=idle_minutes,
            opened_at=record.issued_at,
            idle_deadline=record.idle_deadline,
            absolute_deadline=record.absolute_deadline,
            storage_root=storage_root,
        )
        cleanup.callback(session.close)
        # Match password candidates' local record authority construction;
        # actual record reads retain their own later authenticated boundary.
        record_session = ProfileRecordSession.from_envelope(
            envelope=material.envelope,
            dek=bytes(dek),
            profile_decode_context=profile_decode_context,
        )
        record_session.close()
        target = resolve_login_target(str(bucket_id))
        yield ProfileLoginCandidate(
            outcome=ProfileLoginOutcome(
                bucket_id=str(bucket_id),
                label=target.label,
                authenticated_at=record.issued_at,
                idle_deadline=record.idle_deadline,
                absolute_deadline=record.absolute_deadline,
                session_persisted=True,
                already_authenticated=True,
                closed_previous_bucket_id=None,
            ),
            session=session,
        )


def authenticate_profile_for_invocation(
    *,
    name: str,
    now: datetime | None = None,
    passphrase_callback: Callable[[], str] | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileLoginOutcome:
    """Authenticate explicit credentials and bind one profile for this process.

    Selection and shared human sign-in remain owned by their separate runtime
    boundaries. This door leaves the pointer and all acceleration receipts intact.
    It closes a displaced local session because this process holds one profile's
    custody at a time. The returned outcome is always process-scoped.
    """
    instant = _now() if now is None else now
    storage_root = effective_storage_root()
    target = resolve_login_target(name)

    evaluation = _profile_login_sessions().evaluate_throttle(
        storage_root=storage_root,
        bucket_id=target.bucket_id,
        now=instant,
    )
    if evaluation.throttled:
        raise ProfileLoginThrottledError(remaining_seconds=evaluation.remaining_seconds)

    candidate = _authenticate_candidate_or_record_failure(
        bucket_id=target.bucket_id,
        storage_root=storage_root,
        now=instant,
        passphrase_callback=passphrase_callback,
        profile_decode_context=profile_decode_context,
    )
    try:
        _profile_login_sessions().reset_throttle(storage_root=storage_root, bucket_id=target.bucket_id)
        previous_live = _profile_login_sessions().current_session()
        if previous_live is not None and previous_live.bucket_id != candidate.bucket_id:
            previous_live.close()
        _profile_login_sessions().bind_session(candidate.session)
        bind_active_profile_record_session(candidate.record_session)
    except BaseException:
        candidate.close()
        raise
    refresh_active_profile_output_language()
    return ProfileLoginOutcome(
        bucket_id=candidate.bucket_id,
        label=target.label,
        authenticated_at=candidate.session.opened_at,
        idle_deadline=candidate.session.idle_deadline,
        absolute_deadline=candidate.session.absolute_deadline,
        session_persisted=False,
        already_authenticated=False,
        closed_previous_bucket_id=None,
    )


def _resolve_login_password(callback: Callable[[], str] | None) -> str:
    """Return the one explicitly supplied password channel for current custody."""
    if callback is not None:
        return callback()
    configured = load_settings().cadrumo_secret_passphrase
    if configured is None:
        refuse_profile_login_without_password_channel()
    return configured.get_secret_value()


def _authenticate_candidate_or_record_failure(
    *,
    bucket_id: str,
    storage_root: Path,
    now: datetime,
    passphrase_callback: Callable[[], str] | None,
    profile_decode_context: ProfileDecodeContext,
) -> _CandidateProfileLogin:
    """Authenticate B into unbound candidate memory and nothing else."""
    material = load_profile_custody_password_material(UUID(bucket_id), root=storage_root)
    password = _resolve_login_password(passphrase_callback)
    try:
        unlocked = unlock_profile_custody_password(material, password=password)
    except BaseException as exc:
        refusal = map_profile_authentication_proof_failure(exc, operation=ProfilePasswordProofOperation.LOGIN)
        if refusal is not None:
            _profile_login_sessions().record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)
            raise refusal from exc
        raise

    dek_buffer = bytearray(unlocked.dek)
    try:
        idle_minutes, absolute_minutes = _bucket_session_windows()
        absolute_deadline = now + timedelta(minutes=absolute_minutes)
        session = _profile_login_sessions().open_resumed_session(
            bucket_id=bucket_id,
            dek=bytes(dek_buffer),
            idle_minutes=idle_minutes,
            opened_at=now,
            idle_deadline=min(now + timedelta(minutes=idle_minutes), absolute_deadline),
            absolute_deadline=absolute_deadline,
            storage_root=storage_root,
        )
        try:
            record_session = ProfileRecordSession.from_envelope(
                envelope=material.envelope,
                dek=bytes(dek_buffer),
                profile_decode_context=profile_decode_context,
            )
        except BaseException:
            session.close()
            raise
    finally:
        _profile_login_sessions().zeroise_owned_buffer(dek_buffer)
    return _CandidateProfileLogin(
        bucket_id=bucket_id,
        session=session,
        record_session=record_session,
        material=material,
        windows=(idle_minutes, absolute_minutes),
    )


def _mint_or_warn(
    *,
    storage_root: Path,
    material: ProfileCustodyPasswordMaterialPort,
    session: ProfileBucketSessionPort,
    windows: tuple[int, int],
    login_id: str,
    binding: ProfileAccessBinding,
    sign_in: ProfileSignInGenerationPort,
) -> bool:
    """Mint the persisted session, or report a process-scoped login.

    A host with no usable OS keychain has nowhere secure to custody the
    session key, so no persisted artefact is written at all — failing
    closed beats writing key material to disk. The login still succeeds
    for this process; the caller surfaces the warning. A sign-in generation
    that moved after its capture likewise leaves no receipt.
    """
    try:
        idle_minutes, absolute_minutes = windows
        minted = _profile_login_sessions().mint_acceleration_receipt(
            storage_root=storage_root,
            profile_id=material.envelope.profile_id,
            custody_generation=material.envelope.password_generation,
            dek_epoch=material.envelope.dek_epoch,
            dek=session.dek,
            now=session.opened_at,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
            login_id=login_id,
            sign_in_binding=binding,
            sign_in_generation=sign_in,
        )
    except BaseException as exc:
        if not profile_is_keyring_unavailable(exc):
            raise
        _log.info(
            "profile session not persisted (no usable OS keychain); login is process-scoped profile_id=%s",
            material.envelope.profile_id,
        )
        return False
    if minted is None:
        _log.info(
            "profile session not persisted (sign-in generation changed since publication) profile_id=%s",
            material.envelope.profile_id,
        )
        return False
    return True


__all__ = [
    "ProfileCustodySessionOwnerEffect",
    "ProfileHumanLoginReceipt",
    "ProfileLoginCandidate",
    "ProfileLoginOutcome",
    "ProfileLoginThrottledError",
    "ProfileReceiptRefusedError",
    "authenticate_profile_candidate",
    "authenticate_profile_for_invocation",
    "borrow_profile_receipt_key",
    "close_profile_session_artefacts",
    "publish_created_profile_session",
    "remove_profile_session_acceleration_for_custody_delete",
    "resume_profile_candidate",
    "revoke_live_profile_secret_for_custody_delete",
]
