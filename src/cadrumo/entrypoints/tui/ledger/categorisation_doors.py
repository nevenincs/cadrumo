"""Injected doors to the registered categorisation operations of one admitted profile.

Every plain operation is reached through one shape: the profile the door was
admitted for, and one awaited request that returns the operation's own public
result. The two review operations pause for the operator's decision, so their
door hands back the submitted operation for the operation modal to drive and
reads the settled result afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from ....application.ledger.allocate_operation import LedgerAllocateOperationResult, LedgerAllocateRequest
from ....application.ledger.bulk_classify_operation import LedgerBulkClassifyProjection, LedgerBulkClassifyRequest
from ....application.ledger.counterparty_operation import LedgerCounterpartyRequest, LedgerCounterpartyResult
from ....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ....application.ledger.llm_diagnostics_operation import (
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from ....application.ledger.llm_review_contracts import LedgerLlmReviewRequest
from ....application.ledger.llm_review_results import LedgerLlmOperationResult
from ....application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest, LedgerOperatorIvaResult
from ....application.ledger.participation_operation import LedgerParticipationProjection, LedgerParticipationRequest
from ....application.ledger.participation_rebuild_operation import (
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
)
from ....application.ledger.ratios_contracts import (
    LedgerRatiosEligibleProjection,
    LedgerRatiosEligibleRequest,
    LedgerRatiosListProjection,
    LedgerRatiosListRequest,
    LedgerRatiosSetProjection,
    LedgerRatiosSetRequest,
    LedgerRatiosUnsetProjection,
    LedgerRatiosUnsetRequest,
    LedgerRatiosValidateProjection,
    LedgerRatiosValidateRequest,
)
from ....application.ledger.rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
)
from ....application.ledger.split_operation import LedgerSplitOperationResult, LedgerSplitRequest
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ..operations.controller_port import OperationControllerPort


class LedgerOperationDoorV1[RequestT: BaseModel, ResultT: BaseModel](Protocol):
    """Injected door to one registered operation of one admitted profile."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def __call__(self, request: RequestT, /) -> ResultT:
        """Submit one request and return its receipt-correlated public result."""
        ...


type LedgerSelectionDoorV1 = LedgerOperationDoorV1[LedgerListRequest, LedgerListProjection]
"""One page of entries chosen by the list operation's own filters."""
type LedgerBulkClassifyDoorV1 = LedgerOperationDoorV1[LedgerBulkClassifyRequest, LedgerBulkClassifyProjection]
type LedgerOperatorIvaDoorV1 = LedgerOperationDoorV1[LedgerOperatorIvaRequest, LedgerOperatorIvaResult]
type LedgerRuleListDoorV1 = LedgerOperationDoorV1[LedgerRuleListRequest, LedgerRuleListProjection]
type LedgerRuleAddDoorV1 = LedgerOperationDoorV1[LedgerRuleAddRequest, LedgerRuleAddProjection]
type LedgerRuleApplyDoorV1 = LedgerOperationDoorV1[LedgerRuleApplyRequest, LedgerRuleApplyProjection]
type LedgerCounterpartyDoorV1 = LedgerOperationDoorV1[LedgerCounterpartyRequest, LedgerCounterpartyResult]
type LedgerSplitDoorV1 = LedgerOperationDoorV1[LedgerSplitRequest, LedgerSplitOperationResult]
type LedgerAllocateDoorV1 = LedgerOperationDoorV1[LedgerAllocateRequest, LedgerAllocateOperationResult]
type LedgerParticipationDoorV1 = LedgerOperationDoorV1[LedgerParticipationRequest, LedgerParticipationProjection]
type LedgerParticipationRebuildDoorV1 = LedgerOperationDoorV1[
    LedgerParticipationRebuildRequest, LedgerParticipationRebuildProjection
]
type LedgerLlmDiagnosticsDoorV1 = LedgerOperationDoorV1[LedgerLlmDiagnosticsRequest, LedgerLlmDiagnosticsProjection]
type LedgerRatiosListDoorV1 = LedgerOperationDoorV1[LedgerRatiosListRequest, LedgerRatiosListProjection]
type LedgerRatiosEligibleDoorV1 = LedgerOperationDoorV1[LedgerRatiosEligibleRequest, LedgerRatiosEligibleProjection]
type LedgerRatiosValidateDoorV1 = LedgerOperationDoorV1[LedgerRatiosValidateRequest, LedgerRatiosValidateProjection]
type LedgerRatiosSetDoorV1 = LedgerOperationDoorV1[LedgerRatiosSetRequest, LedgerRatiosSetProjection]
type LedgerRatiosUnsetDoorV1 = LedgerOperationDoorV1[LedgerRatiosUnsetRequest, LedgerRatiosUnsetProjection]


class LedgerSuggestionReviewDoorV1(Protocol):
    """Injected door to one review operation, which pauses for the operator's decision."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...

    async def submit(self, request: LedgerLlmReviewRequest) -> OperationControllerPort:
        """Submit and start one review, returning the operation the modal drives."""
        ...

    async def read_result(
        self, request: LedgerLlmReviewRequest, projection: OperationPublicProjectionV1
    ) -> LedgerLlmOperationResult:
        """Read the settled outcome of a review this door submitted."""
        ...


@dataclass(frozen=True, slots=True)
class LedgerCategorisationDoorsV1:
    """Every categorisation door of one admitted profile, as the tools are built from them."""

    selection: LedgerSelectionDoorV1
    bulk_classify: LedgerBulkClassifyDoorV1
    operator_iva: LedgerOperatorIvaDoorV1
    classify_review: LedgerSuggestionReviewDoorV1
    split_review: LedgerSuggestionReviewDoorV1
    rule_list: LedgerRuleListDoorV1
    rule_add: LedgerRuleAddDoorV1
    rule_apply: LedgerRuleApplyDoorV1
    counterparty: LedgerCounterpartyDoorV1
    split: LedgerSplitDoorV1
    allocate: LedgerAllocateDoorV1
    participation: LedgerParticipationDoorV1
    participation_rebuild: LedgerParticipationRebuildDoorV1
    llm_diagnostics: LedgerLlmDiagnosticsDoorV1
    ratios_list: LedgerRatiosListDoorV1
    ratios_eligible: LedgerRatiosEligibleDoorV1
    ratios_validate: LedgerRatiosValidateDoorV1
    ratios_set: LedgerRatiosSetDoorV1
    ratios_unset: LedgerRatiosUnsetDoorV1


__all__ = [
    "LedgerAllocateDoorV1",
    "LedgerBulkClassifyDoorV1",
    "LedgerCategorisationDoorsV1",
    "LedgerCounterpartyDoorV1",
    "LedgerLlmDiagnosticsDoorV1",
    "LedgerOperationDoorV1",
    "LedgerOperatorIvaDoorV1",
    "LedgerParticipationDoorV1",
    "LedgerParticipationRebuildDoorV1",
    "LedgerRatiosEligibleDoorV1",
    "LedgerRatiosListDoorV1",
    "LedgerRatiosSetDoorV1",
    "LedgerRatiosUnsetDoorV1",
    "LedgerRatiosValidateDoorV1",
    "LedgerRuleAddDoorV1",
    "LedgerRuleApplyDoorV1",
    "LedgerRuleListDoorV1",
    "LedgerSelectionDoorV1",
    "LedgerSplitDoorV1",
    "LedgerSuggestionReviewDoorV1",
]
