"""Identify positive native lock evidence for a profile's human sign-ins."""

from __future__ import annotations

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt_crypto import (
    PersistedProfileSession,
    profile_session_login_matches,
)
from cadrumo.application.user_profile.access_contracts import LoginEligibility, OsLockState, OsLoginContext


def locked_login_ids(
    observed: tuple[OsLoginContext, ...], relevant: frozenset[str], owner: str, receipt: PersistedProfileSession | None
) -> set[str]:
    """Select matching native logins with positive lock or logout evidence."""
    positive = {
        login.login_id
        for login in observed
        if login.os_owner_id == owner
        and (
            login.login_id in relevant
            or (receipt is not None and profile_session_login_matches(record=receipt, login_id=login.login_id))
        )
        and (
            login.lock_state is OsLockState.LOCKED
            or (not login.active and login.unattended is LoginEligibility.INELIGIBLE)
        )
    }
    return positive
