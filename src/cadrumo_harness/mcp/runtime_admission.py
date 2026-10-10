"""Exact-profile and exact-lease admission checks for MCP runtime calls."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.mcp_surfaces import McpSurface
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.profile_access import status_admits_session
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, ProfileAccessStatus
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.errors.hierarchy import ActiveProfilePointerError
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.core.time.clock import now


class McpAdmission(StrEnum):
    """How the session one MCP connection holds was admitted."""

    SIGN_IN = "sign_in"
    """Resumed from the person's sign-in; it ends when that sign-in ends."""
    KEY = "key"
    """Authenticated by an enrolled key, under the grant approved for it."""


_UNPRESENTED_SIGN_IN_REFUSALS: Final[dict[ProfileSessionRefusalReason, AccessDenialCode]] = {
    # The proof is held by the OS keychain; without it nothing says whether a sign-in is stored.
    ProfileSessionRefusalReason.KEYRING_UNAVAILABLE: AccessDenialCode.CUSTODY_UNAVAILABLE,
}
"""Refusals met before the runtime is asked, as the denial a client is told; any other is an absent sign-in."""


def selected_profile_id(*, expected: UUID | None) -> UUID:
    """Return the installation's selected profile, as a profile-bound command resolves it.

    ``expected`` selects nothing. It refuses a selection that differs from it,
    so a connection started for one profile is never moved to another one's
    sign-in by a later selection.
    """
    try:
        selected = resolve_active_bucket_id()
    except ActiveProfilePointerError:
        raise RuntimeFrontendRefusedError(AccessDenialCode.STORAGE_UNAVAILABLE.value) from None
    if selected is None:
        # No profile is selected, so no sign-in exists that this connection could resume.
        raise RuntimeFrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
    try:
        profile_id = UUID(selected)
    except ValueError:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value) from None
    if expected is not None and profile_id != expected:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return profile_id


def _require_client_binding(client: RuntimeFrontendClient, profile_id: UUID) -> UUID:
    if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.MCP:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return client.session_id


def _require_live_session(status: ProfileAccessStatus, *, at: datetime) -> None:
    if status.denial is not None:
        raise RuntimeFrontendRefusedError(status.denial.value)
    if status.session_expires_at is None or status.session_expires_at <= at:
        raise RuntimeFrontendRefusedError(AccessDenialCode.SESSION_EXPIRED.value)


def _require_status_binding(status: ProfileAccessStatus, profile_id: UUID, session_id: UUID) -> None:
    if (
        not status.connected
        or not status.credential_authenticated
        or not status.profile_bound
        or status.profile_id != profile_id
        or status.session_id != session_id
    ):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)


def require_exact_admitted_status(
    client: RuntimeFrontendClient, *, profile_id: UUID, admission: McpAdmission = McpAdmission.KEY
) -> ProfileAccessStatus:
    """Treat a live, exact MCP lease as the only successful admission witness.

    A key lease must also show its automation grant live. A lease resumed from
    the person's sign-in has no grant, and the runtime bounds it by the
    sign-in's own deadlines.
    """
    session_id = _require_client_binding(client, profile_id)
    status = client.status().status
    at = now()
    _require_live_session(status, at=at)
    keyed = admission is McpAdmission.KEY
    if keyed and not status.grant_valid:
        raise RuntimeFrontendRefusedError(AccessDenialCode.GRANT_INACTIVE.value)
    _require_status_binding(status, profile_id, session_id)
    if not status_admits_session(
        status, profile_id=profile_id, session_id=session_id, at=at, requires_automation_grant=keyed
    ):
        refusal = AccessDenialCode.GRANT_INACTIVE if keyed else AccessDenialCode.SESSION_INACTIVE
        raise RuntimeFrontendRefusedError(refusal.value)
    if _require_client_binding(client, profile_id) != session_id:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return status


def resume_shared_sign_in(client: RuntimeFrontendClient, *, profile_id: UUID) -> ProfileAccessStatus:
    """Ask the runtime, once, to resume the person's sign-in on this connection.

    The client presents the stored proof and the runtime alone decides; its
    refusal is raised with the code it gave. Where there is no proof to
    present the runtime is not asked, and the refusal carries the code the
    runtime gives a sign-in that is absent. No password travels here.
    """
    try:
        client.resume_receipt()
    except ProfileReceiptRefusedError as refused:
        answered = refused.__cause__
        if isinstance(answered, RuntimeFrontendRefusedError):
            raise answered from None
        denial = _UNPRESENTED_SIGN_IN_REFUSALS.get(refused.reason, AccessDenialCode.AUTHENTICATION_REQUIRED)
        raise RuntimeFrontendRefusedError(denial.value) from None
    return require_exact_admitted_status(client, profile_id=profile_id, admission=McpAdmission.SIGN_IN)


def status_on_surface(status: ProfileAccessStatus, surface: McpSurface) -> ProfileAccessStatus:
    """Report the scope a status carries as the connection's surface leaves it.

    The runtime holds the connection to its surface at every access, so a
    scope reported whole would name operations and a commit door the
    connection is refused. Reporting less grants and enforces nothing.
    """
    if not surface.narrows:
        return status
    scope = status.effective_scope
    narrowed = scope.model_copy(
        update={
            "operations": frozenset(item for item in scope.operations if surface.admits(item)),
            "actions": scope.actions if surface.changes_records else scope.actions - {AccessAction.COMMIT},
        }
    )
    return status.model_copy(update={"effective_scope": narrowed})
