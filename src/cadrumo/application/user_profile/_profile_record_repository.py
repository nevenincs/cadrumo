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
from ...domain.user_profile import ProfileNotFoundError, ProfileSetupState, UserProfileFact, UserProfileRecord
from ..profile_custody import profile_custody_record_session_material
from ._capsule_record import (
    ProfileRecordCommandEvent,
    ProfileRecordConflictError,
    ProfileRecordSession,
    ProfileRecordStore,
)

_ACTIVE_RECORD_SESSION: ContextVar[ProfileRecordSession | None] = ContextVar(
    "active_profile_record_session", default=None
)


@contextmanager
def bound_profile_record_session(session: ProfileRecordSession) -> Generator[None]:
    """Bind one authenticated record session for the duration of a command."""
    token: Token[ProfileRecordSession | None] = _ACTIVE_RECORD_SESSION.set(session)
    try:
        yield
    finally:
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
    return previous


def clear_active_profile_record_session_binding(expected: ProfileRecordSession) -> None:
    """Clear only an expected active binding without closing its owner.

    Candidate cleanup first removes the context reference, then zeroises the
    candidate.  The identity check prevents a late cleanup from unbinding a
    replacement session installed by a nested operation.
    """
    if _ACTIVE_RECORD_SESSION.get() is expected:
        _ACTIVE_RECORD_SESSION.set(None)


def close_active_profile_record_session() -> None:
    """Zeroise and clear the process-local record authority."""
    session = _ACTIVE_RECORD_SESSION.get()
    if session is not None:
        session.close()
    _ACTIVE_RECORD_SESSION.set(None)


def require_profile_record_session(profile_id: str | UUID) -> ProfileRecordSession:
    """Return the record authority that serves this exact UUID.

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
    """
    try:
        identity = UUID(str(profile_id))
    except ValueError as exc:
        raise ProfileNotFoundError("profile identity is not a canonical UUID") from exc
    session = _ACTIVE_RECORD_SESSION.get()
    if session is not None and session.profile_id == identity:
        return session
    derived = _record_session_from_live_custody_session(identity)
    if derived is None:
        raise ProfileNotFoundError("profile facts require an authenticated session for this committed capsule")
    activate_profile_record_session(derived)
    return derived


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
        """CAS-complete setup; the lifecycle owns the physical replacement."""
        identity = UUID(str(profile_id))
        if identity != self._session.profile_id:
            raise ProfileNotFoundError("profile record session does not serve the requested UUID")
        current = self.load(identity)
        if current.record_revision != expected_revision or current.content_digest != expected_content_digest:
            raise ProfileRecordConflictError("profile record revision compare-and-swap failed")
        if current.setup_state is ProfileSetupState.COMPLETE:
            return current
        occurred_at = (now or datetime.now(UTC)).astimezone(UTC)
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
                event_type="profile.setup.completed",
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
        event_type: str,
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
        """
        identity = UUID(str(profile_id))
        if identity != self._session.profile_id:
            raise ProfileNotFoundError("profile record session does not serve the requested UUID")
        current = self.load(identity)
        if current.record_revision != expected_revision or current.content_digest != expected_content_digest:
            raise ProfileRecordConflictError("profile record revision compare-and-swap failed")
        occurred_at = (now or datetime.now(UTC)).astimezone(UTC)
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
                event_type=event_type,
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
    "require_profile_record_session",
]
