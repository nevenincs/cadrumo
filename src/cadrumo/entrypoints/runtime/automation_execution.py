"""Worker execution of canonical administration through exact parent authority."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...application.operations.models import OperationIdentity
from ...application.runtime.approval_binding import RuntimeApprovalBinding
from ...application.runtime.worker_enrollment import WorkerApprovalRequest
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import (
    AutomationInventory,
    EnrollmentProposal,
    EnrollmentTransition,
)
from ...application.user_profile.automation_execution import AutomationApprovalExecution
from ...core.identity.digest import ContentDigest
from .operation_authority import ProfileWorkerOperationAuthority


class WorkerAutomationAdministration:
    """Use the original operation binding; the worker never opens the control store."""

    def __init__(
        self, authority: ProfileWorkerOperationAuthority, identity: OperationIdentity, profile_id: UUID
    ) -> None:
        """Retain trusted worker composition coordinates without issuing a parent call."""
        self._authority, self._identity, self._profile_id = authority, identity, profile_id

    async def require_profile(self, profile_id: UUID) -> None:
        """Reject a changed target before any administration phase."""
        if profile_id != self._profile_id or profile_id != self._authority.custody.identity.binding.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    async def inventory(self) -> AutomationInventory:
        """Read through the existing parent human-inventory boundary."""
        return await self._authority.automation_inventory(self._identity, self._profile_id)

    async def request(self, request_id: UUID, proposal: EnrollmentProposal) -> EnrollmentTransition:
        """Refuse until the protected request control door is composed."""
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    async def decline(self, request_id: UUID, *, review_digest: ContentDigest) -> EnrollmentTransition:
        """Decline only through this human invocation's exact held COMMIT lease."""
        binding = self._authority.approval_binding(
            self._identity, profile_id=self._profile_id, request_id=request_id, review_digest=review_digest
        )
        result = await self._authority.publish_approval(self._identity, binding, "decline")
        if result is None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return result

    def approval(self, request_id: UUID, *, review_digest: ContentDigest) -> AutomationApprovalExecution:
        """Construct local ownership before the first cancellable proof exchange."""
        binding = self._authority.approval_binding(
            self._identity, profile_id=self._profile_id, request_id=request_id, review_digest=review_digest
        )
        return WorkerAutomationApproval(self._authority, self._identity, binding)


class WorkerAutomationApproval:
    """An operation-owned proxy; only parent memory retains proof and candidates."""

    def __init__(
        self, authority: ProfileWorkerOperationAuthority, identity: OperationIdentity, binding: RuntimeApprovalBinding
    ) -> None:
        """Keep cleanup coordinates before any native allocation may succeed."""
        self._authority, self._identity, self._binding = authority, identity, binding
        self._cleanup: WorkerApprovalRequest | None = None
        self._closed = False

    async def _phase(
        self, phase: Literal["prepare", "inspect_recipient", "deliver_and_verify"], password: SecretBytes | None = None
    ) -> bool | None:
        if self._closed:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        request = self._authority.approval_request(self._identity, self._binding, phase)
        # Keep cleanup even if the prepare reply is lost after parent allocation.
        self._cleanup = request.model_copy(update={"phase": "close", "request_id": uuid4()})
        return await self._authority.approval_phase(request, password)

    async def prepare(self, password: SecretBytes) -> None:
        """Submit the protected password after fresh parent authority preflight."""
        await self._phase("prepare", password)

    async def commit_review(self) -> EnrollmentTransition | None:
        """Publish review through the current task's exact held COMMIT lease."""
        return await self._authority.publish_approval(self._identity, self._binding, "commit_review")

    async def inspect_recipient(self) -> bool:
        """Ask the actual recipient outside the publication fence."""
        result = await self._phase("inspect_recipient")
        if result is None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return result

    async def publish_candidate(self) -> EnrollmentTransition:
        """Publish only an inactive candidate under the task-owned COMMIT lease."""
        result = await self._authority.publish_approval(self._identity, self._binding, "publish_candidate")
        if result is None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return result

    async def deliver_and_verify(self) -> None:
        """Complete protected client delivery and possession outside COMMIT."""
        await self._phase("deliver_and_verify")

    async def activate(self) -> EnrollmentTransition:
        """Publish proven possession under fresh task-owned COMMIT authority."""
        result = await self._authority.publish_approval(self._identity, self._binding, "activate")
        if result is None:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        return result

    async def close(self) -> None:
        """Retire the parent proof even after expiry, disconnect or a lost prepare reply."""
        self._closed = True
        if self._cleanup is not None:
            await self._authority.approval_phase(self._cleanup)
            self._cleanup = None
