"""Bind automation administration to live human authority and reviewed custody."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import override
from uuid import UUID

from cadrumo.application.user_profile.automation_administration import enrollment_review_digest
from cadrumo.application.user_profile.automation_enrollment import (
    AdministrationFacts,
    EnrollmentCustodyPort,
    EnrollmentRecord,
    EnrollmentRequester,
    ProtectedEnrollmentRecipient,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from ..application.approval_binding import RuntimeApprovalBinding
from ..application.session_authority import ProfileSessionAuthority


@dataclass(frozen=True)
class RuntimeAutomationInventoryOwner:
    """A live authority binding supplied by the authenticated runtime callback."""

    authority: ProfileSessionAuthority
    connection_id: UUID
    session_id: UUID

    def facts(self) -> AdministrationFacts:
        """Reobserve this exact session and its originating native login."""
        return self.authority.human_administration_facts(connection_id=self.connection_id, session_id=self.session_id)

    @contextmanager
    def administration_guard(self) -> Generator[None]:
        """Share the same lifecycle fence as operation execution and disclosure."""
        with self.authority.owner.admission_guard():
            yield


@dataclass(frozen=True)
class RuntimeAutomationAdministrationOwner(RuntimeAutomationInventoryOwner):
    """Bind canonical approval to human facts and a separately owned recipient."""

    recipient_lookup: Callable[[EnrollmentRequester], ProtectedEnrollmentRecipient]
    approval_binding: RuntimeApprovalBinding
    custody: EnrollmentCustodyPort

    def _reviewed_record(self) -> EnrollmentRecord:
        state = self.custody.enrollment_state()
        record = next(
            (item for item in state.requests if item.request_id == self.approval_binding.enrollment_request_id),
            None,
        )
        if (
            state.binding != self.approval_binding.profile_binding
            or record is None
            or record.binding != state.binding
            or not secrets.compare_digest(enrollment_review_digest(record), self.approval_binding.review_digest)
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        return record

    @override
    def facts(self) -> AdministrationFacts:
        """Apply the owner's delegation ceiling to this exact reviewed recipient.

        Ordinary human operation authority keeps its original destination. Only
        this request-bound administration view may delegate its registered
        projection permissions to the recipient whose consent digest was reviewed.
        No permission is copied from the proposal itself.
        """
        with self.administration_guard():
            current = super().facts()
            record = self._reviewed_record()
            permissions = frozenset(
                permission.model_copy(update={"destination_id": record.requester.destination_id})
                for permission in current.profile.scope.disclosures
                if permission.destination_id == current.context.authenticated_client_id
            )
            categories = frozenset(
                grant.model_copy(update={"destination_id": record.requester.destination_id})
                for grant in current.profile.scope.disclosure_categories
                if grant.destination_id == current.context.authenticated_client_id
            )
            scope = current.profile.scope.model_copy(
                update={"disclosures": permissions, "disclosure_categories": categories}
            )
            return current.model_copy(update={"profile": current.profile.model_copy(update={"scope": scope})})

    def requester(self) -> EnrollmentRequester:
        """Derive requester coordinates from the original live human connection."""
        facts = self.facts()
        return EnrollmentRequester(
            runtime_boot_id=facts.context.runtime_boot_id,
            connection_id=self.connection_id,
            client_id=facts.context.authenticated_client_id,
            destination_id=facts.context.authenticated_client_id,
        )

    def recipient(self, requester: EnrollmentRequester) -> ProtectedEnrollmentRecipient:
        """Resolve the exact original requesting client through protected transport."""
        return self.recipient_lookup(requester)
