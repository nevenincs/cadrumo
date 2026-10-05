"""Exact grant, key and enrollment state projection after durable denial."""

from __future__ import annotations

from .....application.user_profile.access_contracts import (
    AuthorityState,
)
from .....application.user_profile.automation_enrollment import (
    EnrollmentGrant,
    EnrollmentRecord,
    EnrollmentStage,
)
from .....application.user_profile.automation_lifecycle import (
    AutomationDenial,
    AutomationDenialKind,
)
from .automation_control_projection import changed_control_model
from .automation_records import (
    AutomationControlPayload,
    StoredAutomationGrant,
)


def denied_enrollment_grant(stored: StoredAutomationGrant, change: AutomationDenial, locking: bool) -> EnrollmentGrant:
    """Apply the addressed grant or key denial without changing inventory order."""
    grant = stored.grant
    affected = change.kind in {AutomationDenialKind.ALL, AutomationDenialKind.PROFILE_LOCK} or (
        change.kind is AutomationDenialKind.GRANT and change.target_id == grant.grant_id
    )
    if affected:
        return _denied_whole_grant(stored, locking)
    if change.kind is AutomationDenialKind.KEY:
        return _denied_single_key(stored, change)
    return EnrollmentGrant(grant=grant, keys=stored.keys)


def _denied_whole_grant(stored: StoredAutomationGrant, locking: bool) -> EnrollmentGrant:
    """Suspend only eligible existing authority and revoke incomplete enrollment."""
    grant, keys = stored.grant, stored.keys
    # Incomplete enrollment can never become active through unlock.
    state = (
        AuthorityState.SUSPENDED
        if locking and grant.state in {AuthorityState.ACTIVE, AuthorityState.SUSPENDED}
        else AuthorityState.REVOKED
    )
    if grant.state is AuthorityState.REVOKED:
        state = AuthorityState.REVOKED
    grant = changed_control_model(grant, state=state, generation=grant.generation + 1)
    keys = tuple(
        changed_control_model(
            item,
            key=changed_control_model(
                item.key,
                state=AuthorityState.SUSPENDED
                if state is AuthorityState.SUSPENDED
                and item.key.state in {AuthorityState.ACTIVE, AuthorityState.SUSPENDED}
                else AuthorityState.REVOKED,
                generation=item.key.generation + 1,
            ),
        )
        for item in keys
    )
    return EnrollmentGrant(grant=grant, keys=keys)


def _denied_single_key(stored: StoredAutomationGrant, change: AutomationDenial) -> EnrollmentGrant:
    """Revoke the exact key and any unattended grant with no remaining key authority."""
    grant, keys = stored.grant, stored.keys
    keys = tuple(
        changed_control_model(
            item, key=changed_control_model(item.key, state=AuthorityState.REVOKED, generation=item.key.generation + 1)
        )
        if item.key.key_id == change.target_id
        else item
        for item in keys
    )
    if grant.unattended and keys and all(item.key.state is AuthorityState.REVOKED for item in keys):
        grant = changed_control_model(grant, state=AuthorityState.REVOKED, generation=grant.generation + 1)
    return EnrollmentGrant(grant=grant, keys=keys)


def denied_enrollment_requests(payload: AutomationControlPayload | None) -> tuple[EnrollmentRecord, ...]:
    """Decline unfinished enrollment while preserving completed records and inventory order."""
    return (
        ()
        if payload is None
        else tuple(
            changed_control_model(item, stage=EnrollmentStage.DECLINED)
            if item.stage is not EnrollmentStage.COMPLETE
            else item
            for item in payload.requests
        )
    )
