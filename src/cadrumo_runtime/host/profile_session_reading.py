"""Pure predicates and presentation event projections for profile sessions."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import TypeGuard
from uuid import UUID

from cadrumo.application.user_profile.automation_custody_port import AutomationCustodySnapshot
from cadrumo_client.contracts.access_refusals import AccessDenied
from cadrumo_client.contracts.access_vocabulary import AuthorityState
from cadrumo_client.contracts.presentation import PresentationRequest
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.session_events import PresentationRequested

from .profile_connection import ProfileConnection


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


def presentation_events(
    boot: UUID, connection: ProfileConnection, request: PresentationRequest, connections: Iterable[ProfileConnection]
) -> tuple[PresentationRequested, ...]:
    """Project eligible presentation recipients in their input order."""
    recipients = tuple(
        PresentationRequested(
            runtime_boot_id=boot,
            connection_id=recipient.context.connection_id,
            profile_id=recipient.profile_id,
            session_id=recipient.session_id,
            destination=request.destination,
            params=request.params,
        )
        for recipient in connections
        if recipient.context.presentation
        and recipient.profile_id == connection.profile_id
        and recipient.session_id is not None
        and recipient.login.login_id == connection.login.login_id
    )
    return recipients
