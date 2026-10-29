"""Exact-session frontend operations over a verified runtime connection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from cadrumo.application.operations.secret_submission import OperationSecretRequirement
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt

from ..contracts.access_management import (
    AutomationDenied,
    AutomationDeny,
    SessionInventory,
    SessionInventoryReply,
)
from ..contracts.access_vocabulary import DisclosurePage, DisclosurePageRequest
from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.deadline_budget import (
    MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    deadline_after,
)
from ..contracts.operation_access import OperationAcknowledged, OperationSecret
from ..contracts.presentation import PresentationDelivered, PresentationRequest
from ..contracts.profile_access import (
    ProfileDisclosurePage,
    ProfileDisclosurePageRequest,
    ProfileStatus,
    SessionRequest,
    SessionsLocked,
)
from ..contracts.profile_selection import ActiveProfileReply, ActiveProfileRequest
from ..contracts.sign_in import SignInStatusReply, SignInStatusRequest
from .frontend_client_contracts import FrontendRefusedError, frontend_refusal
from .frontend_custody_client import FrontendCustodyClient

if TYPE_CHECKING:
    pass


class FrontendSessionClient(FrontendCustodyClient):
    """Manage and observe one verified frontend session."""

    def submit_secret(
        self,
        requirement: OperationSecretRequirement,
        secret: bytearray,
        *,
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    ) -> OperationAcknowledged:
        """Consume a secret through its exact operation's protected handoff."""
        try:
            return self._reply(
                self._connection.operation_secret(
                    OperationSecret(
                        request_id=uuid4(),
                        profile_id=self.profile_id,
                        session_id=self._session(),
                        requirement=requirement,
                    ),
                    secret,
                    deadline=deadline_after(timeout),
                ),
                OperationAcknowledged,
            )
        finally:
            secret[:] = bytes(len(secret))

    def _session_status(
        self, action: Literal["session_status", "session_refresh", "session_activity"], *, timeout: float
    ) -> ProfileStatus:
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                SessionRequest(action=action, request_id=uuid4(), profile_id=self.profile_id, session_id=session_id),
                deadline=deadline_after(timeout),
            ),
            ProfileStatus,
        )
        if reply.status.session_id not in (None, session_id) or reply.status.profile_id not in (
            None,
            self.profile_id,
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply

    def status(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> ProfileStatus:
        """Recheck the current connection-bound session without refreshing it."""
        return self._session_status("session_status", timeout=timeout)

    def note_activity(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> ProfileStatus:
        """Report explicit person input; never call from polling or automation."""
        reply = self._session_status("session_activity", timeout=timeout)
        if reply.status.denial is not None:
            raise frontend_refusal(
                reply.status.denial.value, recovery_remaining_seconds=reply.status.recovery_remaining_seconds
            )
        return reply

    def disclosure_page(
        self, request: DisclosurePageRequest, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> DisclosurePage:
        """Read one page of the disclosures this session's status counts."""
        reply = self._reply(
            self._connection.disclosure_page(
                ProfileDisclosurePageRequest(
                    request_id=uuid4(), profile_id=self.profile_id, session_id=self._session(), page=request
                ),
                deadline=deadline_after(timeout),
            ),
            ProfileDisclosurePage,
        )
        if reply.page.offset != request.offset or request.expected_digest not in (None, reply.page.disclosure_digest):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply.page

    def sign_in_status(
        self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS, watch: bool = False
    ) -> SignInStatusReply:
        """Observe shared presence without borrowing proof or authenticating this connection."""
        return self._reply(
            self._connection.sign_in_status(
                SignInStatusRequest(request_id=uuid4(), profile_id=self.profile_id, watch=watch),
                deadline=deadline_after(timeout),
            ),
            SignInStatusReply,
        )

    def active_profile(
        self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS, watch: bool = False
    ) -> ActiveProfileReply:
        """Ask which profile is selected and which holds the live sign-in, without authenticating this connection."""
        return self._reply(
            self._connection.active_profile(
                ActiveProfileRequest(request_id=uuid4(), watch=watch), deadline=deadline_after(timeout)
            ),
            ActiveProfileReply,
        )

    def present_destination(
        self,
        destination: str,
        params: Mapping[str, str] | None = None,
        *,
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    ) -> PresentationDelivered:
        """Ask the person's own signed-in TUI on this profile to show register view `destination`."""
        reply = self._reply(
            self._connection.present(
                PresentationRequest(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    destination=destination,
                    params=dict(params or {}),
                ),
                deadline=deadline_after(timeout),
            ),
            PresentationDelivered,
        )
        if reply.destination != destination or reply.params != dict(params or {}):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply

    def refresh_api_key(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> ProfileStatus:
        """Explicitly renew this connection's API-key lease under current authority."""
        reply = self._session_status("session_refresh", timeout=timeout)
        status = reply.status
        if status.denial is not None:
            raise FrontendRefusedError(status.denial.value)
        if (
            not status.connected
            or not status.credential_authenticated
            or not status.profile_bound
            or status.profile_id != self.profile_id
            or status.session_id != self._session()
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply

    def lock(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> SessionsLocked:
        """Retire this lease through the runtime's own-session lock door."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                SessionRequest(
                    action="session_lock", request_id=uuid4(), profile_id=self.profile_id, session_id=session_id
                ),
                deadline=deadline_after(timeout),
            ),
            SessionsLocked,
        )
        if session_id not in reply.session_ids:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._session_id = None
        return reply

    def revoke_session(
        self, target_session_id: UUID, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> SessionsLocked:
        """Request an explicit session cascade; the runtime requires human authority."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                SessionRequest(
                    action="session_lock",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=session_id,
                    target_session_id=target_session_id,
                ),
                deadline=deadline_after(timeout),
            ),
            SessionsLocked,
        )
        if session_id in reply.session_ids:
            self._session_id = None
        return reply

    def sessions(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> tuple[PublicAccessSession, ...]:
        """Read only this session's authorized exact-profile public inventory."""
        request = SessionInventory(request_id=uuid4(), profile_id=self.profile_id, session_id=self._session())
        reply = self._reply(
            self._connection.session_inventory(request, deadline=deadline_after(timeout)), SessionInventoryReply
        )
        return reply.sessions

    def deny_automation(
        self,
        kind: AutomationDenialKind,
        *,
        target_id: UUID | None = None,
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    ) -> AutomationDenialReceipt:
        """Request a durable authority reduction under this exact current session."""
        request = AutomationDeny(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self._session(),
            kind=kind,
            target_id=target_id,
        )
        reply = self._reply(
            self._connection.deny_automation(request, deadline=deadline_after(timeout)), AutomationDenied
        )
        if kind is AutomationDenialKind.PROFILE_LOCK:
            self._session_id = None
        return reply.receipt
