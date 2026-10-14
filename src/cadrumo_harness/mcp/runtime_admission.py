"""Exact-profile and exact-lease admission checks for MCP runtime calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from time import monotonic, sleep
from typing import Any, Final
from uuid import UUID

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, ProfileAccessStatus
from cadrumo.application.user_profile.sign_in_refusals import SignInRefusal
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.errors.hierarchy import ActiveProfilePointerError
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.profile_access import status_admits_session
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .protocol_contract import refusal_code, sign_in_refusal_facts
from .surfaces import McpSurface


class McpAdmission(StrEnum):
    """How the session one MCP connection holds was admitted."""

    KEY = "key"
    """Authenticated by an enrolled key the person configured at launch, under the grant approved for it."""
    ATTENDED = "attended"
    """Admitted by the person's own decision under the sign-in they hold; it ends when that sign-in ends."""


NO_SESSION: Final = "none"
"""What a reply's ``session`` says when the connection holds no session."""


@dataclass(frozen=True, slots=True)
class AdmissionDenial:
    """Why the runtime last refused to admit a connection: its code and the sign-in facts it gave.

    It is kept instead of the refusal itself, so a later call answers with
    the same code and facts and holds no frame of the call that was refused.
    """

    code: str
    sign_in: SignInRefusal | None = None

    @classmethod
    def of(cls, error: Exception) -> AdmissionDenial:
        """Keep the public code and sign-in facts of one refused admission."""
        sign_in = error.sign_in if isinstance(error, FrontendRefusedError) else None
        return cls(refusal_code(error), sign_in)

    def facts(self) -> dict[str, Any]:
        """Return the sign-in facts a reply carries beside the code."""
        return sign_in_refusal_facts(self.sign_in)

    def refusal(self) -> FrontendRefusedError:
        """Return a fresh refusal with the code and facts the runtime gave."""
        return FrontendRefusedError(self.code, sign_in=self.sign_in)


def selected_profile_id(*, expected: UUID | None) -> UUID:
    """Return the installation's selected profile, as a profile-bound command resolves it.

    ``expected`` selects nothing. It refuses a selection that differs from it,
    so a connection started for one profile is never moved to another one's
    sign-in by a later selection.
    """
    try:
        selected = resolve_active_bucket_id()
    except ActiveProfilePointerError:
        raise FrontendRefusedError(AccessDenialCode.STORAGE_UNAVAILABLE.value) from None
    if selected is None:
        # No selected profile can have an attendance request from this connection.
        raise FrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
    try:
        profile_id = UUID(selected)
    except ValueError:
        raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value) from None
    if expected is not None and profile_id != expected:
        raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return profile_id


def _require_client_binding(client: FrontendClient, profile_id: UUID) -> UUID:
    if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.EXTERNAL_CLIENT:
        raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return client.session_id


def _require_live_session(status: ProfileAccessStatus, *, at: datetime) -> None:
    if status.denial is not None:
        raise FrontendRefusedError(status.denial.value)
    if status.session_expires_at is None or status.session_expires_at <= at:
        raise FrontendRefusedError(AccessDenialCode.SESSION_EXPIRED.value)


def _require_status_binding(status: ProfileAccessStatus, profile_id: UUID, session_id: UUID) -> None:
    if (
        not status.connected
        or not status.credential_authenticated
        or not status.profile_bound
        or status.profile_id != profile_id
        or status.session_id != session_id
    ):
        raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)


def require_exact_admitted_status(
    client: FrontendClient, *, profile_id: UUID, admission: McpAdmission = McpAdmission.KEY
) -> ProfileAccessStatus:
    """Treat a live, exact MCP lease as the only successful admission witness.

    A key lease must also show its automation grant live. An attended lease
    has no grant, and the runtime bounds it by the held human parent's deadlines.
    """
    session_id = _require_client_binding(client, profile_id)
    status = client.status().status
    at = now()
    _require_live_session(status, at=at)
    keyed = admission is McpAdmission.KEY
    if keyed and not status.grant_valid:
        raise FrontendRefusedError(AccessDenialCode.GRANT_INACTIVE.value)
    _require_status_binding(status, profile_id, session_id)
    if not status_admits_session(
        status, profile_id=profile_id, session_id=session_id, at=at, requires_automation_grant=keyed
    ):
        refusal = AccessDenialCode.GRANT_INACTIVE if keyed else AccessDenialCode.SESSION_INACTIVE
        raise FrontendRefusedError(refusal.value)
    if _require_client_binding(client, profile_id) != session_id:
        raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    return status


ATTENDANCE_WAIT_SECONDS: Final = 90.0
"""How long one call waits for the person to decide an ask before it is answered as refused."""

_ATTENDANCE_POLL_SECONDS: Final = 0.25


def attend_held_sign_in(client: FrontendClient, *, profile_id: UUID) -> ProfileAccessStatus:
    """Ask the person holding the sign-in to admit this connection, and wait for their decision.

    The ask carries no secret and the agent names no credential: the runtime
    shows the person this process as the kernel names it, and only their
    approval of this exact ask admits the connection. A decline, a lapsed ask,
    or no held sign-in at all is the runtime's refusal, raised with its code.
    """
    deadline = monotonic() + ATTENDANCE_WAIT_SECONDS
    reply = client.request_attendance()
    while isinstance(reply, AttendancePending):
        if monotonic() >= deadline:
            raise FrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
        sleep(_ATTENDANCE_POLL_SECONDS)
        reply = client.attendance_status(reply.attendance_id)
    return require_exact_admitted_status(client, profile_id=profile_id, admission=McpAdmission.ATTENDED)


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
