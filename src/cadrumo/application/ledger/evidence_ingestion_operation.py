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
from typing import Annotated, override
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes
from ...core.identity.digest import ContentDigest
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
from ...domain.attachments.enums import AttachmentKind, AttachmentSource, DocumentLinkSource
from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.regime_legend import resolve_regime_legends
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
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicNamedScalar, project_facts, restore_facts
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..review.filter import LedgerReviewStatus
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..runtime.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_manual import attach_manual_transaction_evidence, ledger_transaction_result_payload
from .attachment_mutation_operation import LedgerAttachmentStaleRevisionProjection
from .batch_ingest import (
    BatchItemResult,
    BatchItemStatus,
    BatchRunResult,
    InferencePause,
    UnresolvedBatchSource,
    run_evidence_batch,
)
from .commit_fence import LedgerCommitAttemptTracker, TrackedLedgerTransactionRepository, run_with_ledger_commit_fence
from .evidence_ingestion_operation_ports import LedgerEvidenceIngestionPorts, LedgerEvidenceIngestionPortsFactory
from .evidence_port_identity import require_exact_evidence_ports
from .evidence_sweep import EvidenceSweepRefusal, sweep_evidence_folder
from .evidence_sweep_ports import EvidenceSweepDocument
from .export_link_operation_ports import (
    require_export_link_profile,
    resolve_export_link_access,
    settle_export_link_failure,
)
from .extraction_draft_store import bind_extraction_draft_repository_factory
from .id_resolution import resolve_transaction_id
from .invoice_extraction_authority import default_invoice_extraction_period
from .transaction_projection import LedgerTransactionProjection

LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID = "ledger.evidence.batch"
LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID = "ledger.evidence.pull"
LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID = "ledger.evidence.pull_all"
_IDS = (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
)
_Path = Annotated[str, Field(min_length=1, max_length=4096)]
_Reference = Annotated[str, Field(min_length=1, max_length=SUBMISSION_PAYLOAD_MAX_BYTES)]
_Note = Annotated[str, Field(max_length=SUBMISSION_PAYLOAD_MAX_BYTES)]
_Actor = Annotated[str, Field(min_length=1, max_length=SUBMISSION_PAYLOAD_MAX_BYTES)]
_Prefix = Annotated[str, Field(min_length=1, max_length=64)]


class LedgerEvidenceBatchRequest(BaseModel):
    """Local source references kept exclusively in encrypted operand custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    sources: Annotated[tuple[_Path, ...], Field(min_length=1)]
    source_directory: _Path
    direction: InvoiceKind

    @model_validator(mode="after")
    def _absolute_directory(self) -> LedgerEvidenceBatchRequest:
        if not Path(self.source_directory).is_absolute():
            raise ValueError("source directory must be absolute")
        return self


class LedgerEvidencePullRequest(BaseModel):
    """Human-supplied document reference and target ledger handle."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    transaction_id: _Prefix
    source: DocumentLinkSource
    reference: _Reference
    note: _Note = ""
    actor: _Actor | None = None


class LedgerEvidencePullAllRequest(BaseModel):
    """Human-supplied folder reference and retained attachment annotation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    folder: _Reference
    note: _Note = ""


class LedgerEvidenceBatchItemSnapshot(BaseModel):
    """Lossless canonical row with a closed precondition projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    content_address: ContentDigest
    identity: str
    direction: InvoiceKind
    source_name: str
    status: BatchItemStatus
    refusal_code: str | None
    refusal_verdict: PreconditionVerdictSnapshot | None
    needed_inference: bool

    @classmethod
    def from_item(cls, item: BatchItemResult) -> LedgerEvidenceBatchItemSnapshot:
        """Copy canonical identity and outcome without exception text."""
        return cls(
            **item.model_dump(exclude={"refusal_verdict"}),
            refusal_verdict=PreconditionVerdictSnapshot.from_verdict(item.refusal_verdict)
            if item.refusal_verdict is not None
            else None,
        )

    def to_item(self) -> BatchItemResult:
        """Restore canonical row invariants for the existing human presenter."""
        return BatchItemResult(
            **self.model_dump(exclude={"refusal_verdict"}),
            refusal_verdict=self.refusal_verdict.to_verdict() if self.refusal_verdict is not None else None,
        )

    @model_validator(mode="after")
    def _canonical(self) -> LedgerEvidenceBatchItemSnapshot:
        self.to_item()
        return self


class LedgerEvidenceUnresolvedSnapshot(BaseModel):
    """An unreadable source retains its exact canonical refusal facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    source_name: str
    refusal_code: str
    refusal_verdict: PreconditionVerdictSnapshot


class LedgerEvidenceInferencePauseSnapshot(BaseModel):
    """Canonical inference admission facts represented as immutable scalars."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    facts: tuple[PublicNamedScalar, ...]
    precondition_verdict: PreconditionVerdictSnapshot


class LedgerEvidenceBatchSnapshot(BaseModel):
    """Complete ordered batch result; canonical service derives all summaries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    items: tuple[LedgerEvidenceBatchItemSnapshot, ...]
    unresolved: tuple[LedgerEvidenceUnresolvedSnapshot, ...]
    inference_pause: LedgerEvidenceInferencePauseSnapshot | None

    @classmethod
    def from_run(cls, run: BatchRunResult) -> LedgerEvidenceBatchSnapshot:
        """Project every original row and inference fact without truncation."""
        pause = run.inference_pause
        return cls(
            items=tuple(LedgerEvidenceBatchItemSnapshot.from_item(item) for item in run.items),
            unresolved=tuple(
                LedgerEvidenceUnresolvedSnapshot(
                    source_name=row.source_name,
                    refusal_code=row.refusal_code,
                    refusal_verdict=PreconditionVerdictSnapshot.from_verdict(row.refusal_verdict),
                )
                for row in run.unresolved
            ),
            inference_pause=LedgerEvidenceInferencePauseSnapshot(
                facts=project_facts(pause.facts),
                precondition_verdict=PreconditionVerdictSnapshot.from_verdict(pause.precondition_verdict),
            )
            if pause is not None
            else None,
        )

    def to_run(self) -> BatchRunResult:
        """Restore the canonical service report and its existing count semantics."""
        pause = self.inference_pause
        return BatchRunResult(
            items=tuple(item.to_item() for item in self.items),
            unresolved=tuple(
                UnresolvedBatchSource(
                    source_name=row.source_name,
                    refusal_code=row.refusal_code,
                    refusal_verdict=row.refusal_verdict.to_verdict(),
                )
                for row in self.unresolved
            ),
            inference_pause=InferencePause.model_validate(
                {
                    "facts": restore_facts(pause.facts),
                    "precondition_verdict": pause.precondition_verdict.to_verdict(),
                }
            )
            if pause is not None
            else None,
        )

    @model_validator(mode="after")
    def _canonical(self) -> LedgerEvidenceBatchSnapshot:
        self.to_run()
        return self


class _WriteReceipt(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    write_count: int = Field(ge=0)
    effect: OperationEffect

    @model_validator(mode="after")
    def _write_truth(self) -> _WriteReceipt:
        if self.effect not in {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL}:
            raise ValueError("successful evidence results require certain concrete writer outcomes")
        if (self.write_count == 0) != (self.effect is OperationEffect.NONE):
            raise ValueError("evidence effect contradicts its concrete writer count")
        return self


class LedgerEvidenceBatchProjection(_WriteReceipt):
    """Whole protected batch report and actual custody write receipt."""

    direction: InvoiceKind
    run: LedgerEvidenceBatchSnapshot

    @model_validator(mode="after")
    def _direction(self) -> LedgerEvidenceBatchProjection:
        if any(row.direction is not self.direction for row in self.run.items):
            raise ValueError("batch row belongs to another declared direction")
        return self


class LedgerEvidencePullProjection(_WriteReceipt):
    """Full canonical ledger mutation result after document custody and linking."""

    requested_transaction_id: _Prefix
    transaction_id: ContentDigest
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    bucket_event_ids: tuple[str, ...]
    stale_finalized_revisions: tuple[LedgerAttachmentStaleRevisionProjection, ...]

    @model_validator(mode="after")
    def _identity(self) -> LedgerEvidencePullProjection:
        if self.transaction.transaction_id != self.transaction_id or self.effect is not OperationEffect.UPDATED:
            raise ValueError("document pull result contradicts its transaction or writer receipt")
        return self


class LedgerEvidencePullAllFileSnapshot(BaseModel):
    """One canonical sweep row; source metadata stays in human result custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    file_id: str
    name: str
    mime_type: str
    fetched: bool
    attachment_id: ContentDigest | None
    refusal_reason: EvidenceSweepRefusal | None

    @model_validator(mode="after")
    def _outcome(self) -> LedgerEvidencePullAllFileSnapshot:
        if self.fetched != (self.attachment_id is not None) or self.fetched == (self.refusal_reason is not None):
            raise ValueError("sweep row must be either fetched or refused")
        return self


class LedgerEvidencePullAllProjection(_WriteReceipt):
    """Complete canonical ordered sweep and its derived counts."""

    folder_id: str
    total_documents: int = Field(ge=0)
    fetched_count: int = Field(ge=0)
    refused_count: int = Field(ge=0)
    skipped_non_document_count: int = Field(ge=0)
    files: tuple[LedgerEvidencePullAllFileSnapshot, ...]

    @model_validator(mode="after")
    def _counts(self) -> LedgerEvidencePullAllProjection:
        if (
            self.total_documents != len(self.files)
            or self.fetched_count != sum(row.fetched for row in self.files)
            or self.refused_count != sum(not row.fetched for row in self.files)
        ):
            raise ValueError("sweep counts must cover its exact ordered rows")
        return self


class LedgerEvidenceBatchExecutionResult(BaseModel):
    """Encrypted batch execution document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerEvidenceBatchProjection


class LedgerEvidencePullExecutionResult(BaseModel):
    """Encrypted single-document execution document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerEvidencePullProjection


class LedgerEvidencePullAllExecutionResult(BaseModel):
    """Encrypted folder-sweep execution document."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerEvidencePullAllProjection


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


async def _execute[RequestT: LedgerEvidenceBatchRequest | LedgerEvidencePullRequest | LedgerEvidencePullAllRequest](
    factory: LedgerEvidenceIngestionPortsFactory,
    request: OperationRequest[RequestT],
    context: OperationExecutorContext,
) -> str:
    payload = request.payload
    require_export_link_profile(request, context, payload.profile_id)
    expected: dict[type[BaseModel], str] = {
        LedgerEvidenceBatchRequest: LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
        LedgerEvidencePullRequest: LEDGER_EVIDENCE_PULL_OPERATION_DEFINITION_ID,
        LedgerEvidencePullAllRequest: LEDGER_EVIDENCE_PULL_ALL_OPERATION_DEFINITION_ID,
    }
    if type(payload) not in expected or request.definition_id != expected[type(payload)]:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    await context.events.phase(request.definition_id)
    writes = _ConcreteWrites()
    loop = asyncio.get_running_loop()
    admission_failure: BaseException | None = None

    async def admit_read() -> None:
        nonlocal admission_failure
        if admission_failure is not None:
            raise admission_failure
        try:
            async with context.cancellation.irreversible_section():
                require_export_link_profile(request, context, payload.profile_id)
        except BaseException as error:
            admission_failure = error
            writes.tracker.abort()
            raise

    def before_read() -> None:
        asyncio.run_coroutine_threadsafe(admit_read(), loop).result()

    def work() -> (
        LedgerEvidenceBatchExecutionResult | LedgerEvidencePullExecutionResult | LedgerEvidencePullAllExecutionResult
    ):
        before_read()
        ports = factory(
            profile_id=payload.profile_id,
            operation=context.authority_operation,
            mutation_writer=writes.write,
            before_read=before_read,
        )
        _require_ports(ports, payload.profile_id, context)
        with validating_governed_facts(context.authority_operation):
            if isinstance(payload, LedgerEvidenceBatchRequest):
                period = default_invoice_extraction_period()
                legends = resolve_regime_legends(operation=context.authority_operation, effective_date=period.end_date)
                source_directory = Path(payload.source_directory)
                with bind_extraction_draft_repository_factory(ports.draft_factory):
                    run = run_evidence_batch(
                        bucket_id=str(payload.profile_id),
                        sources=payload.sources,
                        source_directory=source_directory,
                        direction=payload.direction,
                        evidence_ports=ports.evidence,
                        extraction_ports=ports.extraction,
                        operation=context.authority_operation,
                        legends=legends,
                        settings=ports.settings,
                        before_item=before_read,
                    )
                if admission_failure is not None:
                    raise admission_failure
                return LedgerEvidenceBatchExecutionResult(
                    projection=LedgerEvidenceBatchProjection(
                        profile_id=payload.profile_id,
                        direction=payload.direction,
                        run=LedgerEvidenceBatchSnapshot.from_run(run),
                        write_count=writes.count,
                        effect=writes.effect(run.any_failed or run.any_deferred),
                    )
                )
            if isinstance(payload, LedgerEvidencePullRequest):
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
                            LedgerAttachmentStaleRevisionProjection.from_blocker(row)
                            for row in result.stale_finalized_revisions
                        ),
                        write_count=writes.count,
                        effect=writes.effect(),
                    )
                )
            if not isinstance(payload, LedgerEvidencePullAllRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            pull_all_payload = payload
            listing = ports.acquisition.list_folder(pull_all_payload.folder)

            def fetch(document: EvidenceSweepDocument) -> str:
                data = ports.acquisition.fetch_folder_document(document)
                reference = f"https://drive.google.com/file/d/{document.file_id}"
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
                        notes=pull_all_payload.note,
                    ),
                )
                return attachment.attachment_id

            sweep = sweep_evidence_folder(documents=listing.documents, fetch=fetch)
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

    async def settle() -> str:
        try:
            result = await run_with_ledger_commit_fence(
                work, tracker=writes.tracker, context=context, task_name=request.definition_id
            )
            if admission_failure is not None:
                raise admission_failure
            if writes.tracker.has_uncertain_write:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            if len(canonical_json_bytes(result.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        except BaseException:
            await settle_export_link_failure(writes.tracker, context)
            raise
        await context.events.effect(result.projection.effect)
        return await context.operands.put(result, written_at=now())

    return await await_cancellation_complete(settle(), task_name=request.definition_id + ".settlement")


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
        zip(_IDS, (LedgerEvidenceBatchRequest, LedgerEvidencePullRequest, LedgerEvidencePullAllRequest), strict=True)
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
        receipt.identity.definition_id != expected[type(result)]
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not projection.effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES
    ):
        raise ValueError("evidence ingestion projection contradicts its terminal receipt")
    return projection


def build_ledger_evidence_ingestion_definitions(
    factory: LedgerEvidenceIngestionPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Declare all three existing human ingestion routes and truthful effects."""
    capabilities = OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.NONE,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset(
            {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
        ),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )
    return (
        OperationDefinition(
            definition_id=_IDS[0],
            request_type=LedgerEvidenceBatchRequest,
            result_type=LedgerEvidenceBatchExecutionResult,
            executor_factory=OperationExecutorFactory(
                request_type=LedgerEvidenceBatchRequest,
                executor_type=LedgerEvidenceBatchExecutor,
                build=lambda: LedgerEvidenceBatchExecutor(factory),
            ),
            phase_codes=(_IDS[0],),
            interaction_kinds=frozenset(),
            capabilities=capabilities,
            reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        ),
        OperationDefinition(
            definition_id=_IDS[1],
            request_type=LedgerEvidencePullRequest,
            result_type=LedgerEvidencePullExecutionResult,
            executor_factory=OperationExecutorFactory(
                request_type=LedgerEvidencePullRequest,
                executor_type=LedgerEvidencePullExecutor,
                build=lambda: LedgerEvidencePullExecutor(factory),
            ),
            phase_codes=(_IDS[1],),
            interaction_kinds=frozenset(),
            capabilities=capabilities,
            reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        ),
        OperationDefinition(
            definition_id=_IDS[2],
            request_type=LedgerEvidencePullAllRequest,
            result_type=LedgerEvidencePullAllExecutionResult,
            executor_factory=OperationExecutorFactory(
                request_type=LedgerEvidencePullAllRequest,
                executor_type=LedgerEvidencePullAllExecutor,
                build=lambda: LedgerEvidencePullAllExecutor(factory),
            ),
            phase_codes=(_IDS[2],),
            interaction_kinds=frozenset(),
            capabilities=capabilities,
            reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        ),
    )


def build_ledger_evidence_ingestion_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind closed schemas and the exact human result policy for every route."""
    result_types: dict[str, type[BaseModel]] = {
        _IDS[0]: LedgerEvidenceBatchProjection,
        _IDS[1]: LedgerEvidencePullProjection,
        _IDS[2]: LedgerEvidencePullAllProjection,
    }
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".request", schema_version=1, model_type=definition.request_type
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".result",
                schema_version=1,
                model_type=result_types[definition.definition_id],
            ),
            access_resolver=resolve_ledger_evidence_ingestion_access,
            result_projector=project_ledger_evidence_ingestion_result,
        )
        for definition in definitions
    )
