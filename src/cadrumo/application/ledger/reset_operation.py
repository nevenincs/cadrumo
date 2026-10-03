"""Guarded exact-profile reset of one canonical ledger catalogue."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.async_cleanup import await_cancellation_complete
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.errors import TransactionValidationError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory
from .actions_lifecycle import reset_ledger_catalogue
from .models import LedgerCatalogueResetReport, LedgerRemovalBlocker
from .read_access import resolve_ledger_read_access

LEDGER_RESET_OPERATION_DEFINITION_ID = "ledger.reset"
LEDGER_RESET_PHASE = "ledger.reset"
_MAX_RECEIPT_COLLECTION_ITEMS = 4096
_MAX_RECEIPT_REASON_LENGTH = 4096
_ReceiptIdentity = Annotated[str, Field(min_length=1, max_length=64)]
_ReceiptIdentities = Annotated[tuple[_ReceiptIdentity, ...], Field(max_length=_MAX_RECEIPT_COLLECTION_ITEMS)]


class LedgerResetBlockerProjection(BaseModel):
    """One bounded finalized filing reference or stale-draft advisory."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    revision_state: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)


_ReceiptBlockers = Annotated[
    tuple[LedgerResetBlockerProjection, ...],
    Field(max_length=_MAX_RECEIPT_COLLECTION_ITEMS),
]


class LedgerResetReportProjection(BaseModel):
    """Bounded wire projection of every canonical catalogue-reset finding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    removed_transaction_ids: _ReceiptIdentities = ()
    reset: bool = False
    dry_run: bool = False
    actor: str = Field(min_length=1, max_length=64)
    reason: str = Field(max_length=_MAX_RECEIPT_REASON_LENGTH)
    cascaded_purchase_invoice_evidence_ids: _ReceiptIdentities = ()
    cascaded_attachment_ids: _ReceiptIdentities = ()
    blocking_modelo_references: _ReceiptBlockers = ()
    stale_draft_revision_references: _ReceiptBlockers = ()
    bucket_event_ids: _ReceiptIdentities = ()


def _project_blockers(rows: tuple[LedgerRemovalBlocker, ...]) -> tuple[LedgerResetBlockerProjection, ...]:
    """Copy every canonical blocker while enforcing the published item limit."""
    return tuple(
        LedgerResetBlockerProjection(
            work_unit_id=row.work_unit_id,
            calculation_revision_id=row.calculation_revision_id,
            revision_state=row.revision_state,
            modelo=row.modelo,
            filing_year=row.filing_year,
            period=row.period,
        )
        for row in rows
    )


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
        blocking_modelo_references=_project_blockers(report.blocking_modelo_references),
        stale_draft_revision_references=_project_blockers(report.stale_draft_revision_references),
        bucket_event_ids=report.bucket_event_ids,
    )


class LedgerResetRequest(BaseModel):
    """Private exact-profile request for a preview or confirmed reset."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    reason: str = Field(default="", max_length=_MAX_RECEIPT_REASON_LENGTH)
    dry_run: bool = False
    actor: str | None = Field(default=None, min_length=1, max_length=64)


class LedgerResetOperationResult(BaseModel):
    """Bounded, encrypted receipt for one exact-profile catalogue reset."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    report: LedgerResetReportProjection


class LedgerResetExecutor:
    """Invoke the canonical reset action under exact-profile commit custody."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile service composition capability."""
        self._ports_factory = ports_factory

    async def execute(self, request: OperationRequest[LedgerResetRequest], context: OperationExecutorContext) -> str:
        """Preview or reset one profile and publish its bounded encrypted receipt."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_RESET_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_RESET_PHASE)

        def reset(*, dry_run: bool) -> LedgerCatalogueResetReport:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            if ports.operation is not operation or ports.transaction_repository.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            for repository in (
                ports.invoice_repository,
                ports.work_unit_repository,
                ports.calculation_repository,
            ):
                if getattr(repository, "bucket_id", None) != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return reset_ledger_catalogue(
                bucket_id=bucket_id,
                actor=payload.actor or bucket_id or "operator",
                reason=payload.reason,
                dry_run=dry_run,
                source_command="aeat app ledger reset",
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
                invoice_repository=ports.invoice_repository,
                work_unit_repository=ports.work_unit_repository,
                calculation_repository=ports.calculation_repository,
                max_receipt_items=_MAX_RECEIPT_COLLECTION_ITEMS,
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


def build_ledger_reset_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare durable exact-profile reset with a bounded secure receipt."""
    return OperationDefinition(
        definition_id=LEDGER_RESET_OPERATION_DEFINITION_ID,
        request_type=LedgerResetRequest,
        result_type=LedgerResetOperationResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerResetRequest,
            executor_type=LedgerResetExecutor,
            build=lambda: LedgerResetExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_RESET_PHASE,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def _operation_result(profile_id: UUID, report: LedgerCatalogueResetReport) -> LedgerResetOperationResult:
    """Validate profile identity and all bounds before publishing a receipt."""
    if str(report.bucket_id) != str(profile_id):
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
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    if request.payload.dry_run:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


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
