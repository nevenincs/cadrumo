"""Committed lease retirement facts, independent of physical cleanup and delivery."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from .access_contracts import AccessDenialCode


class SessionRetirementKind(StrEnum):
    """Allowlisted changes a frontend must use to clear private views."""

    REVOKED = "revoked"
    SIGNED_OUT = "signed_out"
    PROFILE_LOCKED = "profile_locked"
    CUSTODY_CHANGED = "custody_changed"


@dataclass(frozen=True, slots=True)
class SessionRetirement:
    """One published lease removed from authority, carrying no transferable proof."""

    profile_id: UUID
    connection_id: UUID
    session_id: UUID
    reason: AccessDenialCode
    kind: SessionRetirementKind = SessionRetirementKind.REVOKED
