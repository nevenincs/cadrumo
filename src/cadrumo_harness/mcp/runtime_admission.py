"""Exact-profile and exact-lease admission checks for MCP runtime calls."""

from __future__ import annotations

from uuid import UUID

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, ProfileAccessStatus
from cadrumo.core.time.clock import now


def _require_client_binding(client: RuntimeFrontendClient, profile_id: UUID) -> UUID:
    if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.MCP:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return client.session_id


def _require_live_grant(status: ProfileAccessStatus) -> None:
    if status.denial is not None:
        raise RuntimeFrontendRefusedError(status.denial.value)
    if status.session_expires_at is None or status.session_expires_at <= now():
        raise RuntimeFrontendRefusedError(AccessDenialCode.SESSION_EXPIRED.value)
    if not status.grant_valid:
        raise RuntimeFrontendRefusedError(AccessDenialCode.GRANT_INACTIVE.value)


def _require_status_binding(status: ProfileAccessStatus, profile_id: UUID, session_id: UUID) -> None:
    if (
        not status.connected
        or not status.credential_authenticated
        or not status.profile_bound
        or status.profile_id != profile_id
        or status.session_id != session_id
    ):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)


def require_exact_admitted_status(client: RuntimeFrontendClient, *, profile_id: UUID) -> ProfileAccessStatus:
    """Treat a live, exact MCP lease as the only successful admission witness."""
    session_id = _require_client_binding(client, profile_id)
    status = client.status().status
    _require_live_grant(status)
    _require_status_binding(status, profile_id, session_id)
    return status
