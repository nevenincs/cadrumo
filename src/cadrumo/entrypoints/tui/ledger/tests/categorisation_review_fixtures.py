"""A review door whose operation the real operation modal drives to the operator's decision.

The door's controller publishes one REVIEW interaction under the registered
review contract of ``ledger.classify.review`` or ``ledger.split.review``,
answers the modal's apply or reject through a response control, and then
settles. The settled outcome is the operation's own public result, and only an
applied decision changes the in-memory ledger.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from pydantic import BaseModel

from .....application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from .....application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LedgerLlmReviewProjection,
    LedgerLlmReviewRequest,
    LedgerLlmSuggestionProjection,
)
from .....application.ledger.llm_review_execution import LedgerLlmOperationPortsFactory
from .....application.ledger.llm_review_operation import (
    build_ledger_llm_review_definition,
    build_ledger_llm_review_registration,
)
from .....application.ledger.llm_review_results import LedgerLlmOperationResult
from .....application.operations.frontend_contracts import OperationCancellationResultV1, OperationDetachResultV1
from .....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionSuccessV1,
)
from .....application.operations.interactions import OperationResponseIntent, OperationResponseIntentValue
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationPublicDefinitionContractV1, OperationRegistry
from .....application.review.filter import LedgerReviewStatus
from .....core.errors.hierarchy import RecordedRegisteredError
from .....core.identity.transaction_ids import TransactionId
from .....core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .....domain.transactions.enums import BusinessClassification
from .categorisation_entry_fixtures import MemoryLedger
from .categorisation_fixtures import (
    CATEGORISATION_PROFILE_ID,
    CATEGORISATION_REFUSAL_CODE,
    CATEGORISATION_REFUSAL_KEY,
    synthetic_id,
)

_OPERATION_ID = "c" * 64
_INTERACTION_ID = "d" * 64
_DIGEST = "e" * 64
_NOW = datetime(2026, 3, 14, tzinfo=UTC)
_PROVENANCE = "llm:lector-local"


def review_contract(definition_id: str) -> tuple[OperationPublicDefinitionContractV1, str]:
    """The registered public contract of one review definition and its contract-set digest."""
    factory = cast(LedgerLlmOperationPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_ledger_llm_review_definition(definition_id, factory)
    registry = OperationRegistry(
        definitions=(definition,), public_registrations=(build_ledger_llm_review_registration(definition),)
    )
    return registry.lookup_public_contract(definition_id), registry.public_contract_set.contract_set_digest


def suggestion_for(request: LedgerLlmReviewRequest, transaction_id: TransactionId) -> LedgerLlmReviewProjection:
    """The synthetic proposal a review of ``request`` publishes."""
    split = request.mode in {"split", "auto_split"}
    return LedgerLlmReviewProjection(
        profile_id=request.profile_id,
        reviewed_proposal_digest=_DIGEST,
        suggestion=LedgerLlmSuggestionProjection(
            kind="split" if split else "classification",
            transaction_id=transaction_id,
            provenance=_PROVENANCE,
            reason="El concepto coincide con material de oficina.",
            evidence_id=None,
            classification=None if split else BusinessClassification.BUSINESS.value,
            category=None if split else "suministros_oficina",
            confidence="0.82",
            parent_amount="1250.00" if split else None,
        ),
    )


class _Cue:
    """Wakes the modal soon after every observation, as the runtime's change cue does."""

    armed = False

    def arm(self) -> None:
        self.armed = True

    async def wait(self, timeout: float) -> None:
        del timeout
        await asyncio.sleep(0.01)

    def close(self) -> None:
        self.armed = False


class _Control:
    def __init__(self, controller: MemoryReviewController) -> None:
        self.controller = controller

    async def inspect(self) -> OperationResponseControlSuccessV1:
        return OperationResponseControlSuccessV1(
            operation_id=_OPERATION_ID,
            interaction_id=_INTERACTION_ID,
            revision=2,
            available=self.controller.decision is None,
            permitted_intents=frozenset[OperationResponseIntentValue]()
            if self.controller.decision is not None
            else frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
        )

    async def apply(self, request: OperationResponseApplyRequestV1) -> OperationResponseMutationSuccessV1:
        return self.controller.decide(OperationResponseIntent.APPLY, request.revision)

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationSuccessV1:
        return self.controller.decide(OperationResponseIntent.REJECT, request.revision)


class MemoryReviewController:
    """One submitted review: waiting for the operator, then settled by their decision."""

    def __init__(self, request: LedgerLlmReviewRequest, definition_id: str, transaction_id: TransactionId) -> None:
        """Publish the review of ``request`` under the registered contract of ``definition_id``."""
        self.request = request
        self.definition_id = definition_id
        self.transaction_id = transaction_id
        self.contract, self.contract_set_digest = review_contract(definition_id)
        self.decision: OperationResponseIntentValue | None = None

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return "operator:categorisation-review"

    async def start(self) -> str:
        return _OPERATION_ID

    def operation_changes(self) -> _Cue:
        return _Cue()

    def decide(self, intent: OperationResponseIntentValue, revision: int) -> OperationResponseMutationSuccessV1:
        self.decision = intent
        return OperationResponseMutationSuccessV1(
            operation_id=_OPERATION_ID, interaction_id=_INTERACTION_ID, revision=revision, response_action=intent
        )

    def projection(self) -> OperationPublicProjectionV1:
        contract = self.contract
        settled = self.decision is not None
        pending = OperationNoPendingInteractionV1()
        if not settled:
            assert contract.review_projection_schema is not None
            assert contract.interaction_response_schema is not None
            reference = OperationReviewProjectionReferenceV1(
                operation_id=_OPERATION_ID,
                interaction_id=_INTERACTION_ID,
                revision=2,
                review_projection_schema=contract.review_projection_schema,
                definition_contract_digest=contract.definition_contract_digest,
                expires_at=None,
            )
            pending = OperationReviewAvailableInteractionV1(
                operation_id=_OPERATION_ID,
                interaction_id=_INTERACTION_ID,
                revision=2,
                presentation_code="ledger.llm.review-ready",
                response_schema=contract.interaction_response_schema,
                expires_at=None,
                review_reference=reference,
            )
        return OperationPublicProjectionV1(
            operation_id=_OPERATION_ID,
            definition_id=self.definition_id,
            subject_ref=profile_operation_subject(str(CATEGORISATION_PROFILE_ID)),
            revision=3 if settled else 2,
            anchor_cursor=0,
            definition_contract=contract,
            contract_set_digest=self.contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL if settled else OperationLifecycle.WAITING_FOR_INTERACTION,
            terminal_condition=OperationTerminalCondition.SUCCEEDED if settled else None,
            effect=OperationEffect.UPDATED if settled else OperationEffect.NONE,
            phase_code=None if settled else "ledger.llm.review",
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=contract.close_policy,
            cancellation=contract.cancellation,
            cancellable_now=False,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=pending,
            result_ref="f" * 64 if settled else None,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
        )

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        del page_limit
        return OperationObservationSuccessV1(
            projection=self.projection(),
            event_page=OperationPublicEventPageV1(
                operation_id=_OPERATION_ID,
                anchor_cursor=0,
                requested_cursor=after_cursor,
                status=OperationReplayStatus.CAUGHT_UP,
                events=(),
                next_cursor=after_cursor,
                restart_cursor=None,
            ),
        )

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionSuccessV1[LedgerLlmReviewProjection]:
        del projection_type
        return OperationReviewProjectionSuccessV1[LedgerLlmReviewProjection](
            projection_schema=reference.review_projection_schema,
            definition_contract_digest=reference.definition_contract_digest,
            projection=suggestion_for(self.request, self.transaction_id),
        )

    async def response_control(self, *, interaction_id: str, revision: int) -> _Control:
        del interaction_id, revision
        return _Control(self)

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError(f"a review is not cancellable at revision {expected_revision}")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise AssertionError(f"the review fixture is never detached at revision {expected_revision}")


class MemoryReviewDoor:
    """Submits reviews whose outcome, once decided in the modal, the in-memory ledger reflects."""

    def __init__(self, ledger: MemoryLedger, *, definition_id: str = LEDGER_CLASSIFY_REVIEW_DEFINITION_ID) -> None:
        """Review entries of ``ledger`` under ``definition_id``."""
        self.ledger = ledger
        self.definition_id = definition_id
        self.controllers: list[MemoryReviewController] = []
        self.results: list[LedgerLlmOperationResult] = []
        self.refusing = False

    @property
    def profile_id(self) -> UUID:
        return CATEGORISATION_PROFILE_ID

    async def submit(self, request: LedgerLlmReviewRequest) -> MemoryReviewController:
        if self.refusing:
            raise RecordedRegisteredError(CATEGORISATION_REFUSAL_CODE, translated_message=CATEGORISATION_REFUSAL_KEY)
        transaction_id = next(key for key in self.ledger.entries if key.startswith(request.transaction_id))
        controller = MemoryReviewController(request, self.definition_id, transaction_id)
        self.controllers.append(controller)
        return controller

    async def read_result(
        self, request: LedgerLlmReviewRequest, projection: OperationPublicProjectionV1
    ) -> LedgerLlmOperationResult:
        controller = next(item for item in self.controllers if item.request == request)
        assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        transaction_id = controller.transaction_id
        split = request.mode in {"split", "auto_split"}
        if controller.decision == "reject":
            result = LedgerLlmOperationResult(
                profile_id=request.profile_id,
                reviewed_proposal_digest=_DIGEST,
                outcome="rejected",
                transaction_id=transaction_id,
                bucket_event_id="9" * 64,
                suggestion_kind="split" if split else "classification",
                provenance=_PROVENANCE,
            )
        elif split:
            children = (synthetic_id(90_001), synthetic_id(90_002))
            result = LedgerLlmOperationResult(
                profile_id=request.profile_id,
                reviewed_proposal_digest=_DIGEST,
                outcome="split",
                transaction_id=transaction_id,
                split_group_id="8" * 64,
                child_transaction_ids=children,
                classified_child_count=len(children),
                provenance=_PROVENANCE,
            )
        else:
            updated = self.ledger.entries[transaction_id].model_copy(
                update={"business_classification": BusinessClassification.BUSINESS.value}
            )
            self.ledger.entries[transaction_id] = updated
            result = LedgerLlmOperationResult(
                profile_id=request.profile_id,
                reviewed_proposal_digest=_DIGEST,
                outcome="classified",
                transaction_id=transaction_id,
                classification=LedgerClassifyOperationResult(
                    outcome="classified",
                    profile_id=request.profile_id,
                    transaction=updated,
                    review_status=LedgerReviewStatus.REVIEWED,
                    bucket_event_ids=("7" * 64,),
                ),
                provenance=_PROVENANCE,
            )
        self.results.append(result)
        return result


__all__ = ["MemoryReviewController", "MemoryReviewDoor", "review_contract", "suggestion_for"]
