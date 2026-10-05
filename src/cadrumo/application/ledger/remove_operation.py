"""Guarded exact-profile removal of one canonical ledger transaction."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.async_cleanup import await_cancellation_complete
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_lifecycle import remove_manual_transaction
from .id_resolution import resolve_transaction_id
from .models import LedgerRemovalBlocker, LedgerTransactionRemovalReport
from .read_access import resolve_ledger_commit_access, resolve_ledger_read_access

LEDGER_REMOVE_OPERATION_DEFINITION_ID = "ledger.remove"
LEDGER_REMOVE_PHASE = "ledger.remove"
_MAX_RECEIPT_COLLECTION_ITEMS = 4096
_MAX_RECEIPT_REASON_LENGTH = 4096
_ReceiptIdentity = Annotated[str, Field(max_length=64)]
_ReceiptIdentities = Annotated[tuple[_ReceiptIdentity, ...], Field(max_length=_MAX_RECEIPT_COLLECTION_ITEMS)]


class LedgerRemoveBlockerProjection(BaseModel):
    """One bounded filed-basis blocker or stale-draft advisory."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    revision_state: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)


_ReceiptBlockers = Annotated[
    tuple[LedgerRemoveBlockerProjection, ...],
    Field(max_length=_MAX_RECEIPT_COLLECTION_ITEMS),
]


class LedgerRemoveReportProjection(BaseModel):
    """Bounded wire projection of the canonical lifecycle report."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    transaction_id: TransactionId
    removed: bool = False
    dry_run: bool = False
    actor: str = Field(min_length=1, max_length=64)
    reason: str = Field(max_length=_MAX_RECEIPT_REASON_LENGTH)
    cascaded_purchase_invoice_evidence_ids: _ReceiptIdentities = ()
    cascaded_attachment_ids: _ReceiptIdentities = ()
    blocking_modelo_references: _ReceiptBlockers = ()
    stale_draft_revision_references: _ReceiptBlockers = ()
    bucket_event_ids: _ReceiptIdentities = ()


def _project_blockers(rows: tuple[LedgerRemovalBlocker, ...]) -> tuple[LedgerRemoveBlockerProjection, ...]:
    """Copy every canonical blocker while enforcing the published item limit."""
    return tuple(
        LedgerRemoveBlockerProjection(
            work_unit_id=row.work_unit_id,
            calculation_revision_id=row.calculation_revision_id,
            revision_state=row.revision_state,
            modelo=row.modelo,
            filing_year=row.filing_year,
            period=row.period,
        )
        for row in rows
    )


def _project_report(report: LedgerTransactionRemovalReport) -> LedgerRemoveReportProjection:
    """Preserve every report field in the bounded operation result."""
    return LedgerRemoveReportProjection(
        bucket_id=report.bucket_id,
        transaction_id=report.transaction_id,
        removed=report.removed,
        dry_run=report.dry_run,
        actor=report.actor,
        reason=report.reason,
        cascaded_purchase_invoice_evidence_ids=report.cascaded_purchase_invoice_evidence_ids,
        cascaded_attachment_ids=report.cascaded_attachment_ids,
        blocking_modelo_references=_project_blockers(report.blocking_modelo_references),
        stale_draft_revision_references=_project_blockers(report.stale_draft_revision_references),
        bucket_event_ids=report.bucket_event_ids,
    )


class LedgerRemoveRequest(BaseModel):
    """Private exact-profile request; ``transaction_id`` accepts a CLI prefix."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: str = Field(min_length=1, max_length=96)
    reason: str = Field(default="", max_length=_MAX_RECEIPT_REASON_LENGTH)
    dry_run: bool = False
    actor: str | None = Field(default=None, min_length=1, max_length=64)


class LedgerRemoveOperationResult(BaseModel):
    """Bounded, encrypted report preserving every canonical removal finding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    report: LedgerRemoveReportProjection


class LedgerRemoveExecutor:
    """Invoke the canonical action under exact profile and fresh commit custody."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile service composition capability."""
        self._ports_factory = ports_factory

    async def execute(self, request: OperationRequest[LedgerRemoveRequest], context: OperationExecutorContext) -> str:
        """Run preview or deletion and publish its bounded encrypted receipt."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_REMOVE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_REMOVE_PHASE)

        def remove(*, dry_run: bool) -> LedgerTransactionRemovalReport:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
            catalogue = ports.transaction_repository.load()
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
            return remove_manual_transaction(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                actor=payload.actor or bucket_id or "operator",
                reason=payload.reason,
                dry_run=dry_run,
                source_command="aeat app ledger remove",
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
                invoice_repository=ports.invoice_repository,
                work_unit_repository=ports.work_unit_repository,
                calculation_repository=ports.calculation_repository,
            )

        if payload.dry_run:

            async def preview() -> str:
                report = await asyncio.to_thread(remove, dry_run=True)
                result = _operation_result(payload.profile_id, report)
                await context.events.effect(OperationEffect.NONE)
                return await context.operands.put(result, written_at=now())

            return await await_cancellation_complete(preview(), task_name="ledger-remove-preview")

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                # Establish that the complete receipt is representable before any
                # catalogue or audit mutation. The canonical action re-loads and
                # re-checks all guards while committing.
                preflight = await asyncio.to_thread(remove, dry_run=True)
                _operation_result(payload.profile_id, preflight)
                await context.events.effect(OperationEffect.UNKNOWN)
                report = await asyncio.to_thread(remove, dry_run=False)
                await context.events.effect(OperationEffect.UPDATED if report.removed else OperationEffect.NONE)
                result = _operation_result(payload.profile_id, report)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-remove-commit")


def build_ledger_remove_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare durable, exact-profile deletion with a bounded secure receipt."""
    return build_single_phase_definition(
        definition_id=LEDGER_REMOVE_OPERATION_DEFINITION_ID,
        request_type=LedgerRemoveRequest,
        result_type=LedgerRemoveOperationResult,
        executor_type=LedgerRemoveExecutor,
        build=lambda: LedgerRemoveExecutor(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def _operation_result(profile_id: UUID, report: LedgerTransactionRemovalReport) -> LedgerRemoveOperationResult:
    """Validate exact-profile identity and every bound before publishing a receipt."""
    if str(report.bucket_id) != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerRemoveOperationResult(profile_id=profile_id, report=_project_report(report))


def resolve_ledger_remove_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile access and COMMIT for a confirmed mutation."""
    if request.definition_id != LEDGER_REMOVE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerRemoveRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolve = resolve_ledger_read_access if request.payload.dry_run else resolve_ledger_commit_access
    return resolve(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_remove_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and bounded result at the operation registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerRemoveOperationResult,
        access_resolver=resolve_ledger_remove_access,
    )


__all__ = [
    "LEDGER_REMOVE_OPERATION_DEFINITION_ID",
    "LEDGER_REMOVE_PHASE",
    "LedgerRemoveExecutor",
    "LedgerRemoveOperationResult",
    "LedgerRemoveRequest",
    "build_ledger_remove_definition",
    "build_ledger_remove_registration",
    "resolve_ledger_remove_access",
]
