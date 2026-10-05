"""Connection-bound access leases over existing custody and authorization policy."""

from __future__ import annotations

from .session_authority_access import SessionAuthorityAccess
from .session_authority_admission import SessionAuthorityAdmission
from .session_authority_lifecycle import SessionAuthorityLifecycle


class ProfileSessionAuthority(SessionAuthorityAdmission, SessionAuthorityAccess, SessionAuthorityLifecycle):
    """One profile's ephemeral leases for one runtime boot, serialized by its owner."""
