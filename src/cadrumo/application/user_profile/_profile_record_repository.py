"""Session-bound read authority for the capsule-resident current record.

This is intentionally not a generic persistence repository.  It cannot create
rows, save arbitrary aggregates, delete, tombstone, or reactivate anything.
The physical capsule lifecycle stages and publishes bytes; this narrow owner
only authenticates the one exact current fact record for an already-bound
session.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from ...core.paths import effective_storage_root
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventType
from ...domain.user_profile import ProfileNotFoundError, ProfileSetupState, UserProfileFact, UserProfileRecord
from ._capsule_record import (
    ProfileRecordCommandEvent,
    ProfileRecordConflictError,
    ProfileRecordSession,
    ProfileRecordStore,
)
from ._custody_ports import (
    profile_custody_record_session_material,
)
from ._login_session_port import profile_current_bucket_session, profile_session_serves_bucket

_ACTIVE_RECORD_SESSION: ContextVar[ProfileRecordSession | None] = ContextVar(
    "active_profile_record_session", default=None
)

_ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED: ContextVar[bool] = ContextVar(
    "active_profile_record_session_is_session_derived", default=False
)
"""Whether the latched authority was derived from a live custody session.

The two ways an authority becomes current are not the same kind of fact. One
is DERIVED: a login opens a custody session and the authority is minted from
it, so the session is what makes the authority true and the authority cannot
outlive it. The other is BOUND: a caller holding a record session it opened
itself installs it explicitly, and owns its lifetime end to end.

Only the derived kind is retired by the disappearance of a custody session,
which is why the distinction is recorded rather than inferred -- inferring it
from "is a custody session live?" alone would revoke every explicitly bound
authority the moment no profile happened to be logged in.
"""


@contextmanager
def bound_profile_record_session(session: ProfileRecordSession) -> Generator[None]:
    """Bind one authenticated record session for the duration of a command."""
    token: Token[ProfileRecordSession | None] = _ACTIVE_RECORD_SESSION.set(session)
    derived_token: Token[bool] = _ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED.set(False)
    try:
        yield
    finally:
        _ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED.reset(derived_token)
        _ACTIVE_RECORD_SESSION.reset(token)


def activate_profile_record_session(session: ProfileRecordSession) -> None:
    """Install the authenticated record authority for the active process session.

    The caller has already authenticated and bound the matching custody DEK.  A
    later login must retire the old record authority before publishing the new
    one, so a profile switch cannot leave facts decryptable through a prior
    session.
    """
    previous = _ACTIVE_RECORD_SESSION.get()
    if previous is not None and previous is not session:
        previous.close()
    _ACTIVE_RECORD_SESSION.set(session)
    _ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED.set(True)


def bind_active_profile_record_session(session: ProfileRecordSession) -> ProfileRecordSession | None:
    """Bind a candidate record authority without retiring the prior session.

    Handover owns the two-phase lifetime: it first makes B observable, then
    retires A only after every required B publication succeeds.  Returning A
    lets that owner restore the exact prior authority if a later publication
    fails, without a transient plaintext re-authentication or a duplicate
    record-session constructor.
    """
    previous = _ACTIVE_RECORD_SESSION.get()
    _ACTIVE_RECORD_SESSION.set(session)
    # Session-derived like the activating door: handover binds the candidate's
    # authority beside the candidate's bucket session, and restores the prior
    # authority beside the prior bucket session on rollback. Both halves are
    # backed by a custody session, so both must retire when it goes.
    _ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED.set(True)
    return previous


def clear_active_profile_record_session_binding(expected: ProfileRecordSession) -> None:
    """Clear only an expected active binding without closing its owner.

    Candidate cleanup first removes the context reference, then zeroises the
    candidate.  The identity check prevents a late cleanup from unbinding a
    replacement session installed by a nested operation.
    """
    if _ACTIVE_RECORD_SESSION.get() is expected:
        _ACTIVE_RECORD_SESSION.set(None)
        _ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED.set(False)


def close_active_profile_record_session() -> None:
    """Zeroise and clear the process-local record authority."""
    session = _ACTIVE_RECORD_SESSION.get()
    if session is not None:
        session.close()
    _ACTIVE_RECORD_SESSION.set(None)
    _ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED.set(False)


def profile_record_session_if_authenticated(profile_id: str | UUID) -> ProfileRecordSession | None:
    """Return the record authority serving this UUID, or ``None`` when none is live.

    This is the structural answer to "is this profile unlocked?", and callers
    that need to tell a LOCKED profile from a broken one ask it here rather
    than inferring the answer from a refusal message.  An absent session is an
    ordinary, expected state -- the operator has simply not logged in -- so it
    is reported as an absence rather than raised;
    :func:`require_profile_record_session` converts it for the callers whose
    contract is a session or nothing.

    The installed authority is process-local, so a second profile becoming
    the live custody session in the same process would otherwise be read
    through the first profile's latched authority -- or, because the identity
    guard refuses that, not be readable at all until the process restarts.
    An authority that does not serve the requested UUID is therefore re-derived
    rather than refused outright.

    Re-derivation stays as narrow as the first derivation: it succeeds only
    from the requested profile's already-open custody session, so an
    unauthenticated profile remains unreadable, and installing the derived
    authority retires the one it replaces so a switch cannot leave facts
    decryptable through a prior session.

    A latched authority must be LIVE as well as correctly addressed. Retirement
    zeroises the key in place and leaves the object latched, so the identity
    check alone cannot tell a retired authority from a working one: a span that
    binds a session, has it retired under it, and then restores its own prior
    binding on exit hands the next caller a UUID-matching authority with no key
    behind it. That reached the caller as an integrity error from deep inside
    the decrypt, blaming the read for a decision made when the session was
    reused.

    A retired authority is therefore treated exactly as an absent one -- it
    carries no authority, so it is re-derived where a live custody session
    exists and reported absent where none does. Nothing is unbound on the
    declining path: a read that declines should not mutate process state, and a
    successful later derivation replaces the dead reference anyway.

    A SESSION-DERIVED authority must also still be BACKED. Login mints it from
    a live custody session and latches it, and nothing re-checked that
    derivation afterwards, so closing the bucket session by any path other than
    the strong logout left the authority behind and facts readable through it:
    within one process, "logged out" and "record authority gone" were different
    states, and a health check after a logout still read facts through the
    survivor. The custody session is therefore consulted on every resolution of
    a derived authority -- an in-memory check, no capsule read -- and one whose
    session is gone declines exactly as an absent one does.

    An EXPLICITLY BOUND authority is untouched by this. A caller that opened a
    record session itself and installed it owns its lifetime; requiring a live
    custody session behind it would revoke every such binding the moment no
    profile happened to be logged in, which is a different behaviour, not a
    stricter one.

    Declining does not zeroise it. The record authority and the bucket session
    are bound together and rebound together during the login handover's
    rollback window, so a reader is not the owner that may destroy either;
    :func:`~cadrumo.application.user_profile.logout_active_profile`, which is
    the close owner, wipes it there.

    A ``profile_id`` that is not a canonical UUID still raises: that is a
    caller defect rather than a lock state, and returning ``None`` for it would
    let a malformed identity read as a merely locked profile.
    """
    try:
        identity = UUID(str(profile_id))
    except ValueError as exc:
        raise ProfileNotFoundError("profile identity is not a canonical UUID") from exc
    session = _ACTIVE_RECORD_SESSION.get()
    if session is not None and session.profile_id == identity and not session.closed:
        if not _ACTIVE_RECORD_SESSION_IS_SESSION_DERIVED.get():
            return session
        if _live_custody_session_backs(identity):
            return session
        return None
    derived = _record_session_from_live_custody_session(identity)
    if derived is None:
        return None
    activate_profile_record_session(derived)
    return derived


def require_profile_record_session(profile_id: str | UUID) -> ProfileRecordSession:
    """Return the record authority that serves this exact UUID, or refuse.

    The authority resolution itself lives in
    :func:`profile_record_session_if_authenticated`; this door is for callers
    whose contract admits no absence.

    Raises:
        ProfileNotFoundError: When no authenticated session serves this UUID,
            or when ``profile_id`` is not a canonical UUID.
    """
    session = profile_record_session_if_authenticated(profile_id)
    if session is None:
        raise ProfileNotFoundError("profile facts require an authenticated session for this committed capsule")
    return session


def _live_custody_session_backs(profile_id: UUID) -> bool:
    """Return whether a custody session is both serving and still usable.

    Two questions, deliberately asked together. Identity alone is what the
    substrate's own reuse predicate answers, and it is not sufficient here: a
    session is sealed IN PLACE, so a closed one keeps naming its bucket and
    keeps satisfying an identity comparison long after its key is zeroised.
    Reading the seal is what turns "a session exists for this profile" into
    "a session that can still decrypt exists for this profile", which is the
    property a record authority actually depends on.

    Both are in-memory reads; nothing is opened and no capsule file is
    touched, so this is cheap enough to ask on every resolution.
    """
    live = profile_current_bucket_session()
    return live is not None and profile_session_serves_bucket(live, str(profile_id)) and not live.sealed


def _record_session_from_live_custody_session(profile_id: UUID) -> ProfileRecordSession | None:
    """Derive record authority only from the exact already-open custody session."""
    material = profile_custody_record_session_material(profile_id)
    if material is None:
        return None
    return ProfileRecordSession.from_envelope(envelope=material.envelope, dek=material.dek)


class ProfileRecordRepository:
    """Read exactly one encrypted current record through an authenticated session."""

    def __init__(self, *, session: ProfileRecordSession, root: Path | None = None) -> None:
        self._session = session
        self._root = effective_storage_root(root)

    @classmethod
    def for_current_session(cls, profile_id: str | UUID, *, root: Path | None = None) -> ProfileRecordRepository:
        return cls(session=require_profile_record_session(profile_id), root=root)

    @property
    def profile_id(self) -> UUID:
        return self._session.profile_id

    def load(self, profile_id: str | UUID) -> UserProfileRecord:
        identity = UUID(str(profile_id))
        if identity != self._session.profile_id:
            raise ProfileNotFoundError("profile record session does not serve the requested UUID")
        return ProfileRecordStore(session=self._session, root=self._root).load().record

    def complete_setup(
        self,
        profile_id: str | UUID,
        *,
        expected_revision: int,
        expected_content_digest: str,
        now: datetime | None = None,
    ) -> UserProfileRecord:
        """CAS-complete setup; the lifecycle owns the physical replacement.

        Judged through the same authority every fact-writing door uses, but at
        the strictest setting the authority offers. A profile born incomplete
        defers exactly the missing-required-field issues, and this promotion is
        the moment they come due: COMPLETE is not a label for a record that has
        stopped being edited, it is the CLAIM that nothing required is missing.
        Promoting without re-applying them publishes that claim about a record
        that does not support it, and every downstream surface reading setup
        state then trusts it -- which is why this door judges harder than the
        doors that merely write a fact, rather than the same amount.

        The already-COMPLETE early return above stays ahead of the judgement on
        purpose: it is an idempotent no-op that publishes nothing, so holding it
        to a contract a stored record may predate would refuse a caller that
        changes no state.

        Raises:
            ProfileNotFoundError: When the bound session does not serve
                ``profile_id``.
            ProfileRecordConflictError: When the compare-and-swap fails.
            ProfileSchemaValidationError: When the record does not satisfy the
                complete-profile contract it is being promoted into.
        """
        from ._validation import reject_invalid_profile_facts

        identity = UUID(str(profile_id))
        if identity != self._session.profile_id:
            raise ProfileNotFoundError("profile record session does not serve the requested UUID")
        current = self.load(identity)
        if current.record_revision != expected_revision or current.content_digest != expected_content_digest:
            raise ProfileRecordConflictError("profile record revision compare-and-swap failed")
        if current.setup_state is ProfileSetupState.COMPLETE:
            return current
        reject_invalid_profile_facts(str(identity), current.facts, require_complete=True)
        occurred_at = (now or _utc_now()).astimezone(UTC)
        replacement = UserProfileRecord(
            schema_id=current.schema_id,
            schema_version=current.schema_version,
            profile_id=current.profile_id,
            facts=current.facts,
            setup_state=ProfileSetupState.COMPLETE,
            record_revision=current.record_revision + 1,
            previous_record_digest=current.content_digest,
            content_digest="",
            created_at=current.created_at,
            updated_at=occurred_at,
        )
        from ._lifecycle import ProfileCapsuleLifecycle

        # The lifecycle names this deliberate repository-only collaboration private;
        # this explicit command owner is its sole cross-class caller.
        ProfileCapsuleLifecycle(root=self._root)._replace_record_for_profile_command(  # pyright: ignore[reportPrivateUsage]
            profile_id=identity,
            record_session=self._session,
            replacement=replacement,
            event=ProfileRecordCommandEvent(
                event_type=BucketEventType.PROFILE_SETUP_COMPLETED,
                occurred_at=occurred_at.isoformat(),
            ),
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
        )
        return replacement

    def apply_fact_changes(
        self,
        profile_id: str | UUID,
        *,
        facts: tuple[UserProfileFact, ...],
        expected_revision: int,
        expected_content_digest: str,
        event_type: BucketEventType,
        event_payload: Mapping[str, str],
        now: datetime | None = None,
    ) -> UserProfileRecord:
        """CAS-publish an explicit fact replacement and its command event.

        ``facts`` is the complete next exact fact sequence, rather than an
        implicit upsert patch.  Callers must load and compose that sequence
        first, which keeps every mutation revision-bound and makes a cleared
        fact as explicit as an added one.  The lifecycle publishes the
        encrypted replacement and its authenticated event in the same capsule
        data-file replacement.

        ``event_type`` is the closed catalogue member, never a free string, and
        the command witness it is carried on declares the same closed type, so a
        caller-invented string can no longer travel as far as the capsule
        writer.  Taking the member here rather than a string puts the accepted
        set in front of the caller at the call site, where the alternative was a
        refusal deep inside the writer that cost the whole command -- every fact
        it carried included.
        """
        identity = UUID(str(profile_id))
        # Narrowed here rather than trusted, so an untyped caller is refused
        # BEFORE the record is read and the replacement composed.  The command
        # witness below now declares the closed member itself and would refuse
        # too, but only after the load and the compare-and-swap have run.
        event = BucketEventType(event_type)
        if identity != self._session.profile_id:
            raise ProfileNotFoundError("profile record session does not serve the requested UUID")
        current = self.load(identity)
        if current.record_revision != expected_revision or current.content_digest != expected_content_digest:
            raise ProfileRecordConflictError("profile record revision compare-and-swap failed")
        occurred_at = (now or _utc_now()).astimezone(UTC)
        replacement = UserProfileRecord(
            schema_id=current.schema_id,
            schema_version=current.schema_version,
            profile_id=current.profile_id,
            facts=facts,
            setup_state=current.setup_state,
            record_revision=current.record_revision + 1,
            previous_record_digest=current.content_digest,
            content_digest="",
            created_at=current.created_at,
            updated_at=occurred_at,
        )
        from ._lifecycle import ProfileCapsuleLifecycle

        # The lifecycle names this deliberate repository-only collaboration private;
        # this explicit command owner is its sole cross-class caller.
        ProfileCapsuleLifecycle(root=self._root)._replace_record_for_profile_command(  # pyright: ignore[reportPrivateUsage]
            profile_id=identity,
            record_session=self._session,
            replacement=replacement,
            event=ProfileRecordCommandEvent(
                event_type=event,
                occurred_at=occurred_at.isoformat(),
                payload=event_payload,
            ),
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
        )
        return replacement


__all__ = [
    "ProfileRecordRepository",
    "activate_profile_record_session",
    "bind_active_profile_record_session",
    "bound_profile_record_session",
    "clear_active_profile_record_session_binding",
    "close_active_profile_record_session",
    "profile_record_session_if_authenticated",
    "require_profile_record_session",
]
