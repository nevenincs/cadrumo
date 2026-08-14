"""Session-bound read authority for the capsule-resident current record.

This is intentionally not a generic persistence repository.  It cannot create
rows, save arbitrary aggregates, delete, tombstone, or reactivate anything.
The physical capsule lifecycle stages and publishes bytes; this narrow owner
only authenticates the one exact current fact record for an already-bound
session.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Iterator
from uuid import UUID

from ...adapters.persistence.storage.custody import load_committed_profile_custody_data_file
from ...core.paths import effective_storage_root
from ...domain.user_profile import ProfileNotFoundError, UserProfileRecord
from ._capsule_record import PROFILE_RECORD_DATA_FILENAME, ProfileRecordSession

_ACTIVE_RECORD_SESSION: ContextVar[ProfileRecordSession | None] = ContextVar("active_profile_record_session", default=None)


@contextmanager
def bound_profile_record_session(session: ProfileRecordSession) -> Iterator[None]:
    """Bind one authenticated record session for the duration of a command."""
    token: Token[ProfileRecordSession | None] = _ACTIVE_RECORD_SESSION.set(session)
    try:
        yield
    finally:
        _ACTIVE_RECORD_SESSION.reset(token)


def require_profile_record_session(profile_id: str | UUID) -> ProfileRecordSession:
    """Return the active session only when it serves this exact UUID."""
    try:
        identity = UUID(str(profile_id))
    except ValueError as exc:
        raise ProfileNotFoundError("profile identity is not a canonical UUID") from exc
    session = _ACTIVE_RECORD_SESSION.get()
    if session is None or session.profile_id != identity:
        raise ProfileNotFoundError("profile facts require an authenticated session for this committed capsule")
    return session


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
        payload = load_committed_profile_custody_data_file(
            identity,
            PROFILE_RECORD_DATA_FILENAME,
            root=self._root,
        )
        record, _ = self._session.decode_current(payload)
        return record


__all__ = ["ProfileRecordRepository", "bound_profile_record_session", "require_profile_record_session"]
