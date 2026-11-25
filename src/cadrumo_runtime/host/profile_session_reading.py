"""Pure predicates for profile sessions."""

from __future__ import annotations

from datetime import datetime
from typing import TypeGuard

from cadrumo.application.user_profile.automation_custody_port import AutomationCustodySnapshot
from cadrumo_client.contracts.access_refusals import AccessDenied
from cadrumo_client.contracts.access_vocabulary import AuthorityState
from cadrumo_client.contracts.profile_access import ProfileStatus


def issued_key_can_admit(snapshot: AutomationCustodySnapshot, instant: datetime) -> bool:
    """Say whether an issued key could still admit an automation: a sign-out ends no key session."""
    if not snapshot.automation_enabled:
        return False
    live_grants = {
        grant.grant_id
        for grant in snapshot.grants
        if grant.state is AuthorityState.ACTIVE and grant.unattended and grant.valid_from <= instant < grant.expires_at
    }
    return any(
        key.grant_id in live_grants
        and key.state is AuthorityState.ACTIVE
        and key.valid_from <= instant < key.expires_at
        for key in snapshot.keys
    )


def login_completed(result: ProfileStatus | AccessDenied) -> TypeGuard[ProfileStatus]:
    """Determine whether admission completed a bound authenticated session."""
    return (
        isinstance(result, ProfileStatus)
        and result.status.denial is None
        and result.status.connected
        and result.status.credential_authenticated
        and result.status.profile_bound
    )
