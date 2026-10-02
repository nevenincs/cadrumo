"""Safe typed CLI envelopes for runtime-owned profile access management."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ....application.operations.models import OperationId
from ....application.user_profile.access_contracts import (
    SessionKind,
    SessionState,
)
from ....application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    AutomationReceiptProjection,
    AutomationReviewProjection,
    AutomationScopeProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from ....application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ....application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from ....core.json_contract import OutputSchema
from ....core.operations import OperationEffect


class RuntimeSessionPayload(OutputSchema):
    """Allowlisted current-session metadata with a portable scope projection."""

    session_id: UUID
    profile_id: UUID
    client_id: UUID
    parent_session_id: UUID | None
    grant_id: UUID | None
    key_id: UUID | None
    kind: SessionKind
    state: SessionState
    scope: AutomationScopeProjection
    expires_at: datetime
    remaining_seconds: int


class ConfigProfileSessionsResult(OutputSchema):
    """Authorized session inventory for one exact profile."""

    profile_id: UUID
    sessions: tuple[RuntimeSessionPayload, ...]


class ConfigProfileAutomationListResult(OutputSchema):
    """One authorized, secret-free inventory and its settled operation identity."""

    profile_id: UUID
    operation_id: OperationId
    inventory: AutomationInventoryProjection


class ConfigProfileAutomationInspectResult(OutputSchema):
    """One exact review read from the canonical public inventory."""

    profile_id: UUID
    inventory_operation_id: OperationId
    review: AutomationReviewProjection


class ConfigProfileAutomationCreateResult(OutputSchema):
    """First requester review and terminal state, with verified native reference."""

    profile_id: UUID
    submitted: AutomationReceiptProjection
    terminal: AutomationReceiptProjection
    credential_reference: UUID | None

    @model_validator(mode="after")
    def _exact_terminal(self) -> ConfigProfileAutomationCreateResult:
        if (
            not _same_request(self.profile_id, self.submitted, self.terminal)
            or (self.terminal.stage is EnrollmentStage.DECLINED and self.credential_reference is not None)
            or (
                self.terminal.stage is EnrollmentStage.COMPLETE
                and (self.terminal.key_id is None or self.credential_reference != self.terminal.credential_reference)
            )
        ):
            raise ValueError("automation creation has inconsistent terminal identity")
        return self


class ConfigProfileAutomationChangeResult(OutputSchema):
    """One reviewed own-grant change with only a newly verified key reference."""

    profile_id: UUID
    kind: EnrollmentKind
    submitted: AutomationReceiptProjection
    terminal: AutomationReceiptProjection
    credential_reference: UUID | None

    @model_validator(mode="after")
    def _exact_terminal(self) -> ConfigProfileAutomationChangeResult:
        if self.kind not in {
            EnrollmentKind.ROTATE,
            EnrollmentKind.RENEW,
            EnrollmentKind.CHANGE_SCOPE,
        } or not _same_request(self.profile_id, self.submitted, self.terminal):
            raise ValueError("automation change has inconsistent request identity")
        if self.terminal.stage is EnrollmentStage.DECLINED:
            if self.credential_reference is not None:
                raise ValueError("declined automation change cannot yield a credential")
        elif self.kind is EnrollmentKind.ROTATE:
            if self.terminal.key_id is None or self.credential_reference != self.terminal.credential_reference:
                raise ValueError("rotation lacks its verified candidate")
        elif (
            self.terminal.key_id is not None
            or self.terminal.credential_reference is not None
            or (self.credential_reference is not None)
        ):
            raise ValueError("nonrotating change cannot yield a new credential")
        return self


def _same_request(
    profile_id: UUID, submitted: AutomationReceiptProjection, terminal: AutomationReceiptProjection
) -> bool:
    return (
        submitted.profile_id == profile_id
        and terminal.profile_id == profile_id
        and submitted.request_id == terminal.request_id
        and submitted.review_digest == terminal.review_digest
        and submitted.grant_id == terminal.grant_id
        and submitted.stage is EnrollmentStage.REQUESTED
        and terminal.stage in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}
    )


class ConfigProfileAutomationDecisionResult(OutputSchema):
    """Settled reviewed decision with no approval proof or key material."""

    profile_id: UUID
    inventory_operation_id: OperationId
    operation_id: OperationId
    decision: Literal["approve", "decline"]
    effect: OperationEffect
    receipt: AutomationReceiptProjection


class ConfigProfileAutomationDenyResult(OutputSchema):
    """A durable reduction receipt, without claiming native cleanup completed."""

    profile_id: UUID
    kind: AutomationDenialKind
    target_id: UUID | None
    receipt: AutomationDenialReceipt


class ConfigProfileLockResult(OutputSchema):
    """Distinguish current, selected, and global authority reductions."""

    profile_id: UUID
    scope: Literal["current", "selected", "profile"]
    target_session_id: UUID | None
    session_ids: tuple[UUID, ...]
    denial: AutomationDenialReceipt | None


class ConfigProfileResumeResult(OutputSchema):
    """Exact selected grants reactivated under a fresh password proof."""

    profile_id: UUID
    receipt: AutomationResumeReceipt


__all__ = [
    "ConfigProfileAutomationChangeResult",
    "ConfigProfileAutomationCreateResult",
    "ConfigProfileAutomationDecisionResult",
    "ConfigProfileAutomationDenyResult",
    "ConfigProfileAutomationInspectResult",
    "ConfigProfileAutomationListResult",
    "ConfigProfileLockResult",
    "ConfigProfileResumeResult",
    "ConfigProfileSessionsResult",
    "RuntimeSessionPayload",
]
