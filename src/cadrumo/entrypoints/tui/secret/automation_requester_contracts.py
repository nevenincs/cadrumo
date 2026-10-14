"""Typed proposal data and safe outcome returned by the requester screen."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.automation_enrollment import EnrollmentKind, EnrollmentProposal, EnrollmentStage
from ....core.period import Period

type RequesterClientOpener = Callable[[UUID], Awaitable[RuntimeFrontendClient]]
type FreshCredentialClientOpener = Callable[[UUID, UUID, float], RuntimeFrontendClient]


@dataclass(frozen=True, slots=True)
class AutomationRequestOutcome:
    """Safe receipt identity after a completed or uncertain request."""

    request_id: UUID | None
    review_digest: str | None
    stage: EnrollmentStage | None
    credential_reference: UUID | None
    uncertain: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class ProposalDraft:
    """Validated requester fields before server destination binding."""

    kind: EnrollmentKind
    operations: frozenset[str]
    actions: frozenset[AccessAction]
    disclosures: frozenset[tuple[str, DisclosureCategory]]
    periods: frozenset[Period] | None
    period_independent: bool
    delegation: bool
    expires_at: datetime
    key_expires_at: datetime | None
    unattended: bool
    os_lock: bool
    target_grant_id: UUID | None
    target_key_id: UUID | None
    credential_reference: UUID | None

    def proposal(self, destination_id: UUID) -> EnrollmentProposal:
        """Bind disclosed schemas to the server-minted destination, not UI input."""
        scope = AccessScope(
            operations=frozenset(self.operations),
            actions=self.actions,
            disclosures=frozenset(
                DisclosurePermission(destination_id=destination_id, projection_id=schema, category=category)
                for schema, category in self.disclosures
            ),
            periods=self.periods,
            allow_period_independent=self.period_independent,
            allow_delegation=self.delegation,
        )
        return EnrollmentProposal(
            kind=self.kind,
            scope=scope,
            expires_at=self.expires_at,
            key_expires_at=self.key_expires_at,
            unattended=self.unattended,
            allow_os_lock=self.os_lock,
            target_grant_id=self.target_grant_id,
            target_key_id=self.target_key_id,
        )
