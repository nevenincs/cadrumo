"""Authenticated record bindings for profile repository behavior tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from ..capsule_record import ProfileRecordSession
from ..profile_record_repository import ACTIVE_RECORD_AUTHORITY, ProfileRecordAuthority


@contextmanager
def bound_profile_record_session(session: ProfileRecordSession) -> Generator[None]:
    """Bind one authenticated record session for the duration of a command."""
    with ACTIVE_RECORD_AUTHORITY.override(ProfileRecordAuthority(session=session, session_derived=False)):
        yield
