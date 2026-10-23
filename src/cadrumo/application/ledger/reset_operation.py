"""Guarded exact-profile reset of one canonical ledger catalogue."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.errors import TransactionValidationError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_lifecycle import reset_ledger_catalogue
from .models import LedgerCatalogueResetReport
from .read_access import resolve_ledger_commit_access, resolve_ledger_read_access
from .removal_receipt_projection import (
    MAX_LEDGER_REMOVAL_RECEIPT_ITEMS,
    MAX_LEDGER_REMOVAL_RECEIPT_REASON_LENGTH,
    LedgerRemovalReceiptIdentities,
    LedgerRemovalReceiptProjection,
    project_removal_blockers,
)

LEDGER_RESET_OPERATION_DEFINITION_ID = "ledger.reset"
LEDGER_RESET_PHASE = "ledger.reset"


class LedgerResetReportProjection(LedgerRemovalReceiptProjection):
    """Bounded wire projection of every canonical catalogue-reset finding."""

    removed_transaction_ids: LedgerRemovalReceiptIdentities = ()
    reset: bool = False


def _project_report(report: LedgerCatalogueResetReport) -> LedgerResetReportProjection:
    """Preserve every canonical reset field in the bounded operation result."""
    return LedgerResetReportProjection(
        bucket_id=report.bucket_id,
        removed_transaction_ids=report.removed_transaction_ids,
        reset=report.reset,
        dry_run=report.dry_run,
        actor=report.actor,
        reason=report.reason,
        cascaded_purchase_invoice_evidence_ids=report.cascaded_purchase_invoice_evidence_ids,
        cascaded_attachment_ids=report.cascaded_attachment_ids,
        blocking_modelo_references=project_removal_blockers(report.blocking_modelo_references),
        stale_draft_revision_references=project_removal_blockers(report.stale_draft_revision_references),
        bucket_event_ids=report.bucket_event_ids,
    )


class LedgerResetRequest(BaseModel):
    """Private exact-profile request for a preview or confirmed reset."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    reason: str = Field(default="", max_length=MAX_LEDGER_REMOVAL_RECEIPT_REASON_LENGTH)
    dry_run: bool = False
    actor: str | None = Field(default=None, min_length=1, max_length=64)


class LedgerResetOperationResult(BaseModel):
    """Bounded, encrypted receipt for one exact-profile catalogue reset."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    report: LedgerResetReportProjection


class LedgerResetExecutor:
    """Invoke the canonical reset action under exact-profile commit custody."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Retain the exact-profile service composition capability."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(self, request: OperationRequest[LedgerResetRequest], context: OperationExecutorContext) -> str:
        """Preview or reset one profile and publish its bounded encrypted receipt."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_RESET_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_RESET_PHASE)
        actor = execution_actor_label(
            self._execution_caller_reader, context, supplied=payload.actor or bucket_id or "operator"
        )

        def reset(*, dry_run: bool) -> LedgerCatalogueResetReport:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
            return reset_ledger_catalogue(
                bucket_id=bucket_id,
                actor=actor,
                reason=payload.reason,
                dry_run=dry_run,
                source_command="aeat app ledger reset",
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
                invoice_repository=ports.invoice_repository,
                work_unit_repository=ports.work_unit_repository,
                calculation_repository=ports.calculation_repository,
                max_receipt_items=MAX_LEDGER_REMOVAL_RECEIPT_ITEMS,
            )

        if payload.dry_run:

            async def preview() -> str:
                report = await asyncio.to_thread(reset, dry_run=True)
                result = _operation_result(payload.profile_id, report)
                await context.events.effect(OperationEffect.NONE)
                return await context.operands.put(result, written_at=now())

            return await await_cancellation_complete(preview(), task_name="ledger-reset-preview")

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                # Fresh COMMIT authority fences both preflight and mutation.
                # The canonical dry-run proves the complete receipt is
                # representable for the facts it observes; it performs no
                # writes. The canonical mutator repeats the receipt bound after
                # loading current facts and immediately before persistence.
                preflight = await asyncio.to_thread(reset, dry_run=True)
                _operation_result(payload.profile_id, preflight)
                if preflight.blocking_modelo_references:
                    raise TransactionValidationError(
                        "ledger catalogue reset refused because finalized modelo revisions cite transactions",
                        context={
                            "blocking_reference_count": str(len(preflight.blocking_modelo_references)),
                        },
                    )
                # The canonical action re-loads and re-checks every guard while
                # committing, so a concurrent filing change cannot slip past
                # the non-mutating preflight.
                await context.events.effect(OperationEffect.UNKNOWN)
                report = await asyncio.to_thread(reset, dry_run=False)
                await context.events.effect(OperationEffect.UPDATED if report.reset else OperationEffect.NONE)
                result = _operation_result(payload.profile_id, report)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-reset-commit")


def build_ledger_reset_definition(
    ports_factory: LedgerActionPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare durable exact-profile reset with a bounded secure receipt."""
    return build_single_phase_definition(
        definition_id=LEDGER_RESET_OPERATION_DEFINITION_ID,
        request_type=LedgerResetRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerResetOperationResult,
        executor_type=LedgerResetExecutor,
        build=lambda: LedgerResetExecutor(ports_factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
    )


def _operation_result(profile_id: UUID, report: LedgerCatalogueResetReport) -> LedgerResetOperationResult:
    """Validate profile identity and all bounds before publishing a receipt."""
    if report.bucket_id != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerResetOperationResult(profile_id=profile_id, report=_project_report(report))


def resolve_ledger_reset_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile access and COMMIT for a confirmed reset."""
    if request.definition_id != LEDGER_RESET_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerResetRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolve = resolve_ledger_read_access if request.payload.dry_run else resolve_ledger_commit_access
    return resolve(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_reset_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and bounded result at the operation registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerResetOperationResult,
        access_resolver=resolve_ledger_reset_access,
    )


__all__ = [
    "LEDGER_RESET_OPERATION_DEFINITION_ID",
    "LEDGER_RESET_PHASE",
    "LedgerResetExecutor",
    "LedgerResetOperationResult",
    "LedgerResetRequest",
    "build_ledger_reset_definition",
    "build_ledger_reset_registration",
    "resolve_ledger_reset_access",
]
