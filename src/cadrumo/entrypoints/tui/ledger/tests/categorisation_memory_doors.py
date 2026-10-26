"""Every categorisation door over one in-memory profile, as the tools are built from them."""

from __future__ import annotations

from dataclasses import dataclass, field

from .....application.ledger.allocate_operation import LedgerAllocateOperationResult, LedgerAllocateRequest
from .....application.ledger.bulk_classify_operation import LedgerBulkClassifyProjection, LedgerBulkClassifyRequest
from .....application.ledger.counterparty_operation import LedgerCounterpartyRequest, LedgerCounterpartyResult
from .....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from .....application.ledger.llm_diagnostics_operation import (
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from .....application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
)
from .....application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest, LedgerOperatorIvaResult
from .....application.ledger.participation_operation import LedgerParticipationProjection, LedgerParticipationRequest
from .....application.ledger.participation_rebuild_operation import (
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
)
from .....application.ledger.ratios_contracts import (
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
from .....application.ledger.rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
)
from .....application.ledger.split_operation import LedgerSplitOperationResult, LedgerSplitRequest
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.identity.transaction_ids import TransactionId
from .....domain.transactions.enums import BusinessClassification
from ..categorisation_doors import LedgerCategorisationDoorsV1
from ..controller import LedgerWorkspaceController
from ..models import LedgerClassificationResultV1, LedgerClassificationSubmissionV1
from ..tools import LedgerToolV1
from ..workspace_injection import LedgerWorkspaceInjection
from .categorisation_entry_fixtures import MemoryLedger, synthetic_transaction
from .categorisation_fixtures import MemoryDoor, MemoryRuleBook
from .categorisation_register_fixtures import MemoryCounterparties, MemoryRatios, diagnostics_report
from .categorisation_review_fixtures import MemoryReviewDoor
from .workspace_fixtures import (
    LEDGER_TX_A,
    LEDGER_TX_B,
    ledger_context,
    ledger_focused_context,
    ledger_projection,
    ledger_review_action,
)


def _workspace_ledger() -> MemoryLedger:
    """A ledger holding the two entries the workspace fixture projects, with their amounts."""
    return MemoryLedger(
        entries={
            LEDGER_TX_A: synthetic_transaction(LEDGER_TX_A, description="Material de oficina", amount="1250.00"),
            LEDGER_TX_B: synthetic_transaction(
                LEDGER_TX_B,
                description="Servicios de consultoría",
                amount="480.50",
                classification=BusinessClassification.BUSINESS,
            ),
        }
    )


@dataclass
class MemoryCategorisationProfile:
    """The in-memory state behind every categorisation door of one synthetic profile."""

    ledger: MemoryLedger = field(default_factory=_workspace_ledger)
    rules: MemoryRuleBook = field(default_factory=MemoryRuleBook)
    counterparties: MemoryCounterparties = field(default_factory=MemoryCounterparties)
    ratios: MemoryRatios = field(default_factory=MemoryRatios)

    def doors(self) -> MemoryCategorisationDoors:
        """One door per operation, each answering from this profile's state."""
        ledger = self.ledger
        return MemoryCategorisationDoors(
            selection=MemoryDoor(ledger.list_page),
            bulk_classify=MemoryDoor(ledger.bulk_classify),
            operator_iva=MemoryDoor(ledger.derive_iva),
            classify_review=MemoryReviewDoor(ledger, definition_id=LEDGER_CLASSIFY_REVIEW_DEFINITION_ID),
            split_review=MemoryReviewDoor(ledger, definition_id=LEDGER_SPLIT_REVIEW_DEFINITION_ID),
            rule_list=MemoryDoor(self.rules.list_rules),
            rule_add=MemoryDoor(self.rules.add_rule),
            rule_apply=MemoryDoor(self.rules.apply_rules),
            counterparty=MemoryDoor(self.counterparties.act),
            split=MemoryDoor(ledger.split),
            allocate=MemoryDoor(ledger.allocate),
            participation=MemoryDoor(ledger.participation),
            participation_rebuild=MemoryDoor(ledger.rebuild),
            llm_diagnostics=MemoryDoor(diagnostics_report),
            ratios_list=MemoryDoor(self.ratios.list_overrides),
            ratios_eligible=MemoryDoor(self.ratios.eligible),
            ratios_validate=MemoryDoor(self.ratios.validate),
            ratios_set=MemoryDoor(self.ratios.set_ratio),
            ratios_unset=MemoryDoor(self.ratios.unset_ratio),
        )


@dataclass(frozen=True)
class MemoryCategorisationDoors:
    """The in-memory doors, each still typed as the fake it is so a test can steer and read it."""

    selection: MemoryDoor[LedgerListRequest, LedgerListProjection]
    bulk_classify: MemoryDoor[LedgerBulkClassifyRequest, LedgerBulkClassifyProjection]
    operator_iva: MemoryDoor[LedgerOperatorIvaRequest, LedgerOperatorIvaResult]
    classify_review: MemoryReviewDoor
    split_review: MemoryReviewDoor
    rule_list: MemoryDoor[LedgerRuleListRequest, LedgerRuleListProjection]
    rule_add: MemoryDoor[LedgerRuleAddRequest, LedgerRuleAddProjection]
    rule_apply: MemoryDoor[LedgerRuleApplyRequest, LedgerRuleApplyProjection]
    counterparty: MemoryDoor[LedgerCounterpartyRequest, LedgerCounterpartyResult]
    split: MemoryDoor[LedgerSplitRequest, LedgerSplitOperationResult]
    allocate: MemoryDoor[LedgerAllocateRequest, LedgerAllocateOperationResult]
    participation: MemoryDoor[LedgerParticipationRequest, LedgerParticipationProjection]
    participation_rebuild: MemoryDoor[LedgerParticipationRebuildRequest, LedgerParticipationRebuildProjection]
    llm_diagnostics: MemoryDoor[LedgerLlmDiagnosticsRequest, LedgerLlmDiagnosticsProjection]
    ratios_list: MemoryDoor[LedgerRatiosListRequest, LedgerRatiosListProjection]
    ratios_eligible: MemoryDoor[LedgerRatiosEligibleRequest, LedgerRatiosEligibleProjection]
    ratios_validate: MemoryDoor[LedgerRatiosValidateRequest, LedgerRatiosValidateProjection]
    ratios_set: MemoryDoor[LedgerRatiosSetRequest, LedgerRatiosSetProjection]
    ratios_unset: MemoryDoor[LedgerRatiosUnsetRequest, LedgerRatiosUnsetProjection]

    def bundle(self) -> LedgerCategorisationDoorsV1:
        """The same doors as the tools receive them."""
        return LedgerCategorisationDoorsV1(
            selection=self.selection,
            bulk_classify=self.bulk_classify,
            operator_iva=self.operator_iva,
            classify_review=self.classify_review,
            split_review=self.split_review,
            rule_list=self.rule_list,
            rule_add=self.rule_add,
            rule_apply=self.rule_apply,
            counterparty=self.counterparty,
            split=self.split,
            allocate=self.allocate,
            participation=self.participation,
            participation_rebuild=self.participation_rebuild,
            llm_diagnostics=self.llm_diagnostics,
            ratios_list=self.ratios_list,
            ratios_eligible=self.ratios_eligible,
            ratios_validate=self.ratios_validate,
            ratios_set=self.ratios_set,
            ratios_unset=self.ratios_unset,
        )


class _UnusedClassificationDoor:
    """The single-entry classification door the Classification area needs to open; tools never call it."""

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> LedgerClassificationResultV1:
        raise AssertionError(f"a categorisation tool used the single-entry classification door: {submission}")


def categorisation_controller(
    *, selected: TransactionId | None = LEDGER_TX_A, tools: tuple[LedgerToolV1, ...] = ()
) -> LedgerWorkspaceController:
    """The workspace a tool is opened over, with the first fixture entry selected unless told otherwise."""
    return LedgerWorkspaceController(
        ledger_focused_context(selected) if selected is not None else ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            classify_action=ActionReference(action_id=lookup_action("operator.ledger.classify").action_id),
            classification_submitter=_UnusedClassificationDoor(),
            tools=tools,
        ),
    )


__all__ = [
    "LEDGER_TX_A",
    "LEDGER_TX_B",
    "MemoryCategorisationDoors",
    "MemoryCategorisationProfile",
    "categorisation_controller",
]
