"""Async execution boundary for canonical automation administration.

The registered executor owns sequencing, cancellation and result persistence.
The local adapter dispatches the existing blocking service off its event loop;
an owned native runtime may instead provide a protected phase proxy.
"""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

from pydantic import SecretBytes

from ...core.identity.digest import ContentDigest
from .automation_administration_service import AutomationAdministrationService
from .automation_approval_session import ApprovalSession
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import AutomationInventory, EnrollmentProposal, EnrollmentTransition


class AutomationApprovalExecution(Protocol):
    """One caller-owned approval journey; close follows every completed phase."""

    async def prepare(self, password: SecretBytes) -> None:
        """Prove the current profile password outside COMMIT."""
        ...

    async def commit_review(self) -> EnrollmentTransition | None:
        """Publish a simple reviewed change or enter the candidate journey."""
        ...

    async def inspect_recipient(self) -> bool:
        """Check exact recipient possession outside COMMIT."""
        ...

    async def publish_candidate(self) -> EnrollmentTransition:
        """Publish an unusable candidate under the caller's COMMIT guard."""
        ...

    async def deliver_and_verify(self) -> None:
        """Deliver and verify client possession outside COMMIT."""
        ...

    async def activate(self) -> EnrollmentTransition:
        """Activate the verified candidate under the caller's COMMIT guard."""
        ...

    async def close(self) -> None:
        """Release proof and delivery references after all phase calls settle."""
        ...


class AutomationAdministrationExecution(Protocol):
    """Typed administration phases supplied to the registered executor."""

    async def require_profile(self, profile_id: UUID) -> None:
        """Refuse a service bound to another current profile."""
        ...

    async def request(self, request_id: UUID, proposal: EnrollmentProposal) -> EnrollmentTransition:
        """Publish or identify one exact enrollment request."""
        ...

    async def decline(self, request_id: UUID, *, review_digest: ContentDigest) -> EnrollmentTransition:
        """Decline one reviewed request or identify its existing decline."""
        ...

    async def inventory(self) -> AutomationInventory:
        """Read human-authorized protected administration state."""
        ...

    def approval(self, request_id: UUID, *, review_digest: ContentDigest) -> AutomationApprovalExecution:
        """Construct caller-owned approval memory before cancellable work."""
        ...


class _ThreadedAutomationApproval:
    """Dispatch the one existing ApprovalSession's blocking phases."""

    __slots__ = ("_session",)

    def __init__(self, session: ApprovalSession) -> None:
        """Keep the caller-created session until an explicit close."""
        self._session = session

    async def prepare(self, password: SecretBytes) -> None:
        """Prove the supplied password through the existing session."""
        await asyncio.to_thread(self._session.prepare, password)

    async def commit_review(self) -> EnrollmentTransition | None:
        """Run the session's reviewed publication phase."""
        return await asyncio.to_thread(self._session.commit_review)

    async def inspect_recipient(self) -> bool:
        """Ask the original recipient whether a candidate is needed."""
        return await asyncio.to_thread(self._session.inspect_recipient)

    async def publish_candidate(self) -> EnrollmentTransition:
        """Publish the inactive candidate through the canonical service."""
        return await asyncio.to_thread(self._session.publish_candidate)

    async def deliver_and_verify(self) -> None:
        """Complete protected recipient delivery and possession proof."""
        await asyncio.to_thread(self._session.deliver_and_verify)

    async def activate(self) -> EnrollmentTransition:
        """Activate only the recipient-proven candidate."""
        return await asyncio.to_thread(self._session.activate)

    async def close(self) -> None:
        """Drop every proof and delivery reference after phase settlement."""
        await asyncio.to_thread(self._session.close)


class ThreadedAutomationAdministration:
    """Run the canonical synchronous service off the operation event loop."""

    __slots__ = ("_service",)

    def __init__(self, service: AutomationAdministrationService) -> None:
        """Bind one real application service; no approval starts here."""
        self._service = service

    async def require_profile(self, profile_id: UUID) -> None:
        """Check the service's current exact-profile binding off loop."""

        def check() -> None:
            with self._service.owner.administration_guard():
                if self._service.owner.facts().profile.binding.profile_id != profile_id:
                    raise AutomationCustodyError(AutomationCustodyCode.INVALID)

        await asyncio.to_thread(check)

    async def request(self, request_id: UUID, proposal: EnrollmentProposal) -> EnrollmentTransition:
        """Run the canonical request publication without duplicating policy."""
        return await asyncio.to_thread(self._service.request, request_id, proposal)

    async def decline(self, request_id: UUID, *, review_digest: ContentDigest) -> EnrollmentTransition:
        """Run the canonical decline publication off loop."""
        return await asyncio.to_thread(self._service.decline, request_id, review_digest=review_digest)

    async def inventory(self) -> AutomationInventory:
        """Read protected inventory through the existing service."""
        return await asyncio.to_thread(self._service.inventory)

    def approval(self, request_id: UUID, *, review_digest: ContentDigest) -> AutomationApprovalExecution:
        """Construct the caller-owned session before any cancellable phase."""
        return _ThreadedAutomationApproval(self._service.approval(request_id, review_digest=review_digest))


__all__ = [
    "AutomationAdministrationExecution",
    "AutomationApprovalExecution",
    "ThreadedAutomationAdministration",
]
