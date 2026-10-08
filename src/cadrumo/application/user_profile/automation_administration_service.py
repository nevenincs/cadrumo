"""Canonical service for request-bound automation administration."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...core.identity.digest import ContentDigest
from .access_administration import AccessAdministrationAction
from .access_contracts import ACCESS_LEASE_MAXIMUM
from .access_policy import scope_is_subset
from .automation_administration import (
    authorize_enrollment,
    enrollment_receipt,
    find_enrollment,
    inspect_automation_inventory,
    replace_enrollment_model,
    require_enrollment_review,
    target_enrollment_grant,
    updated_enrollment_state,
    validate_enrollment_state,
)
from .automation_approval_session import ApprovalSession
from .automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .automation_enrollment import (
    AdministrationFacts,
    AutomationAdministrationOwner,
    AutomationInventory,
    AutomationKeyIssuer,
    EnrollmentControlState,
    EnrollmentCustodyPort,
    EnrollmentProposal,
    EnrollmentRecord,
    EnrollmentRequester,
    EnrollmentStage,
    EnrollmentTransition,
)


def _requester_matches_context(requester: EnrollmentRequester, facts: AdministrationFacts) -> bool:
    return (
        requester.runtime_boot_id == facts.context.runtime_boot_id
        and requester.connection_id == facts.context.connection_id
        and requester.client_id == facts.context.authenticated_client_id
    )


def _existing_request_transition(
    state: EnrollmentControlState,
    request_id: UUID,
    proposal: EnrollmentProposal,
    requester: EnrollmentRequester,
) -> EnrollmentTransition | None:
    old = next((item for item in state.requests if item.request_id == request_id), None)
    if old is None:
        return None
    if old.proposal != proposal or old.requester != requester:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    return EnrollmentTransition(receipt=enrollment_receipt(old), published=False)


def _proposal_is_allowed(
    proposal: EnrollmentProposal, facts: AdministrationFacts, requester: EnrollmentRequester
) -> bool:
    return (
        scope_is_subset(proposal.scope, facts.profile.scope)
        and proposal.expires_at > facts.context.now
        and (proposal.key_expires_at is None or proposal.key_expires_at > facts.context.now)
        and all(item.destination_id == requester.destination_id for item in proposal.scope.disclosures)
    )


class AutomationAdministrationService:
    """One profile's administration, with explicit current owner and recipient ports."""

    def __init__(
        self,
        *,
        custody: EnrollmentCustodyPort,
        owner: AutomationAdministrationOwner,
        issuer: AutomationKeyIssuer,
        storage_root: Path,
    ) -> None:
        """Compose trusted dependencies; never infer authority from active selection."""
        self.custody, self.owner, self.issuer, self.storage_root = custody, owner, issuer, storage_root

    def _state(self) -> tuple[EnrollmentControlState, AdministrationFacts]:
        return validate_enrollment_state(self.custody, self.owner, require_enabled=True)

    def request(self, request_id: UUID, proposal: EnrollmentProposal) -> EnrollmentTransition:
        """Create an inactive exact-connection request; repeated IDs cannot retarget."""
        with self.owner.administration_guard():
            state, facts = self._state()
            requester = self.owner.requester()
            if not _requester_matches_context(requester, facts):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            existing = _existing_request_transition(state, request_id, proposal, requester)
            if existing is not None:
                return existing
            if not _proposal_is_allowed(proposal, facts, requester):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            record = EnrollmentRecord(
                request_id=request_id,
                binding=state.binding,
                requester=requester,
                proposal=proposal,
                created_at=facts.context.now,
                expires_at=facts.context.now + ACCESS_LEASE_MAXIMUM,
                stage=EnrollmentStage.REQUESTED,
                grant_id=proposal.target_grant_id or uuid4(),
            )
            target_enrollment_grant(state, record)
            self.custody.publish_enrollment(replace_enrollment_model(state, requests=(*state.requests, record)))
            return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)

    def approval(self, request_id: UUID, *, review_digest: ContentDigest) -> ApprovalSession:
        """Create one caller-owned approval journey before any cancellable work."""
        return ApprovalSession(self, request_id=request_id, review_digest=review_digest)

    def approve(self, request_id: UUID, *, review_digest: ContentDigest, password: SecretBytes) -> EnrollmentTransition:
        """Complete the same staged approval journey for direct application callers."""
        session = self.approval(request_id, review_digest=review_digest)
        try:
            session.prepare(password)
            completed = session.commit_review()
            if completed is not None:
                return completed
            if session.inspect_recipient():
                session.publish_candidate()
            session.deliver_and_verify()
            return session.activate()
        finally:
            session.close()

    def decline(self, request_id: UUID, *, review_digest: ContentDigest) -> EnrollmentTransition:
        """End a pending request; a declined candidate remains unusable."""
        with self.owner.administration_guard():
            state, facts = self._state()
            record = find_enrollment(state, request_id)
            require_enrollment_review(record, review_digest)
            authorize_enrollment(record, AccessAdministrationAction.DECLINE, facts)
            if record.stage is EnrollmentStage.DECLINED:
                return EnrollmentTransition(receipt=enrollment_receipt(record), published=False)
            if record.stage is EnrollmentStage.COMPLETE:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            record = replace_enrollment_model(record, stage=EnrollmentStage.DECLINED)
            self.custody.publish_enrollment(updated_enrollment_state(state, record))
            return EnrollmentTransition(receipt=enrollment_receipt(record), published=True)

    def inventory(self) -> AutomationInventory:
        """Recheck human authority before releasing grant or exact consent details."""
        return inspect_automation_inventory(custody=self.custody, owner=self.owner)
