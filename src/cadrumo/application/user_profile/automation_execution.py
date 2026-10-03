"""Async execution boundary for canonical automation administration.

The registered executor owns sequencing, cancellation and result persistence.
The owning runtime supplies the phases through a protected worker proxy.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import SecretBytes

from ...core.identity.digest import ContentDigest
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


__all__ = [
    "AutomationAdministrationExecution",
    "AutomationApprovalExecution",
]
