"""Exact-profile registered invoice linkage through the canonical atomic writer."""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CoreValidationError
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.invoices.errors import InvoiceLinkError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..review.filter import LedgerReviewStatus
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_common import build_manual_ledger_result, resolve_revision_guarded_transaction_repository
from .actions_manual import ledger_transaction_result_payload, link_manual_transaction_invoice
from .commit_fence import (
    LedgerCommitAttemptTracker,
    RevisionGuardedTrackedLedgerTransactionRepository,
    run_with_ledger_commit_fence,
)
from .export_link_operation_ports import (
    resolve_export_link_access,
    settle_export_link_failure,
)
from .id_resolution import resolve_transaction_id
from .transaction_projection import LedgerTransactionProjection

LEDGER_LINK_OPERATION_DEFINITION_ID = "ledger.link"
LEDGER_LINK_VALIDATION_REFUSAL_CODE = "REFUSED_LEDGER_LINK_VALIDATION"
_Identifier = Annotated[str, Field(min_length=1, max_length=64)]


class LedgerLinkValidationRefusedError(CoreValidationError):
    """Declared operator-correctable missing or cross-profile invoice refusal."""


class LedgerLinkRequest(BaseModel):
    """One transaction prefix and one existing invoice in the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_id: _Identifier
    invoice_id: _Identifier
    actor: Annotated[str, Field(max_length=64)] | None = None


class LedgerLinkProjection(BaseModel):
    """The accepted mutation quintet and existing invoice-only link metadata."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    operation: Literal["link"] = "link"
    bucket_id: str
    transaction_id: _Identifier
    invoice_id: _Identifier
    actor: Annotated[str, Field(min_length=1, max_length=64)]
    bucket_event_ids: Annotated[tuple[_Identifier, ...], Field(min_length=1, max_length=1)]
    review_status: LedgerReviewStatus
    transaction: LedgerTransactionProjection

    @model_validator(mode="after")
    def _exact_link(self) -> Self:
        if (
            self.bucket_id != str(self.profile_id)
            or self.transaction.transaction_id != self.transaction_id
            or self.transaction.invoice_id != self.invoice_id
        ):
            raise ValueError("ledger linkage result contradicts its profile or reciprocal link")
        return self


class LedgerLinkOperationResult(BaseModel):
    """Complete mutation result or closed canonical refusal without invoice values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_id: _Identifier
    invoice_id: _Identifier
    outcome: Literal["linked", "refused"]
    projection: LedgerLinkProjection | None = None
    reason: Literal["missing_invoice", "cross_bucket_invoice"] | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> Self:
        if self.outcome == "linked":
            if (
                self.reason is not None
                or self.projection is None
                or self.projection.profile_id != self.profile_id
                or self.projection.invoice_id != self.invoice_id
                or not self.projection.transaction_id.startswith(self.transaction_id.strip().lower())
            ):
                raise ValueError("ledger linkage outcome differs from its exact request")
        elif self.reason is None or self.projection is not None:
            raise ValueError("ledger linkage refusal is incomplete")
        return self


class LedgerLinkExecutionResult(BaseModel):
    """Encrypted result custody for the reviewed mutation receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result: LedgerLinkOperationResult


class LedgerLinkExecutor:
    """Delegate linkage and fence the single invoice/transaction/event co-commit."""

    def __init__(self, factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile canonical action-port factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Link the guarded records or return a closed prewrite refusal."""
        payload = request.payload
        if (
            request.definition_id != LEDGER_LINK_OPERATION_DEFINITION_ID
            or type(payload) is not LedgerLinkRequest
            or not isinstance(payload, LedgerLinkRequest)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(request.definition_id)
        tracker = LedgerCommitAttemptTracker()

        def work() -> LedgerLinkProjection:
            ports = self._factory(bucket_id=str(payload.profile_id), operation=context.authority_operation)
            if ports.operation is not context.authority_operation:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            original = resolve_revision_guarded_transaction_repository(
                bucket_id=str(payload.profile_id), repository=ports.transaction_repository
            )
            repository = RevisionGuardedTrackedLedgerTransactionRepository(original, tracker)
            actor = (payload.actor or "operator").strip() or "operator"
            with validating_governed_facts(context.authority_operation):
                transaction_id = resolve_transaction_id(payload.transaction_id, repository.load().transactions)
                result = link_manual_transaction_invoice(
                    bucket_id=str(payload.profile_id),
                    transaction_id=transaction_id,
                    invoice_id=payload.invoice_id,
                    actor=actor,
                    source_command="aeat app ledger link",
                    ports=replace(ports, transaction_repository=repository),
                )
                transaction = result.transactions.get(result.transaction_id)
                if transaction is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                canonical = ledger_transaction_result_payload(
                    build_manual_ledger_result(str(payload.profile_id), transaction, result.bucket_event_ids)
                )
            return LedgerLinkProjection(
                profile_id=payload.profile_id,
                bucket_id=canonical.bucket_id,
                transaction_id=canonical.transaction_id,
                invoice_id=result.invoice_id,
                actor=actor,
                bucket_event_ids=result.bucket_event_ids,
                review_status=canonical.review_status,
                transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
            )

        try:
            projection = await run_with_ledger_commit_fence(
                work, tracker=tracker, context=context, task_name=request.definition_id
            )
        except InvoiceLinkError as error:
            facts = error.context
            reason: Literal["missing_invoice", "cross_bucket_invoice"] | None = None
            if facts is not None and facts.get("invoice_id") == payload.invoice_id:
                if facts.get("command_bucket_id") == str(payload.profile_id) and "invoice_bucket_id" in facts:
                    reason = "cross_bucket_invoice"
                elif facts.get("bucket_id") == str(payload.profile_id):
                    reason = "missing_invoice"
            if tracker.attempt_count or tracker.has_possible_write or reason is None:
                await settle_export_link_failure(tracker, context, confirmed_effect=OperationEffect.UPDATED)
                raise
            result = LedgerLinkOperationResult(
                profile_id=payload.profile_id,
                transaction_id=payload.transaction_id,
                invoice_id=payload.invoice_id,
                outcome="refused",
                reason=reason,
            )
            async with context.cancellation.irreversible_section():
                require_operation_profile(request, context, payload.profile_id)
                await context.events.effect(OperationEffect.NONE)
                detail_ref = await context.operands.put(LedgerLinkExecutionResult(result=result), written_at=now())
            return OperationRefusalEvidence(refusal_code=LEDGER_LINK_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref)
        except BaseException:
            await settle_export_link_failure(tracker, context, confirmed_effect=OperationEffect.UPDATED)
            raise
        if (
            not tracker.confirmed_write
            or tracker.has_uncertain_write
            or len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        result = LedgerLinkOperationResult(
            profile_id=payload.profile_id,
            transaction_id=payload.transaction_id,
            invoice_id=payload.invoice_id,
            outcome="linked",
            projection=projection,
        )
        return await context.operands.put(LedgerLinkExecutionResult(result=result), written_at=now())


def project_ledger_link_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> LedgerLinkOperationResult:
    """Require a successful atomic co-commit for the exact profile and purpose."""
    if type(result) is not LedgerLinkExecutionResult or not isinstance(result, LedgerLinkExecutionResult):
        raise ValueError("invalid ledger linkage result")
    projection = result.result
    if (
        receipt.identity.definition_id != LEDGER_LINK_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES
    ):
        raise ValueError("ledger linkage result contradicts its terminal receipt")
    if projection.outcome == "linked":
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.effect is not OperationEffect.UPDATED
        ):
            raise ValueError("ledger linkage success contradicts its terminal receipt")
    elif (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref != LEDGER_LINK_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
    ):
        raise ValueError("ledger linkage refusal contradicts its terminal receipt")
    return LedgerLinkOperationResult.model_validate(projection.model_dump(mode="python"), strict=True)


def resolve_ledger_link_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact whole-profile linkage and reviewed result destination consent."""
    payload = request.payload
    if (
        request.definition_id != LEDGER_LINK_OPERATION_DEFINITION_ID
        or type(payload) is not LedgerLinkRequest
        or not isinstance(payload, LedgerLinkRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_export_link_access(
        request, context, profile_id=payload.profile_id, periods=frozenset[Period](), requires_human=False
    )


def build_ledger_link_definition(factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Expose the existing value-safe link through the shared worker on all fronts."""
    return OperationDefinition(
        definition_id=LEDGER_LINK_OPERATION_DEFINITION_ID,
        request_type=LedgerLinkRequest,
        result_type=LedgerLinkExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerLinkRequest, executor_type=LedgerLinkExecutor, build=lambda: LedgerLinkExecutor(factory)
        ),
        phase_codes=(LEDGER_LINK_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        refusal_detail_codes=frozenset({LEDGER_LINK_VALIDATION_REFUSAL_CODE}),
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_ledger_link_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the canonical strict mutation projection to exact purpose and consent."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerLinkOperationResult,
        result_projector=project_ledger_link_result,
        access_resolver=resolve_ledger_link_access,
    )
