"""Human evidence ingestion through one exact-profile worker authority.

The canonical batch service retains ordering and per-document outcomes.
Only concrete custody writers determine effects; remote reads run outside COMMIT.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path
from typing import override
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.regime_legend import resolve_regime_legends
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, terminal_receipt_matches
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .batch_ingest import run_evidence_batch
from .commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from .evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchExecutionResult,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
    LedgerEvidenceBatchSnapshot,
)
from .evidence_ingestion_operation_ports import (
    LedgerEvidenceIngestionPorts,
    LedgerEvidenceIngestionPortsFactory,
)
from .evidence_port_identity import require_exact_evidence_ports
from .export_link_operation_ports import (
    resolve_export_link_access,
    settle_export_link_failure,
)
from .extraction_draft_repository import bind_extraction_draft_repository_factory
from .invoice_extraction_authority import default_invoice_extraction_period


class _CountingCommitTracker(LedgerCommitAttemptTracker):
    def __init__(self) -> None:
        super().__init__()
        self._count = 0
        self._count_lock = threading.Lock()

    @property
    def count(self) -> int:
        with self._count_lock:
            return self._count

    @override
    def call_writer(self, write: Callable[[], None]) -> None:
        super().call_writer(write)
        with self._count_lock:
            self._count += 1


class _ConcreteWrites:
    def __init__(self) -> None:
        self.tracker = _CountingCommitTracker()

    @property
    def count(self) -> int:
        return self.tracker.count

    def write(self, write: Callable[[], None]) -> None:
        self.tracker.call_writer(write)

    def effect(self, incomplete: bool = False) -> OperationEffect:
        if self.tracker.has_uncertain_write:
            return OperationEffect.UNKNOWN
        if self.count:
            return OperationEffect.PARTIAL if incomplete else OperationEffect.UPDATED
        return OperationEffect.NONE


def _require_ports(
    ports: LedgerEvidenceIngestionPorts, request_profile: UUID, context: OperationExecutorContext
) -> None:
    if ports.profile_id != request_profile or ports.operation is not context.authority_operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_exact_evidence_ports(ports.evidence, bucket_id=str(request_profile))


def _validated_payload(
    request: OperationRequest[LedgerEvidenceBatchRequest], context: OperationExecutorContext
) -> LedgerEvidenceBatchRequest:
    payload = request.payload
    require_operation_profile(request, context, payload.profile_id)
    if (
        type(payload) is not LedgerEvidenceBatchRequest
        or request.definition_id != LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return payload


class _ReadAdmission:
    """Bridge synchronous worker reads through the operation's cancellation guard."""

    def __init__(
        self,
        request: OperationRequest[LedgerEvidenceBatchRequest],
        payload: LedgerEvidenceBatchRequest,
        context: OperationExecutorContext,
        writes: _ConcreteWrites,
    ) -> None:
        self._request = request
        self._payload = payload
        self._context = context
        self._writes = writes
        self._loop = asyncio.get_running_loop()
        self.failure: BaseException | None = None

    async def _admit(self) -> None:
        if self.failure is not None:
            raise self.failure
        try:
            async with self._context.cancellation.irreversible_section():
                require_operation_profile(self._request, self._context, self._payload.profile_id)
        except BaseException as error:
            self.failure = error
            self._writes.tracker.abort()
            raise

    def before_read(self) -> None:
        asyncio.run_coroutine_threadsafe(self._admit(), self._loop).result()

    def raise_if_failed(self) -> None:
        if self.failure is not None:
            raise self.failure


def _execute_batch(
    payload: LedgerEvidenceBatchRequest,
    ports: LedgerEvidenceIngestionPorts,
    writes: _ConcreteWrites,
    context: OperationExecutorContext,
    before_read: Callable[[], None],
    raise_if_admission_failed: Callable[[], None],
) -> LedgerEvidenceBatchExecutionResult:
    period = default_invoice_extraction_period()
    legends = resolve_regime_legends(operation=context.authority_operation, effective_date=period.end_date)
    with bind_extraction_draft_repository_factory(ports.draft_factory):
        run = run_evidence_batch(
            bucket_id=str(payload.profile_id),
            sources=payload.sources,
            source_directory=Path(payload.source_directory),
            direction=payload.direction,
            evidence_ports=ports.evidence,
            extraction_ports=ports.extraction,
            operation=context.authority_operation,
            legends=legends,
            settings=ports.settings,
            before_item=before_read,
        )
    raise_if_admission_failed()
    if writes.tracker.has_uncertain_write:
        # The batch absorbs a failed row and carries on, so a custody write whose
        # outcome is unknown surfaces here. A result document can only describe
        # certain writes; this refuses before one is built.
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return LedgerEvidenceBatchExecutionResult(
        projection=LedgerEvidenceBatchProjection(
            profile_id=payload.profile_id,
            direction=payload.direction,
            run=LedgerEvidenceBatchSnapshot.from_run(run),
            write_count=writes.count,
            effect=writes.effect(run.any_failed or run.any_deferred),
        )
    )


def _ingestion_work(
    factory: LedgerEvidenceIngestionPortsFactory,
    context: OperationExecutorContext,
    payload: LedgerEvidenceBatchRequest,
    writes: _ConcreteWrites,
    admission: _ReadAdmission,
) -> LedgerEvidenceBatchExecutionResult:
    admission.before_read()
    ports = factory(
        profile_id=payload.profile_id,
        operation=context.authority_operation,
        mutation_writer=writes.write,
        before_read=admission.before_read,
    )
    _require_ports(ports, payload.profile_id, context)
    with validating_governed_facts(context.authority_operation):
        return _execute_batch(payload, ports, writes, context, admission.before_read, admission.raise_if_failed)


async def _settle_ingestion(
    work: Callable[[], LedgerEvidenceBatchExecutionResult],
    task_name: str,
    context: OperationExecutorContext,
    writes: _ConcreteWrites,
    admission: _ReadAdmission,
) -> str:
    try:
        result = await run_with_ledger_commit_fence(work, tracker=writes.tracker, context=context, task_name=task_name)
        admission.raise_if_failed()
        if len(canonical_json_bytes(result.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    except BaseException:
        await settle_export_link_failure(writes.tracker, context)
        raise
    await context.events.effect(result.projection.effect)
    return await context.operands.put(result, written_at=now())


async def _execute(
    factory: LedgerEvidenceIngestionPortsFactory,
    request: OperationRequest[LedgerEvidenceBatchRequest],
    context: OperationExecutorContext,
) -> str:
    payload = _validated_payload(request, context)
    await context.events.phase(request.definition_id)
    writes = _ConcreteWrites()
    admission = _ReadAdmission(request, payload, context, writes)

    def work() -> LedgerEvidenceBatchExecutionResult:
        return _ingestion_work(factory, context, payload, writes, admission)

    settlement = _settle_ingestion(work, request.definition_id, context, writes, admission)
    return await await_cancellation_complete(settlement, task_name=request.definition_id + ".settlement")


class LedgerEvidenceBatchExecutor:
    """Run the canonical bounded batch under exact profile custody."""

    def __init__(self, factory: LedgerEvidenceIngestionPortsFactory) -> None:
        """Bind the canonical exact-profile capability factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[LedgerEvidenceBatchRequest], context: OperationExecutorContext
    ) -> str:
        """Retain the complete batch report and concrete custody receipt."""
        return await _execute(self._factory, request, context)


def resolve_ledger_evidence_ingestion_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human CLI, all-period scope and exact dual-category disclosure."""
    payload = request.payload
    if (
        request.definition_id != LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID
        or type(payload) is not LedgerEvidenceBatchRequest
        or not isinstance(payload, LedgerEvidenceBatchRequest)
        or context.frontend is not OperationFrontendProjection.CLI
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_export_link_access(
        request, context, profile_id=payload.profile_id, periods=frozenset[Period](), requires_human=True
    )


def project_ledger_evidence_ingestion_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the declared human projection matching a certain terminal effect."""
    if type(result) is not LedgerEvidenceBatchExecutionResult or not isinstance(
        result, LedgerEvidenceBatchExecutionResult
    ):
        raise ValueError("invalid evidence ingestion execution result")
    projection = result.projection
    if (
        not terminal_receipt_matches(
            receipt,
            definition_id=LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(projection.profile_id)),
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=projection.effect,
        )
        or len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES
    ):
        raise ValueError("evidence ingestion projection contradicts its terminal receipt")
    return projection


def build_ledger_evidence_ingestion_definitions(
    factory: LedgerEvidenceIngestionPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Declare the human batch ingestion route and its truthful effects."""
    return (
        build_single_phase_definition(
            definition_id=LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidenceBatchRequest,
            result_type=LedgerEvidenceBatchExecutionResult,
            executor_type=LedgerEvidenceBatchExecutor,
            build=lambda: LedgerEvidenceBatchExecutor(factory),
            capabilities=RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        ),
    )


def build_ledger_evidence_ingestion_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind the closed schema and the exact human result policy for the route."""
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=LedgerEvidenceBatchProjection,
            result_projector=project_ledger_evidence_ingestion_result,
            access_resolver=resolve_ledger_evidence_ingestion_access,
        )
        for definition in definitions
    )
