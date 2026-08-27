"""Transactional profile login over current password custody.

``aeat config login`` resolves a committed capsule, evaluates its throttle,
and authenticates that exact envelope-and-sentinel pair into an unbound
candidate DEK session. It never consults a provider, a shared master key, or
recovery material. Until candidate authentication, pointer compare-and-swap,
and local binding have all succeeded, the active profile remains untouched.

Three distinct artefacts meet in this module, and reading any of them as
another has twice produced a wrong conclusion about what the code does. They
belong to different custody classes with different key requirements:

- the **acceleration receipt** -- keyring key plus a keystore sidecar record,
  OUTSIDE the encrypted store, wrapping an already-unlocked DEK. Revocable
  with no unlocked profile, which is why retirement can complete during
  recovery. Not a session: no counterparty, no protocol.
- the **live bucket session** -- the in-process
  :class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`
  holding the unlocked DEK. Purely process-local, so it is absent in an
  ordinary invocation, every one of which is a fresh process.
- the **AEAT authority session** -- an encrypted row INSIDE the bucket,
  revocable only with the key. Owned by the auth package; named here only to
  keep it distinct.

Unqualified "session" in this module means the live bucket session and
nothing else.

The optional acceleration receipt is exactly that: acceleration. Its absence
or failure leaves a valid live bucket session; it never changes the outcome
of password authentication. A prior profile is retired only after B is
durably selected and locally bound.

:func:`bind_resumed_profile_session` is the read-side counterpart and the
SINGLE resume authority: the login no-op path, the CLI root callback and
the named-profile read path all call it, so the surfaces cannot drift.

See Also:
    :mod:`cadrumo.adapters.persistence.storage.custody._acceleration_receipt`
        The split-knowledge receipt this module mints and resumes.
    :func:`~cadrumo.application.user_profile.logout_active_profile`
        The symmetric strong close, which reuses
        :func:`close_profile_session_artefacts` from here.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import ProfileSessionRefusalReason, StorageCategory, storage_location
from ...core.bucket_pointer import BucketPointer, resolve_active_bucket_id
from ...core.config import load_settings
from ...core.hashing import (
    bounded_canonical_json_bytes,
    reject_duplicate_json_members,
    reject_json_constant,
)
from ...core.identity import BucketId
from ...core.logging import get_logger
from ...core.paths import effective_storage_root
from ...core.time import now as _now
from ...core.time import validate_utc_aware
from ...domain.user_profile.errors import ProfileNotFoundError, UserProfileError
from .authentication import ProfilePasswordProofOperation
from .capsule_record import ProfileRecordSession
from .custody_ports import (
    ProfileCustodyLocalRecordStore,
    ProfileCustodyPasswordMaterialPort,
    default_profile_bucket_event_history_repository,
    default_profile_custody_local_record_store,
    load_profile_custody_password_material,
    map_profile_authentication_proof_failure,
    profile_is_keyring_unavailable,
    refuse_profile_login_without_password_channel,
    unlock_profile_custody_password,
)
from .login_session_port import (
    ProfileBucketSessionPort,
    ProfileLoginSessionPort,
    ProfilePersistedSessionPort,
    ProfileSessionResumeOutcomePort,
    profile_login_session_port,
)
from .profile_pointer import (
    ActiveProfilePointerTransaction,
    ActiveProfilePointerTransactionError,
    active_profile_pointer_transaction,
)
from .profile_record_repository import (
    activate_profile_record_session,
    bind_active_profile_record_session,
    clear_active_profile_record_session_binding,
    close_active_profile_record_session,
)

if TYPE_CHECKING:
    from ..workflow.profile_bucket_models import ProfileBucketPointer

_log = get_logger(__name__)

_HANDOVER_JOURNAL_FILENAME = "profile-login-handover.v2.json"
_HANDOVER_JOURNAL_MAX_BYTES = 4 * 1024


def _login_sessions() -> ProfileLoginSessionPort:
    """Resolve the login-session aggregate composed for this host context."""
    return profile_login_session_port()


class _HandoverPhase(StrEnum):
    """Durable boundaries of one password-authenticated profile handover."""

    PREPARED = "prepared"
    POINTER_PUBLISHED = "pointer_published"
    B_BOUND = "b_bound"
    ACCELERATED = "accelerated"
    ACTIVATED = "activated"
    A_RETIRED = "a_retired"


_HANDOVER_PREDECESSOR: dict[_HandoverPhase, _HandoverPhase] = {
    _HandoverPhase.POINTER_PUBLISHED: _HandoverPhase.PREPARED,
    _HandoverPhase.B_BOUND: _HandoverPhase.POINTER_PUBLISHED,
    _HandoverPhase.ACCELERATED: _HandoverPhase.B_BOUND,
    _HandoverPhase.ACTIVATED: _HandoverPhase.ACCELERATED,
    _HandoverPhase.A_RETIRED: _HandoverPhase.ACTIVATED,
}
_HANDOVER_PHASE_INDEX: dict[_HandoverPhase, int] = {
    _HandoverPhase.PREPARED: 0,
    _HandoverPhase.POINTER_PUBLISHED: 1,
    _HandoverPhase.B_BOUND: 2,
    _HandoverPhase.ACCELERATED: 3,
    _HandoverPhase.ACTIVATED: 4,
    _HandoverPhase.A_RETIRED: 5,
}


class _ProfileLoginHandoverJournal(BaseModel):
    """Non-secret recovery witness for the short A-to-B handover window."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[2] = 2
    phase: _HandoverPhase
    profile_a: BucketId | None
    profile_b: BucketId
    pointer_before: BucketPointer
    pointer_after: BucketPointer
    activation_at: datetime

    @model_validator(mode="after")
    def _validate_journal(self) -> _ProfileLoginHandoverJournal:
        """Keep recovery time deterministic and safe to replay as an event key."""
        validate_utc_aware(self.activation_at)
        if self.pointer_after.bucket_id != self.profile_b:
            raise ValueError("handover pointer-after selection must name profile B")
        if self.pointer_after != self.pointer_before and (
            self.pointer_after.transition_revision != self.pointer_before.transition_revision + 1
        ):
            raise ValueError("handover pointer transition revision must advance exactly once when selection changes")
        return self

    @classmethod
    def prepare(
        cls,
        *,
        profile_a: str | None,
        profile_b: str,
        pointer_before: BucketPointer,
        pointer_after: BucketPointer,
        activation_at: datetime,
    ) -> _ProfileLoginHandoverJournal:
        """Capture the one non-secret transition before pointer publication."""
        return cls(
            phase=_HandoverPhase.PREPARED,
            profile_a=profile_a,
            profile_b=profile_b,
            pointer_before=pointer_before,
            pointer_after=pointer_after,
            activation_at=activation_at,
        )

    def at_phase(self, phase: _HandoverPhase) -> _ProfileLoginHandoverJournal:
        """Return this exact handover witnessed at its next durable phase."""
        return self.model_copy(update={"phase": phase})

    def at_least_phase(self, phase: _HandoverPhase) -> _ProfileLoginHandoverJournal:
        """Advance a recovery receipt without ever regressing its durable phase."""
        if _HANDOVER_PHASE_INDEX[self.phase] >= _HANDOVER_PHASE_INDEX[phase]:
            return self
        return self.at_phase(phase)

    def canonical_json_bytes(self) -> bytes:
        """Return the journal's one bounded, byte-exact persistence form."""
        return bounded_canonical_json_bytes(
            self.model_dump(mode="json"),
            maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES,
            subject="profile login handover journal",
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
    :class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`
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
            keychain, so the session is process-scoped only.
        already_authenticated: ``True`` when a still-valid persisted
            session was resumed as a no-op (no re-prompt, no new record).
        closed_previous_bucket_id: Bucket whose session this login closed
            during a cross-profile handover, or ``None`` when the login
            re-entered the profile already selected. Populated whether or
            not that profile still had a live session in this process.
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
    closed: bool = False

    def close(self) -> None:
        """Destroy an unpromoted candidate without touching active A."""
        if self.closed:
            return
        self.closed = True
        self.record_session.close()
        self.session.close()


@dataclass(slots=True)
class _HandoverRecovery:
    """What one recovery classification leaves for the login that observed it.

    ``interrupted`` is the witness the login must still replay, and is absent
    whenever recovery settled the handover itself.  ``completed_selection``
    names the profile the last COMPLETED handover selected, which is the only
    durable record of what the pointer named before an out-of-band writer moved
    it -- and is therefore the sole remaining source for the profile this login
    is moving away from once that happened in an earlier process.
    """

    interrupted: _ProfileLoginHandoverJournal | None = None
    completed_selection: str | None = None


@dataclass(slots=True)
class _LoginAttempt:
    """Resolved, lock-scoped inputs shared by one login attempt."""

    target: ProfileBucketPointer
    selected: BucketPointer
    prior_pointer: BucketPointer
    pointer_transaction: ActiveProfilePointerTransaction
    storage_root: Path
    interrupted_handover: _ProfileLoginHandoverJournal | None
    completed_selection: str | None = None


@dataclass(slots=True)
class _HandoverPublication:
    """Durable pointer publication returned before candidate binding."""

    journal: _ProfileLoginHandoverJournal
    published_pointer: BucketPointer


@dataclass(slots=True)
class _CandidatePromotionResult:
    """Candidate state that is safe to retire A against."""

    journal: _ProfileLoginHandoverJournal
    previous_record: ProfileRecordSession | None
    persisted: bool


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


def _handover_journal_path(storage_root: Path) -> Path:
    """Return the one root-local journal for an in-flight profile switch."""
    return (
        storage_root / storage_location(StorageCategory.OPERATION_JOURNAL).relative_path() / _HANDOVER_JOURNAL_FILENAME
    )


def _handover_journal_directory(storage_root: Path) -> Path:
    """Return the one anchored local-record parent for the handover witness."""
    return storage_root / storage_location(StorageCategory.OPERATION_JOURNAL).relative_path()


def _parse_handover_journal(payload: bytes) -> _ProfileLoginHandoverJournal:
    """Decode only the journal's exact bounded canonical JSON form."""
    if len(payload) > _HANDOVER_JOURNAL_MAX_BYTES:
        _refuse_handover_journal("journal exceeds its byte limit")
    try:
        document = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        if not isinstance(document, dict):
            raise ValueError("handover journal must be a JSON object")
        canonical = bounded_canonical_json_bytes(
            cast(dict[str, object], document),
            maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES,
            subject="profile login handover journal",
        )
        journal = _ProfileLoginHandoverJournal.model_validate_json(canonical)
        if journal.canonical_json_bytes() != payload:
            raise ValueError("handover journal bytes are not canonical")
        return journal
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError, TypeError):
        _refuse_handover_journal("journal is malformed or noncanonical")


def _handover_journal_store() -> ProfileCustodyLocalRecordStore:
    """Resolve the one application port for root-local custody records."""
    return default_profile_custody_local_record_store()


def _ensure_handover_journal_directory(*, storage_root: Path, store: ProfileCustodyLocalRecordStore) -> Path:
    """Anchor the journal parent before any local record operation."""
    directory = _handover_journal_directory(storage_root)
    try:
        store.ensure_directory(directory)
    except Exception:
        _refuse_handover_journal("journal directory cannot be anchored")
    return directory


def _refuse_handover_journal(reason: str) -> NoReturn:
    """Fail closed when a durable handover witness cannot be trusted."""
    raise ActiveProfilePointerTransactionError(
        translated_message="errors.integrity.integrity_storage_profile_custody_record",
        context={"owner": "profile-login-handover", "reason": reason},
    )


def _save_handover_journal(*, storage_root: Path, journal: _ProfileLoginHandoverJournal) -> None:
    """Durably publish one complete non-secret handover phase under root lock."""
    try:
        store = _handover_journal_store()
        _ensure_handover_journal_directory(storage_root=storage_root, store=store)
        if journal.phase is _HandoverPhase.PREPARED:
            predecessor = None
        else:
            predecessor = journal.at_phase(_HANDOVER_PREDECESSOR[journal.phase]).canonical_json_bytes()
        path = _handover_journal_path(storage_root)
        current = journal.canonical_json_bytes()
        store.compare_and_replace_same_or_predecessor(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES,
        )
        # The first receipt atomically publishes its target and retains only
        # its exact predecessor as a recoverable cleanup sidecar. Repeating
        # the same canonical receipt has no target write; it removes that
        # verified sidecar or fails closed so a future retry can converge.
        store.compare_and_replace_same_or_predecessor(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES,
        )
    except Exception:
        _refuse_handover_journal("journal compare-and-replace differs from the exact transition")


def _load_handover_journal(*, storage_root: Path) -> _ProfileLoginHandoverJournal | None:
    """Load the sole bounded in-flight witness, refusing malformed replacement."""
    try:
        store = _handover_journal_store()
        _ensure_handover_journal_directory(storage_root=storage_root, store=store)
        payload = store.read_optional(_handover_journal_path(storage_root), maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES)
    except Exception:
        _refuse_handover_journal("journal cannot be anchored and read")
    if payload is None:
        return None
    return _parse_handover_journal(payload)


def _clear_handover_journal(*, storage_root: Path, journal: _ProfileLoginHandoverJournal) -> None:
    """Remove the completed or fully rolled-back witness under root lock."""
    try:
        store = _handover_journal_store()
        _ensure_handover_journal_directory(storage_root=storage_root, store=store)
        current = journal.canonical_json_bytes()
        predecessor = (
            None
            if journal.phase is _HandoverPhase.PREPARED
            else journal.at_phase(_HANDOVER_PREDECESSOR[journal.phase]).canonical_json_bytes()
        )
        path = _handover_journal_path(storage_root)
        # A crash can leave the publication target plus only its exact
        # predecessor sidecar. Re-submit the same receipt first: this is a
        # target no-op that clears that verified sidecar before the terminal
        # compare-and-clear removes the journal itself.
        store.compare_and_replace_same_or_predecessor(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES,
        )
        store.compare_and_clear(
            path,
            expected=current,
            maximum_bytes=_HANDOVER_JOURNAL_MAX_BYTES,
        )
    except Exception:
        _refuse_handover_journal("journal compare-and-clear differs from the exact transition")


def _recover_interrupted_handover(
    *,
    storage_root: Path,
    pointer_transaction: ActiveProfilePointerTransaction,
) -> _HandoverRecovery:
    """Classify an interrupted handover without unlocking or overwriting it.

    A process crash has already destroyed A's in-process handles.  The durable
    pointer therefore decides the next process's profile.  Before B's
    activation event is durable, the caller must re-authenticate B and replay
    the stable journal event; once activation is witnessed, no replay is
    needed and the journal can be removed.

    The terminal receipt is classified by its PHASE alone, before the pointer
    is consulted at all.  A journal reaches ``A_RETIRED`` only after the
    handover has run to its end -- the receipt is written after A's authorities
    are closed and its durable session artefacts revoked -- so there is no such
    thing as an interrupted terminal handover, and the two pointer states it
    witnessed answer no question that is still open.  It is retained past its
    own completion purely so ONE later login observes the boundary, and in that
    interval the pointer legitimately moves for reasons the handover never
    witnessed: registering a profile compare-and-swaps the pointer onto the new
    capsule inside the create transaction, so an ordinary
    register-login-register-login sequence leaves the retained receipt matching
    neither of its own states.  Judging a finished handover against a pointer
    that has since moved on reported a live interruption where none existed and
    refused every subsequent login.

    Every pre-terminal phase still carries real outstanding work, so it is
    still judged against the pointer and still fails closed when that pointer
    is unrecognisable.
    """
    journal = _load_handover_journal(storage_root=storage_root)
    if journal is None:
        return _HandoverRecovery()
    if journal.phase is _HandoverPhase.A_RETIRED:
        _complete_witnessed_retirement(storage_root=storage_root, journal=journal)
        _clear_handover_journal(storage_root=storage_root, journal=journal)
        return _HandoverRecovery(completed_selection=journal.profile_b)
    current = pointer_transaction.read()
    before = journal.pointer_before
    after = journal.pointer_after
    if current == before:
        # The pointer stands where it did before this handover, so nothing it
        # selected survived and the profile it moved away from is still the
        # selected one.  There is no completed selection to carry.
        _clear_handover_journal(storage_root=storage_root, journal=journal)
        return _HandoverRecovery()
    if current != after:
        _refuse_handover_journal("pointer no longer matches either witnessed handover state")
    if journal.phase is _HandoverPhase.ACTIVATED:
        _complete_witnessed_retirement(storage_root=storage_root, journal=journal)
        _clear_handover_journal(storage_root=storage_root, journal=journal)
        return _HandoverRecovery(completed_selection=journal.profile_b)
    return _HandoverRecovery(interrupted=journal)


def _complete_witnessed_retirement(*, storage_root: Path, journal: _ProfileLoginHandoverJournal) -> None:
    """Retire the profile a witnessed-complete handover may not have finished.

    A handover that reached activation already serves the operator, so recovery
    classifies it as needing no replay and the next login can resume B as a
    no-op. Retiring A on disk is then the one step that may still be
    outstanding, and stranding it leaves A's acceleration receipt resumable
    without A's passphrase. It is a durable delete needing neither
    authentication nor key material, so it is finished here rather than left to
    a replay path a complete handover never takes.

    Idempotent, and it deliberately routes through the same single revocation
    authority the handover itself uses, so recovery finishes exactly what that
    handover would have done and nothing more.
    """
    retired = journal.profile_a
    if retired is None or retired == journal.profile_b:
        return
    _revoke_profile_session_artefacts(storage_root=storage_root, bucket_id=retired)


def _revoke_profile_session_artefacts(*, storage_root: Path, bucket_id: str) -> None:
    """Revoke the durable session artefacts owned by ``bucket_id`` (idempotent).

    The single authority for "this profile's stored session is void": deletes
    the on-disk session record AND its OS-keychain session key (split
    knowledge, so either alone is already useless) and clears the failed-login
    backoff.

    Deliberately owns no process-local state. A caller that already holds the
    exact session objects it must close -- the cross-profile handover, which
    closes A's two authorities by identity while B is the live one -- needs the
    durable revocation without a process teardown that would reach the wrong
    profile. Splitting it here keeps that revocation a single implementation
    rather than a second copy at the handover.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the profile whose stored session to revoke.
    """
    _login_sessions().delete_acceleration_receipt(storage_root=storage_root, profile_id=UUID(bucket_id))
    _login_sessions().reset_throttle(storage_root=storage_root, bucket_id=bucket_id)


def close_profile_session_artefacts(*, storage_root: Path, bucket_id: str) -> None:
    """Tear down every session artefact owned by ``bucket_id`` (idempotent).

    The single authority for "this profile is no longer logged in": clears the
    process-local record authority, then revokes the durable artefacts through
    :func:`_revoke_profile_session_artefacts`. Composed by the strong close in
    :func:`~cadrumo.application.user_profile.logout_active_profile`, so neither
    surface owns a second teardown path.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the profile whose session to tear down.
    """
    close_active_profile_record_session()
    _revoke_profile_session_artefacts(storage_root=storage_root, bucket_id=bucket_id)


def _distinct_bucket_ids(*bucket_ids: str | None) -> tuple[str, ...]:
    """Return the supplied identities once each, in order, dropping absent ones.

    Every profile identity a command-line process can observe is partial on its
    own: the live in-process session is absent in a fresh process, and the
    durable pointer is already moved on mid-handover. Both revocation owners --
    logout and the login handover -- therefore act on the UNION of their
    observations rather than on one of them, and share this one folding so the
    two cannot drift.
    """
    return tuple(dict.fromkeys(value for value in bucket_ids if value is not None))


def has_live_profile_session() -> bool:
    """Report whether this process currently holds an open profile session.

    A durable active pointer is NOT the same fact: a registered profile keeps
    its selection across a logout, so the pointer can name a profile whose
    session is closed. A caller that needs profile-bound encrypted storage --
    anything that reads or writes through the secure object store -- must ask
    this rather than reading the pointer, because only an open session carries
    the key that store needs.
    """
    return _login_sessions().current_session() is not None


def logout_active_profile() -> str | None:
    """Strong-close the selected profile without any provider fallback.

    Logout is the explicit session-revocation owner: it clears the live DEK
    binding, its current record binding, the UUID-paired acceleration receipt,
    and the durable active pointer while the canonical root lock is held.
    It returns the authenticated profile UUID when there was a session or
    selection to revoke, otherwise ``None`` for an idempotent logged-out call.
    """
    storage_root = effective_storage_root()
    live = _login_sessions().current_session()
    live_bucket_id = live.bucket_id if live is not None else None
    with active_profile_pointer_transaction(storage_root) as pointer_transaction:
        selected = pointer_transaction.read()
        selected_bucket_id = selected.bucket_id
        target_ids = _distinct_bucket_ids(live_bucket_id, selected_bucket_id)
        if not target_ids:
            return None
        _login_sessions().close_active_session()
        for bucket_id in target_ids:
            close_profile_session_artefacts(storage_root=storage_root, bucket_id=bucket_id)
        pointer_transaction.clear()
    return live_bucket_id or selected_bucket_id


def revoke_live_profile_secret_for_custody_delete(*, bucket_id: str) -> ProfileCustodySessionOwnerEffect:
    """Zeroise this process's live DEK only when it serves ``bucket_id``.

    This is deliberately narrower than logout: a custody deletion must never
    tear down an unrelated profile's active session.  The active-session
    owner performs both the identity query and the zeroisation; callers only
    receive a durable, non-secret outcome they can receipt.
    """
    session = _login_sessions().current_session()
    if not _login_sessions().session_serves_bucket(session, bucket_id):
        return ProfileCustodySessionOwnerEffect.VERIFIED_ABSENT
    _login_sessions().close_active_session()
    if _login_sessions().session_serves_bucket(_login_sessions().current_session(), bucket_id):
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
    """Remove the actual persisted session acceleration and verify its absence."""
    path = _login_sessions().acceleration_receipt_path(storage_root=storage_root, profile_id=UUID(bucket_id))
    was_present = os.path.lexists(path)
    close_profile_session_artefacts(storage_root=storage_root, bucket_id=bucket_id)
    if os.path.lexists(path):
        raise UserProfileError(
            translated_message="errors.integrity.integrity_storage_profile_custody_record",
            context={"bucket_id": bucket_id, "owner": "local-session-acceleration"},
        )
    return ProfileCustodySessionOwnerEffect.REMOVED if was_present else ProfileCustodySessionOwnerEffect.VERIFIED_ABSENT


def bind_resumed_profile_session(
    *,
    bucket_id: str,
    now: datetime | None = None,
) -> ProfileSessionRefusalReason | None:
    """Resume ``bucket_id``'s persisted session and bind it to this process.

    The SINGLE resume authority, shared by the login idempotence guard, the
    CLI root callback, and the named-profile read path so they cannot drift.
    Fail-closed throughout: the adapter deletes stale artefacts and reports a
    typed refusal, and this function opens NOTHING on any refusal branch.

    ``bucket_id`` is an explicit target, NOT the active profile. The name once
    said "active", which was false of the parameter and cost a real defect:
    the named-profile read path concluded this authority could not serve a
    target it had resolved itself, skipped the resume, and reported records it
    could not open as missing. Binding is what distinguishes this from the
    substrate's own ``resume_profile_session``, which returns material and
    binds nothing.

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
    storage_root = effective_storage_root()
    outcome, dek = _resume_acceleration_receipt(
        storage_root=storage_root,
        bucket_id=bucket_id,
        now=instant,
    )
    if not outcome.resumed or outcome.record is None or dek is None:
        return outcome.refusal if outcome.refusal is not None else ProfileSessionRefusalReason.ABSENT

    record = outcome.record
    # Wipe the buffer the resume actually returned, not a copy of it. Copying
    # first and zeroising the copy leaves the original resident and beyond any
    # later reach, which is the defect this key's wipeability exists to remove.
    # The session takes and owns its own copy.
    try:
        idle_minutes, _ = _bucket_session_windows()
        session = _login_sessions().open_resumed_session(
            bucket_id=bucket_id,
            dek=bytes(dek),
            idle_minutes=idle_minutes,
            opened_at=record.issued_at,
            idle_deadline=record.idle_deadline,
            absolute_deadline=record.absolute_deadline,
            storage_root=storage_root,
        )
    finally:
        _login_sessions().zeroise_owned_buffer(dek)

    session.touch(instant)
    _login_sessions().bind_session(session)
    _activate_record_authority(bucket_id=bucket_id, dek=session.dek, storage_root=storage_root)
    _persist_advanced_idle_deadline(
        storage_root=storage_root,
        profile_id=record.profile_id,
        record=record,
        new_idle_deadline=session.idle_deadline,
    )
    return None


def _activate_record_authority(*, bucket_id: str, dek: bytes, storage_root: Path) -> None:
    """Bind the record codec to the same live custody session as the bucket.

    A profile record is authenticated with envelope-bound AAD, not merely with
    a bucket UUID.  Loading the committed envelope after the custody session
    has opened therefore makes every fact consumer prove both the session and
    the exact capsule it reads.
    """
    material = load_profile_custody_password_material(UUID(bucket_id), root=storage_root)
    activate_profile_record_session(ProfileRecordSession.from_envelope(envelope=material.envelope, dek=dek))


def _resume_acceleration_receipt(
    *,
    storage_root: Path,
    bucket_id: str,
    now: datetime,
) -> tuple[ProfileSessionResumeOutcomePort, bytearray | None]:
    """Resume only against the envelope that is current for this capsule."""
    profile_id = UUID(bucket_id)
    material = load_profile_custody_password_material(profile_id, root=storage_root)
    envelope = material.envelope
    return _login_sessions().resume_acceleration_receipt(
        storage_root=storage_root,
        profile_id=profile_id,
        custody_generation=envelope.password_generation,
        dek_epoch=envelope.dek_epoch,
        now=now,
    )


def _persist_advanced_idle_deadline(
    *,
    storage_root: Path,
    profile_id: UUID,
    record: object,
    new_idle_deadline: datetime,
) -> None:
    """Re-persist the record once with its idle deadline rolled forward.

    Best-effort by design: the live session is already open and correct,
    so a keychain or disk hiccup here must not fail the operator's verb —
    it only costs an earlier idle expiry, which is the fail-closed
    direction.
    """
    if not _login_sessions().is_persisted_receipt(record):  # pragma: no cover - typed at the call site
        return
    if new_idle_deadline <= record.idle_deadline:
        return
    try:
        advanced = _login_sessions().advance_acceleration_idle_deadline(
            storage_root=storage_root,
            profile_id=profile_id,
            record=record,
            new_idle_deadline=new_idle_deadline,
        )
        del advanced
    except BaseException as exc:
        if not (isinstance(exc, (OSError, ValueError)) or profile_is_keyring_unavailable(exc)):
            raise
        _log.debug(
            "profile-session idle-deadline re-persist skipped profile_id=%s error_type=%s",
            profile_id,
            type(exc).__name__,
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


def _resolve_selected_target(pointer: BucketPointer) -> ProfileBucketPointer:
    """Resolve the already-selected profile for a bare ``login``.

    The same live-profile resolver used for ``login NAME`` is required here:
    reading a manifest directly by UUID would let a stale pointer select a
    tombstoned bucket and authenticate it before the lifecycle boundary could
    refuse the selection.
    """
    from ..workflow.profile_bucket_scan import resolve_profile_bucket

    if pointer.bucket_id is None:
        raise ProfileNotFoundError(
            translated_message="application.user_profile.errors.no_active_profile_selected",
        )
    assert pointer.bucket_id is not None
    resolved = resolve_profile_bucket(pointer.bucket_id)
    if resolved is None:
        raise ProfileNotFoundError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": pointer.bucket_id},
        )
    return resolved


def _prepare_login_attempt(
    *,
    name: str | None,
    storage_root: Path,
    pointer_transaction: ActiveProfilePointerTransaction,
) -> _LoginAttempt:
    """Resolve the target and capture the exact pointer for one handover."""
    selected = pointer_transaction.read()
    recovery = _recover_interrupted_handover(
        storage_root=storage_root,
        pointer_transaction=pointer_transaction,
    )
    interrupted_handover = recovery.interrupted
    target = resolve_login_target(name) if name is not None else _resolve_selected_target(selected)
    prior_pointer = selected
    if interrupted_handover is not None and target.bucket_id != interrupted_handover.profile_b:
        _refuse_handover_journal("incomplete handover requires authenticating its B profile")
    return _LoginAttempt(
        target=target,
        selected=selected,
        prior_pointer=prior_pointer,
        pointer_transaction=pointer_transaction,
        storage_root=storage_root,
        interrupted_handover=interrupted_handover,
        completed_selection=recovery.completed_selection,
    )


def _can_resume_idempotent_login(
    *,
    attempt: _LoginAttempt,
    live_session: ProfileBucketSessionPort | None,
) -> bool:
    """Return whether the committed target is eligible for a no-op resume."""
    if attempt.interrupted_handover is not None:
        return False
    selected = attempt.selected
    if selected.bucket_id != attempt.target.bucket_id:
        return False
    return live_session is None or _login_sessions().session_serves_bucket(live_session, attempt.target.bucket_id)


def _resume_idempotent_login_if_allowed(
    *,
    attempt: _LoginAttempt,
    now: datetime,
) -> ProfilePersistedSessionPort | None:
    """Resume only when the durable pointer and local binding already agree."""
    live_before = _login_sessions().current_session()
    if not _can_resume_idempotent_login(attempt=attempt, live_session=live_before):
        return None
    return _resume_for_idempotent_login(bucket_id=attempt.target.bucket_id, now=now)


def _idempotent_login_outcome(
    *,
    target: ProfileBucketPointer,
    resumed: ProfilePersistedSessionPort,
) -> ProfileLoginOutcome:
    """Project one resumed persisted session into the public login result."""
    return ProfileLoginOutcome(
        bucket_id=target.bucket_id,
        label=target.label,
        authenticated_at=resumed.issued_at,
        idle_deadline=resumed.idle_deadline,
        absolute_deadline=resumed.absolute_deadline,
        session_persisted=True,
        already_authenticated=True,
        closed_previous_bucket_id=None,
    )


def login_profile(
    *,
    name: str | None = None,
    now: datetime | None = None,
    passphrase_callback: Callable[[], str] | None = None,
) -> ProfileLoginOutcome:
    """Authenticate B before replacing an active A session.

    Target resolution and throttle preflight happen before Argon2.  Password
    authentication creates only transaction-owned candidate memory.  The
    exact pointer capture is compared immediately before publication; then B
    becomes the process binding and optional acceleration is attempted.  A is
    not closed until those operations have succeeded.
    """
    instant = _now() if now is None else now
    storage_root = effective_storage_root()

    with active_profile_pointer_transaction() as pointer_transaction:
        attempt = _prepare_login_attempt(
            name=name,
            storage_root=storage_root,
            pointer_transaction=pointer_transaction,
        )
        resumed = _resume_idempotent_login_if_allowed(attempt=attempt, now=instant)
        if resumed is not None:
            return _idempotent_login_outcome(target=attempt.target, resumed=resumed)

        candidate = _authenticate_login_candidate(
            attempt=attempt,
            now=instant,
            passphrase_callback=passphrase_callback,
        )
        return _finish_candidate_login(attempt=attempt, candidate=candidate)


def _resume_for_idempotent_login(
    *,
    bucket_id: str,
    now: datetime,
) -> ProfilePersistedSessionPort | None:
    """Return the resumed record when the idempotent-login guard applies.

    The guard requires a still-valid PERSISTED record in every case
    ("a login for a profile whose persisted session is
    still valid returns the existing session as a no-op"). A live session
    already bound to this bucket only short-circuits the reopen — the
    record is still peeked, and its absence still means "not idempotent".
    Otherwise the record is resumed through the shared
    :func:`bind_resumed_profile_session` authority.

    Returns ``None`` when the profile must authenticate: either genuinely
    logged out, or holding a live session that was never persisted because
    the host had no usable keychain. In that second case a fresh
    authentication is the fail-closed outcome by design — the no-op is
    anchored to the AAD-bound, deadline-authenticated record, never to
    process memory alone.
    """
    live = _login_sessions().current_session()
    if _login_sessions().session_serves_bucket(live, bucket_id) and live is not None and not live.is_expired(now):
        peeked, _ = _resume_acceleration_receipt(
            storage_root=effective_storage_root(),
            bucket_id=bucket_id,
            now=now,
        )
        return peeked.record if peeked.resumed else None
    if bind_resumed_profile_session(bucket_id=bucket_id, now=now) is not None:
        return None
    peeked, _ = _resume_acceleration_receipt(
        storage_root=effective_storage_root(),
        bucket_id=bucket_id,
        now=now,
    )
    return peeked.record if peeked.resumed else None


def _resolve_login_password(callback: Callable[[], str] | None) -> str:
    """Return the one explicitly supplied password channel for current custody."""
    if callback is not None:
        return callback()
    configured = load_settings().cadrumo_secret_passphrase
    if configured is None:
        refuse_profile_login_without_password_channel()
    return configured.get_secret_value()


def _authenticate_login_candidate(
    *,
    attempt: _LoginAttempt,
    now: datetime,
    passphrase_callback: Callable[[], str] | None,
) -> _CandidateProfileLogin:
    """Apply the throttle gate before authenticating the candidate profile."""
    evaluation = _login_sessions().evaluate_throttle(
        storage_root=attempt.storage_root,
        bucket_id=attempt.target.bucket_id,
        now=now,
    )
    if evaluation.throttled:
        raise ProfileLoginThrottledError(remaining_seconds=evaluation.remaining_seconds)
    return _authenticate_candidate_or_record_failure(
        bucket_id=attempt.target.bucket_id,
        storage_root=attempt.storage_root,
        now=now,
        passphrase_callback=passphrase_callback,
    )


def _finish_candidate_login(
    *,
    attempt: _LoginAttempt,
    candidate: _CandidateProfileLogin,
) -> ProfileLoginOutcome:
    """Reset the online-control cache and close an unpromoted candidate on error."""
    try:
        # Resetting an online-control cache must never turn an already
        # authenticated candidate into an A teardown. It is performed
        # while B is still only transaction-local.
        _login_sessions().reset_throttle(storage_root=attempt.storage_root, bucket_id=attempt.target.bucket_id)
        return _promote_candidate_login(
            candidate=candidate,
            target_label=attempt.target.label,
            selected_bucket_id=attempt.selected.bucket_id,
            prior_pointer=attempt.prior_pointer,
            pointer_transaction=attempt.pointer_transaction,
            storage_root=attempt.storage_root,
            interrupted_handover=attempt.interrupted_handover,
            completed_selection=attempt.completed_selection,
        )
    except BaseException:
        candidate.close()
        raise


def _authenticate_candidate_or_record_failure(
    *,
    bucket_id: str,
    storage_root: Path,
    now: datetime,
    passphrase_callback: Callable[[], str] | None,
) -> _CandidateProfileLogin:
    """Authenticate B into unbound candidate memory and nothing else."""
    material = load_profile_custody_password_material(UUID(bucket_id), root=storage_root)
    password = _resolve_login_password(passphrase_callback)
    try:
        unlocked = unlock_profile_custody_password(material, password=password)
    except BaseException as exc:
        refusal = map_profile_authentication_proof_failure(exc, operation=ProfilePasswordProofOperation.LOGIN)
        if refusal is not None:
            _login_sessions().record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)
            raise refusal from exc
        raise

    dek_buffer = bytearray(unlocked.dek)
    try:
        idle_minutes, absolute_minutes = _bucket_session_windows()
        absolute_deadline = now + timedelta(minutes=absolute_minutes)
        session = _login_sessions().open_resumed_session(
            bucket_id=bucket_id,
            dek=bytes(dek_buffer),
            idle_minutes=idle_minutes,
            opened_at=now,
            idle_deadline=min(now + timedelta(minutes=idle_minutes), absolute_deadline),
            absolute_deadline=absolute_deadline,
            storage_root=storage_root,
        )
        try:
            record_session = ProfileRecordSession.from_envelope(envelope=material.envelope, dek=bytes(dek_buffer))
        except BaseException:
            session.close()
            raise
    finally:
        _login_sessions().zeroise_owned_buffer(dek_buffer)
    return _CandidateProfileLogin(
        bucket_id=bucket_id,
        session=session,
        record_session=record_session,
        material=material,
    )


def _promote_candidate_login(
    *,
    candidate: _CandidateProfileLogin,
    target_label: str,
    selected_bucket_id: str | None,
    prior_pointer: BucketPointer,
    pointer_transaction: ActiveProfilePointerTransaction,
    storage_root: Path,
    interrupted_handover: _ProfileLoginHandoverJournal | None,
    completed_selection: str | None,
) -> ProfileLoginOutcome:
    """CAS-publish, activate, then retire A through durable phases."""
    # The live session is ONE of four inputs to the retirement set, never the
    # gate: it is absent in an ordinary invocation, which is a fresh process.
    # This binding survives for its own separate job -- closing the in-process
    # session object by identity, further down in _retire_previous_authorities.
    previous_live = _login_sessions().current_session()
    retired_bucket_ids = _retired_bucket_ids(
        live_bucket_id=_live_bucket_id(previous_live),
        selected_bucket_id=selected_bucket_id,
        interrupted_bucket_id=None if interrupted_handover is None else interrupted_handover.profile_a,
        completed_selection=completed_selection,
        candidate_bucket_id=candidate.bucket_id,
    )
    retired_bucket_id = retired_bucket_ids[0] if retired_bucket_ids else None
    publication = _publish_candidate_handover(
        candidate=candidate,
        retired_bucket_id=retired_bucket_id,
        prior_pointer=prior_pointer,
        pointer_transaction=pointer_transaction,
        storage_root=storage_root,
        interrupted_handover=interrupted_handover,
    )
    promotion = _bind_candidate_promotion(
        candidate=candidate,
        previous_live=previous_live,
        publication=publication,
        prior_pointer=prior_pointer,
        pointer_transaction=pointer_transaction,
        storage_root=storage_root,
    )

    # Only now can A be retired.  B is durable (or deliberately process-local)
    # and both current-context authorities serve its exact UUID.
    _retire_previous_authorities(
        candidate=candidate,
        previous_live=previous_live,
        previous_record=promotion.previous_record,
        retired_bucket_ids=retired_bucket_ids,
        storage_root=storage_root,
    )
    handover = promotion.journal.at_phase(_HandoverPhase.A_RETIRED)
    _save_handover_journal(storage_root=storage_root, journal=handover)
    # Keep the terminal receipt until the next login observes it.  A process
    # may die immediately after A's zeroisation; retaining this one bounded,
    # non-secret file makes that boundary explicit and lets recovery classify
    # it without inferring completion from a vanished sidecar.
    return ProfileLoginOutcome(
        bucket_id=candidate.bucket_id,
        label=target_label,
        authenticated_at=candidate.session.opened_at,
        idle_deadline=candidate.session.idle_deadline,
        absolute_deadline=candidate.session.absolute_deadline,
        session_persisted=promotion.persisted,
        already_authenticated=False,
        closed_previous_bucket_id=retired_bucket_id,
    )


def _live_bucket_id(session: ProfileBucketSessionPort | None) -> str | None:
    """Return the identity of a prior live session, if one exists."""
    if session is None:
        return None
    return session.bucket_id


def _publish_candidate_handover(
    *,
    candidate: _CandidateProfileLogin,
    retired_bucket_id: str | None,
    prior_pointer: BucketPointer,
    pointer_transaction: ActiveProfilePointerTransaction,
    storage_root: Path,
    interrupted_handover: _ProfileLoginHandoverJournal | None,
) -> _HandoverPublication:
    """Publish a fresh pointer or validate the pointer from interrupted work."""
    if interrupted_handover is None:
        return _publish_fresh_candidate_handover(
            candidate=candidate,
            retired_bucket_id=retired_bucket_id,
            prior_pointer=prior_pointer,
            pointer_transaction=pointer_transaction,
            storage_root=storage_root,
        )
    return _resume_candidate_handover(
        interrupted_handover=interrupted_handover,
        pointer_transaction=pointer_transaction,
    )


def _publish_fresh_candidate_handover(
    *,
    candidate: _CandidateProfileLogin,
    retired_bucket_id: str | None,
    prior_pointer: BucketPointer,
    pointer_transaction: ActiveProfilePointerTransaction,
    storage_root: Path,
) -> _HandoverPublication:
    """Prepare and compare-and-swap the pointer for a new candidate.

    ``profile_a`` witnesses the profile this handover is moving AWAY from, and
    is therefore taken from the same durable-first union the retirement acts on.
    Once the pointer is published it names B, so the journal is the only place a
    later recovery process can still learn A's identity.
    """
    planned_pointer = (
        prior_pointer
        if prior_pointer.bucket_id == candidate.bucket_id
        else BucketPointer.selected(
            bucket_id=candidate.bucket_id,
            transition_revision=prior_pointer.transition_revision + 1,
        )
    )
    handover = _ProfileLoginHandoverJournal.prepare(
        profile_a=retired_bucket_id,
        profile_b=candidate.bucket_id,
        pointer_before=prior_pointer,
        pointer_after=planned_pointer,
        activation_at=_now(),
    )
    _save_handover_journal(storage_root=storage_root, journal=handover)
    published = pointer_transaction.compare_and_select(expected=prior_pointer, bucket_id=candidate.bucket_id)
    if published != handover.pointer_after:
        _refuse_handover_journal("published pointer differs from prepared B witness")
    handover = handover.at_phase(_HandoverPhase.POINTER_PUBLISHED)
    _save_handover_journal(storage_root=storage_root, journal=handover)
    return _HandoverPublication(journal=handover, published_pointer=published)


def _resume_candidate_handover(
    *,
    interrupted_handover: _ProfileLoginHandoverJournal,
    pointer_transaction: ActiveProfilePointerTransaction,
) -> _HandoverPublication:
    """Validate the durable pointer before replaying an interrupted handover."""
    published = interrupted_handover.pointer_after
    if pointer_transaction.read() != published:
        _refuse_handover_journal("incomplete handover B pointer changed before recovery")
    return _HandoverPublication(journal=interrupted_handover, published_pointer=published)


def _bind_candidate_promotion(
    *,
    candidate: _CandidateProfileLogin,
    previous_live: ProfileBucketSessionPort | None,
    publication: _HandoverPublication,
    prior_pointer: BucketPointer,
    pointer_transaction: ActiveProfilePointerTransaction,
    storage_root: Path,
) -> _CandidatePromotionResult:
    """Bind B and complete required durable phases inside the rollback window."""
    previous_record: ProfileRecordSession | None = None
    handover = publication.journal
    try:
        # Receipt retries are deliberately explicit: the canonical custody
        # primitive treats matching bytes as a no-op, while also retiring only
        # its verified predecessor sidecar if a process died after publication
        # but before durable cleanup.  Do this before B gains any live binding.
        _save_handover_journal(storage_root=storage_root, journal=handover)
        # Both context bindings are in-process and do not perform I/O.  A has
        # not been closed, so an unexpected later failure can rebind it before
        # the durable pointer is restored.
        _login_sessions().bind_session(candidate.session)
        previous_record = bind_active_profile_record_session(candidate.record_session)
        bound = handover.at_least_phase(_HandoverPhase.B_BOUND)
        if bound != handover:
            _save_handover_journal(storage_root=storage_root, journal=bound)
        handover = bound
        persisted = _mint_or_warn(
            storage_root=storage_root,
            material=candidate.material,
            session=candidate.session,
        )
        accelerated = handover.at_least_phase(_HandoverPhase.ACCELERATED)
        if accelerated != handover:
            _save_handover_journal(storage_root=storage_root, journal=accelerated)
        handover = accelerated
        # Activation is required B state, not best-effort telemetry.  Keep it
        # inside the rollback window, with one stable event instant so a crash
        # before the phase receipt can replay the same content-addressed event.
        _record_activation(profile_id=candidate.bucket_id, occurred_at=handover.activation_at)
        activated = handover.at_least_phase(_HandoverPhase.ACTIVATED)
        if activated != handover:
            _save_handover_journal(storage_root=storage_root, journal=activated)
        handover = activated
    except BaseException:
        _rollback_candidate_promotion(
            candidate=candidate,
            previous_live=previous_live,
            previous_record=previous_record,
            prior_pointer=prior_pointer,
            published_pointer=publication.published_pointer,
            pointer_transaction=pointer_transaction,
            storage_root=storage_root,
        )
        raise
    return _CandidatePromotionResult(journal=handover, previous_record=previous_record, persisted=persisted)


def _retire_previous_authorities(
    *,
    candidate: _CandidateProfileLogin,
    previous_live: ProfileBucketSessionPort | None,
    previous_record: ProfileRecordSession | None,
    retired_bucket_ids: tuple[str, ...],
    storage_root: Path,
) -> None:
    """Retire A completely, in process and on disk, after B is fully durable.

    Closing A's two in-process authorities is not retirement on its own. A's
    acceleration receipt wraps A's bucket DEK under a key the OS keychain still
    holds, and a handover rotates neither A's custody generation nor its DEK
    epoch, so a receipt left behind stays resumable: it hands back A's bucket
    DEK without A's passphrase, which is the profile-A resurrection this phase
    exists to refuse. Revoking the durable artefacts is therefore part of
    retiring A, not cleanup that can be deferred.

    ``retired_bucket_ids`` holds every bucket the handover actually moved away
    from, and is empty when the login re-entered the profile already selected.
    That distinction is load-bearing: revoking on a same-profile re-login would
    destroy the receipt this very login just minted.
    """
    if previous_live is not None and previous_live is not candidate.session:
        previous_live.close()
    if previous_record is not None and previous_record is not candidate.record_session:
        previous_record.close()
    for bucket_id in retired_bucket_ids:
        _revoke_profile_session_artefacts(storage_root=storage_root, bucket_id=bucket_id)


def _retired_bucket_ids(
    *,
    live_bucket_id: str | None,
    selected_bucket_id: str | None,
    interrupted_bucket_id: str | None,
    completed_selection: str | None,
    candidate_bucket_id: str,
) -> tuple[str, ...]:
    """Report every prior profile this handover actually moves away from.

    Four observations are folded because no single one is complete, and a
    profile whose durable session artefacts survive the handover is resumable
    without its passphrase:

    * the live in-process session, which is the only source when one process
      switches profiles, and is absent in an ordinary command-line invocation
      because every invocation is a fresh process;
    * the durable active pointer captured before publication, which names the
      retired profile in a fresh process, and has already moved on to B once
      an interrupted handover is being replayed;
    * the interrupted handover's own witness, which is the only source left
      once that publication happened in a process that then died;
    * the profile the last COMPLETED handover selected, which is the only
      source left once an out-of-band pointer writer moved the selection in
      between. Registering a profile is exactly such a writer -- the create
      transaction compare-and-swaps the pointer onto the new capsule -- so
      after register-login-register-login the captured pointer names the
      profile being entered rather than the one being left, and without this
      the displaced profile keeps a resumable receipt.

    The candidate is excluded rather than filtered later: a login that re-enters
    the profile already selected retires nothing, and revoking there would
    destroy the receipt that same login just minted.
    """
    return tuple(
        value
        for value in _distinct_bucket_ids(
            live_bucket_id,
            selected_bucket_id,
            interrupted_bucket_id,
            completed_selection,
        )
        if value != candidate_bucket_id
    )


def _rollback_candidate_promotion(
    *,
    candidate: _CandidateProfileLogin,
    previous_live: ProfileBucketSessionPort | None,
    previous_record: ProfileRecordSession | None,
    prior_pointer: BucketPointer,
    published_pointer: BucketPointer,
    pointer_transaction: ActiveProfilePointerTransaction,
    storage_root: Path,
) -> None:
    """Restore A and erase every B candidate artefact after swap failure."""
    try:
        _login_sessions().delete_acceleration_receipt(
            storage_root=storage_root,
            profile_id=candidate.material.envelope.profile_id,
        )
    finally:
        if previous_live is not None:
            _login_sessions().bind_session(previous_live)
        else:
            _login_sessions().close_active_session()
        if previous_record is not None:
            bind_active_profile_record_session(previous_record)
        else:
            clear_active_profile_record_session_binding(candidate.record_session)
        candidate.close()
        pointer_transaction.compare_and_restore(expected=published_pointer, captured=prior_pointer)


def _record_activation(*, profile_id: str, occurred_at: datetime) -> None:
    """Record that ``profile_id`` became the active profile.

    Authentication and activation are one operation from the operator's
    point of view, so a successful login owes the same two records the
    dedicated selection span writes: the workflow-state selection, and the
    ``PROFILE_ACTIVATED`` entry in the bucket-event catalogue that lets an
    auditor replay which profile became active and when.

    Both are delegated to the primitives that already own them rather than
    re-implemented here. The dedicated span is deliberately NOT reused: it
    opens its own pointer transaction and re-acquires the per-bucket lock,
    and this runs inside a caller that already holds both, so composing the
    span would nest them against the project-wide pointer-then-bucket lock
    order. Reading the workflow state also surfaces a bucket whose manifest
    exists but whose encrypted profile record does not, so activation
    validates rather than silently succeeding.

    Only a genuine authentication reaches here: the idempotent no-op
    returns before this point, so a retry re-stamps no activation.
    """
    from ...core.config import override_settings
    from ...domain.buckets import BucketEventObjectType, BucketEventType, emit_bucket_event

    # A CLI invocation may have resolved and pinned the previously active
    # profile before an interactive login selects this one.  The pointer and
    # bucket session already name ``profile_id`` here, so let that authenticated
    # identity own the storage route for the activation write too.  Otherwise
    # the inherited settings override can route the database to the previous
    # bucket and manufacture a route/session mismatch after valid credentials.
    with override_settings(cadrumo_active_profile=profile_id):
        # Through the shared emitter, not a bare load-append-save: the history is
        # a singleton row, so an unguarded rewrite drops whatever another
        # process committed in between -- and a lost activation entry leaves no
        # gap to notice, because the surviving events are all internally intact.
        emit_bucket_event(
            repository=default_profile_bucket_event_history_repository(),
            bucket_id=profile_id,
            event_type=BucketEventType.PROFILE_ACTIVATED,
            occurred_at=occurred_at,
            actor="profile-login",
            object_type=BucketEventObjectType.PROFILE,
            object_id=profile_id,
            payload={"active_profile": resolve_active_bucket_id() or profile_id},
            payload_version=1,
        )


def _mint_or_warn(
    *,
    storage_root: Path,
    material: ProfileCustodyPasswordMaterialPort,
    session: ProfileBucketSessionPort,
) -> bool:
    """Mint the persisted session, or report a process-scoped login.

    A host with no usable OS keychain has nowhere secure to custody the
    session key, so no persisted artefact is written at all — failing
    closed beats writing key material to disk. The login still succeeds
    for this process; the caller surfaces the warning.
    """
    try:
        idle_minutes, absolute_minutes = _bucket_session_windows()
        _login_sessions().mint_acceleration_receipt(
            storage_root=storage_root,
            profile_id=material.envelope.profile_id,
            custody_generation=material.envelope.password_generation,
            dek_epoch=material.envelope.dek_epoch,
            dek=session.dek,
            now=session.opened_at,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
        )
    except BaseException as exc:
        if not profile_is_keyring_unavailable(exc):
            raise
        _log.info(
            "profile session not persisted (no usable OS keychain); login is process-scoped profile_id=%s",
            material.envelope.profile_id,
        )
        return False
    return True


__all__ = [
    "ProfileCustodySessionOwnerEffect",
    "ProfileLoginOutcome",
    "ProfileLoginThrottledError",
    "bind_resumed_profile_session",
    "close_profile_session_artefacts",
    "has_live_profile_session",
    "login_profile",
    "logout_active_profile",
    "remove_profile_session_acceleration_for_custody_delete",
    "revoke_live_profile_secret_for_custody_delete",
]
