"""Human evidence ingestion through one exact-profile worker authority.

Canonical batch and sweep services retain ordering and per-document outcomes.
Only concrete custody writers determine effects; remote reads run outside COMMIT.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import override
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.google_drive_reference import build_google_drive_file_reference
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.errors import AttachmentValidationError
from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
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
from .actions_manual import attach_manual_transaction_evidence, ledger_transaction_result_payload
from .attachment_mutation_operation import LedgerAttachmentStaleRevisionProjection
from .batch_ingest import run_evidence_batch
from .commit_fence import LedgerCommitAttemptTracker, TrackedLedgerTransactionRepository, run_with_ledger_commit_fence
from .evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_INGESTION_OPERATION_IDS,
    LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchExecutionResult,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
    LedgerEvidenceBatchSnapshot,
    LedgerEvidencePullAllExecutionResult,
    LedgerEvidencePullAllFileSnapshot,
    LedgerEvidencePullAllProjection,
    LedgerEvidencePullAllRequest,
    LedgerEvidencePullExecutionResult,
    LedgerEvidencePullProjection,
    LedgerEvidencePullRequest,
)
from .evidence_ingestion_operation_ports import (
    EvidenceAcquisitionListing,
    LedgerEvidenceIngestionPorts,
    LedgerEvidenceIngestionPortsFactory,
)
from .evidence_port_identity import require_exact_evidence_ports
from .evidence_sweep import sweep_evidence_folder
from .evidence_sweep_ports import EvidenceSweepDocument
from .export_link_operation_ports import (
    resolve_export_link_access,
    settle_export_link_failure,
)
from .extraction_draft_store import bind_extraction_draft_repository_factory
from .id_resolution import resolve_transaction_id
from .invoice_extraction_authority import default_invoice_extraction_period
from .transaction_projection import LedgerTransactionProjection

type _IngestionPayload = LedgerEvidenceBatchRequest | LedgerEvidencePullRequest | LedgerEvidencePullAllRequest
type _IngestionResult = (
    LedgerEvidenceBatchExecutionResult | LedgerEvidencePullExecutionResult | LedgerEvidencePullAllExecutionResult
)


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
    if (
        ports.profile_id != request_profile
        or ports.operation is not context.authority_operation
        or ports.actions.operation is not context.authority_operation
        or ports.actions.transaction_repository.bucket_id != str(request_profile)
        or ports.actions.attachment_store is not ports.attachment_store
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_exact_evidence_ports(ports.evidence, bucket_id=str(request_profile))
    if ports.actions.bucket_event_repository is not ports.evidence.bucket_event_repository:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    for repository in (
        ports.actions.invoice_repository,
        ports.actions.work_unit_repository,
        ports.actions.calculation_repository,
    ):
        if getattr(repository, "bucket_id", None) != str(request_profile):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _validated_payload[RequestT: _IngestionPayload](
    request: OperationRequest[RequestT], context: OperationExecutorContext
) -> RequestT:
    payload = request.payload
    require_operation_profile(request, context, payload.profile_id)
    expected: dict[type[BaseModel], str] = {
        LedgerEvidenceBatchRequest: LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
        LedgerEvidencePullRequest: LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
        LedgerEvidencePullAllRequest: LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
    }
    if type(payload) not in expected or request.definition_id != expected[type(payload)]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return payload


class _ReadAdmission[PayloadT: _IngestionPayload]:
    """Bridge synchronous worker reads through the operation's cancellation guard."""

    def __init__(
        self,
        request: OperationRequest[PayloadT],
        payload: PayloadT,
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
    return LedgerEvidenceBatchExecutionResult(
        projection=LedgerEvidenceBatchProjection(
            profile_id=payload.profile_id,
            direction=payload.direction,
            run=LedgerEvidenceBatchSnapshot.from_run(run),
            write_count=writes.count,
            effect=writes.effect(run.any_failed or run.any_deferred),
        )
    )


def _execute_pull(
    payload: LedgerEvidencePullRequest, ports: LedgerEvidenceIngestionPorts, writes: _ConcreteWrites
) -> LedgerEvidencePullExecutionResult:
    repository = ports.actions.transaction_repository
    catalogue = repository.load()
    resolved_id = resolve_transaction_id(
        payload.transaction_id, (row.transaction_id for row in catalogue.transactions.values())
    )
    expected_current = catalogue.get(resolved_id)
    if expected_current is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    source = payload.source.to_attachment_source()
    data = ports.acquisition.fetch(source=source, reference=payload.reference)
    attachment = add_attachment(
        ports.attachment_store,
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=source,
            source_reference=payload.reference,
            mime_type=ports.acquisition.mime_type(payload.reference, data),
            captured_at=now(),
            bucket_id=str(payload.profile_id),
            link_transaction_ids=(resolved_id,),
            metadata={"source": source.value, "source_reference": payload.reference},
            notes=payload.note,
        ),
    )
    result = attach_manual_transaction_evidence(
        bucket_id=str(payload.profile_id),
        transaction_id=resolved_id,
        attachment_ids=(attachment.attachment_id,),
        actor=payload.actor or str(payload.profile_id),
        source_command="aeat app ledger evidence pull",
        expected_current=expected_current,
        ports=replace(
            ports.actions,
            transaction_repository=TrackedLedgerTransactionRepository(repository, writes.tracker),
        ),
    )
    canonical = ledger_transaction_result_payload(result)
    return LedgerEvidencePullExecutionResult(
        projection=LedgerEvidencePullProjection(
            profile_id=payload.profile_id,
            requested_transaction_id=payload.transaction_id,
            transaction_id=canonical.transaction_id,
            transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
            review_status=canonical.review_status,
            bucket_event_ids=result.bucket_event_ids,
            stale_finalized_revisions=tuple(
                LedgerAttachmentStaleRevisionProjection.from_blocker(row) for row in result.stale_finalized_revisions
            ),
            write_count=writes.count,
            effect=writes.effect(),
        )
    )


def _fetch_folder_document(
    payload: LedgerEvidencePullAllRequest,
    listing: EvidenceAcquisitionListing,
    document: EvidenceSweepDocument,
    ports: LedgerEvidenceIngestionPorts,
) -> str:
    try:
        reference = build_google_drive_file_reference(document.file_id)
    except ValueError as error:
        raise AttachmentValidationError("Drive folder entry has an invalid file ID") from error
    data = ports.acquisition.fetch_folder_document(document)
    attachment = add_attachment(
        ports.attachment_store,
        content=AttachmentBytesContent(data=data),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.DRIVE_DOCUMENT,
            source=AttachmentSource.GOOGLE_DRIVE,
            source_reference=reference,
            mime_type=document.mime_type or ports.acquisition.mime_type(document.name, data),
            captured_at=now(),
            bucket_id=str(payload.profile_id),
            metadata={
                "source": AttachmentSource.GOOGLE_DRIVE.value,
                "source_reference": reference,
                "drive_folder_id": listing.folder_id,
                "drive_file_name": document.name,
            },
            notes=payload.note,
        ),
    )
    return attachment.attachment_id


def _execute_pull_all(
    payload: LedgerEvidencePullAllRequest, ports: LedgerEvidenceIngestionPorts, writes: _ConcreteWrites
) -> LedgerEvidencePullAllExecutionResult:
    listing = ports.acquisition.list_folder(payload.folder)
    sweep = sweep_evidence_folder(
        documents=listing.documents,
        fetch=lambda document: _fetch_folder_document(payload, listing, document, ports),
    )
    return LedgerEvidencePullAllExecutionResult(
        projection=LedgerEvidencePullAllProjection(
            profile_id=payload.profile_id,
            folder_id=listing.folder_id,
            total_documents=len(listing.documents),
            fetched_count=sweep.fetched_count,
            refused_count=sweep.refused_count,
            skipped_non_document_count=listing.skipped_non_document_count,
            files=tuple(
                LedgerEvidencePullAllFileSnapshot(
                    file_id=row.file_id,
                    name=row.name,
                    mime_type=row.mime_type,
                    fetched=row.fetched,
                    attachment_id=row.attachment_id,
                    refusal_reason=row.refusal,
                )
                for row in sweep.documents
            ),
            write_count=writes.count,
            effect=writes.effect(bool(sweep.refused_count)),
        )
    )


def _ingestion_work[PayloadT: _IngestionPayload](
    factory: LedgerEvidenceIngestionPortsFactory,
    context: OperationExecutorContext,
    payload: PayloadT,
    writes: _ConcreteWrites,
    admission: _ReadAdmission[PayloadT],
) -> _IngestionResult:
    admission.before_read()
    ports = factory(
        profile_id=payload.profile_id,
        operation=context.authority_operation,
        mutation_writer=writes.write,
        before_read=admission.before_read,
    )
    _require_ports(ports, payload.profile_id, context)
    with validating_governed_facts(context.authority_operation):
        if isinstance(payload, LedgerEvidenceBatchRequest):
            return _execute_batch(payload, ports, writes, context, admission.before_read, admission.raise_if_failed)
        if isinstance(payload, LedgerEvidencePullRequest):
            return _execute_pull(payload, ports, writes)
        if isinstance(payload, LedgerEvidencePullAllRequest):
            return _execute_pull_all(payload, ports, writes)
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


async def _settle_ingestion[PayloadT: _IngestionPayload](
    work: Callable[[], _IngestionResult],
    task_name: str,
    context: OperationExecutorContext,
    writes: _ConcreteWrites,
    admission: _ReadAdmission[PayloadT],
) -> str:
    try:
        result = await run_with_ledger_commit_fence(work, tracker=writes.tracker, context=context, task_name=task_name)
        admission.raise_if_failed()
        if writes.tracker.has_uncertain_write:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        if len(canonical_json_bytes(result.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    except BaseException:
        await settle_export_link_failure(writes.tracker, context)
        raise
    await context.events.effect(result.projection.effect)
    return await context.operands.put(result, written_at=now())


async def _execute[RequestT: _IngestionPayload](
    factory: LedgerEvidenceIngestionPortsFactory,
    request: OperationRequest[RequestT],
    context: OperationExecutorContext,
) -> str:
    payload = _validated_payload(request, context)
    await context.events.phase(request.definition_id)
    writes = _ConcreteWrites()
    admission = _ReadAdmission(request, payload, context, writes)

    def work() -> _IngestionResult:
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


class LedgerEvidencePullExecutor:
    """Acquire one document and apply the canonical ledger attachment mutation."""

    def __init__(self, factory: LedgerEvidenceIngestionPortsFactory) -> None:
        """Bind the canonical exact-profile capability factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[LedgerEvidencePullRequest], context: OperationExecutorContext
    ) -> str:
        """Acquire bytes, preserve provenance and apply canonical attachment lifecycle."""
        return await _execute(self._factory, request, context)


class LedgerEvidencePullAllExecutor:
    """Acquire a canonical ordered folder sweep into exact profile custody."""

    def __init__(self, factory: LedgerEvidenceIngestionPortsFactory) -> None:
        """Bind the canonical exact-profile capability factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[LedgerEvidencePullAllRequest], context: OperationExecutorContext
    ) -> str:
        """Retain every ordered sweep row and settle actual custody outcomes."""
        return await _execute(self._factory, request, context)


def resolve_ledger_evidence_ingestion_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human CLI, all-period scope and exact dual-category disclosure."""
    payload = request.payload
    expected = dict(
        zip(
            LEDGER_EVIDENCE_INGESTION_OPERATION_IDS,
            (LedgerEvidenceBatchRequest, LedgerEvidencePullRequest, LedgerEvidencePullAllRequest),
            strict=True,
        )
    )
    if (
        request.definition_id not in expected
        or type(payload) is not expected[request.definition_id]
        or not isinstance(
            payload, (LedgerEvidenceBatchRequest, LedgerEvidencePullRequest, LedgerEvidencePullAllRequest)
        )
        or context.frontend is not OperationFrontendProjection.CLI
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_export_link_access(
        request, context, profile_id=payload.profile_id, periods=frozenset[Period](), requires_human=True
    )


def project_ledger_evidence_ingestion_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the declared human projection matching a certain terminal effect."""
    expected: dict[type[BaseModel], str] = {
        LedgerEvidenceBatchExecutionResult: LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
        LedgerEvidencePullExecutionResult: LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
        LedgerEvidencePullAllExecutionResult: LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
    }
    if type(result) not in expected or not isinstance(
        result,
        (LedgerEvidenceBatchExecutionResult, LedgerEvidencePullExecutionResult, LedgerEvidencePullAllExecutionResult),
    ):
        raise ValueError("invalid evidence ingestion execution result")
    projection = result.projection
    if (
        not terminal_receipt_matches(
            receipt,
            definition_id=expected[type(result)],
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
    """Declare all three existing human ingestion routes and truthful effects."""
    capabilities = RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES
    return (
        build_single_phase_definition(
            definition_id=LEDGER_EVIDENCE_INGESTION_OPERATION_IDS[0],
            request_type=LedgerEvidenceBatchRequest,
            result_type=LedgerEvidenceBatchExecutionResult,
            executor_type=LedgerEvidenceBatchExecutor,
            build=lambda: LedgerEvidenceBatchExecutor(factory),
            capabilities=capabilities,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        ),
        build_single_phase_definition(
            definition_id=LEDGER_EVIDENCE_INGESTION_OPERATION_IDS[1],
            request_type=LedgerEvidencePullRequest,
            result_type=LedgerEvidencePullExecutionResult,
            executor_type=LedgerEvidencePullExecutor,
            build=lambda: LedgerEvidencePullExecutor(factory),
            capabilities=capabilities,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        ),
        build_single_phase_definition(
            definition_id=LEDGER_EVIDENCE_INGESTION_OPERATION_IDS[2],
            request_type=LedgerEvidencePullAllRequest,
            result_type=LedgerEvidencePullAllExecutionResult,
            executor_type=LedgerEvidencePullAllExecutor,
            build=lambda: LedgerEvidencePullAllExecutor(factory),
            capabilities=capabilities,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        ),
    )


def build_ledger_evidence_ingestion_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind closed schemas and the exact human result policy for every route."""
    result_types: dict[str, type[BaseModel]] = {
        LEDGER_EVIDENCE_INGESTION_OPERATION_IDS[0]: LedgerEvidenceBatchProjection,
        LEDGER_EVIDENCE_INGESTION_OPERATION_IDS[1]: LedgerEvidencePullProjection,
        LEDGER_EVIDENCE_INGESTION_OPERATION_IDS[2]: LedgerEvidencePullAllProjection,
    }
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=result_types[definition.definition_id],
            result_projector=project_ledger_evidence_ingestion_result,
            access_resolver=resolve_ledger_evidence_ingestion_access,
        )
        for definition in definitions
    )
