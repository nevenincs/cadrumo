"""A synthetic in-memory evidence store behind the twelve evidence and attachment doors.

Every door takes its operation's real request model and returns its real public
result model, so the screens are driven through the same validation the
registered operations publish. Each call crosses a thread the way the runtime
door's transport does, and records whether it was made from a Textual worker.
Every document, supplier and identifier here is synthetic.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from pydantic import BaseModel
from textual.pilot import Pilot
from textual.widget import Widget
from textual.widgets import Button, Static
from textual.worker import NoActiveWorker, get_current_worker

from .....application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationId,
    LedgerAttachmentOperationResult,
    LedgerAttachmentProjection,
    LedgerAttachRequest,
    LedgerDetachRequest,
)
from .....application.ledger.attachment_review import AttachmentReviewItem
from .....application.ledger.batch_ingest import (
    BatchItemResult,
    BatchItemStatus,
    BatchRunResult,
    InferencePause,
    UnresolvedBatchSource,
)
from .....application.ledger.evidence import MediaKind
from .....application.ledger.evidence_followup_contracts import (
    CloudDerivedArtefactProjection,
    ConsentedDispatchProjection,
    ConsentWithdrawalSurveyProjection,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from .....application.ledger.evidence_ingestion_contracts import (
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
    LedgerEvidenceBatchSnapshot,
)
from .....application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from .....application.ledger.evidence_read_operation import (
    LedgerEvidenceAutomationRecordProjection,
    LedgerEvidenceQueryProjection,
    LedgerEvidenceQueryRequest,
    LedgerEvidenceRecordProjection,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRefusal,
    LedgerEvidenceViewRequest,
    LedgerEvidenceViewSuccess,
)
from .....application.ledger.evidence_review_summaries import LedgerEvidenceReviewSummaryProjection
from .....application.ledger.invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    InvoiceDraftProjectionV1,
)
from .....application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from .....application.ledger.transaction_projection import LedgerTransactionProjection
from .....application.operations.public_scalar import PublicDecimal
from .....application.review.filter import LedgerReviewStatus
from .....core.confirmation_gate import ConfirmationBlockReason
from .....core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from .....core.operations import OperationEffect
from .....domain.attachments.enums import AttachmentSource
from .....domain.iva.schema import InvoiceKind
from ...account import AccountSessionExpiredError
from ...tests.settling import settle
from ..evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .workspace_fixtures import LEDGER_TX_A, LEDGER_TX_B

EVIDENCE_FILES_PROFILE_ID: Final = UUID("3ee00000-0000-4000-8000-0000000000e3")
EVIDENCE_FILES_REFUSAL_CODE: Final = "REFUSED_LEDGER_EVIDENCE_NOT_FOUND"
EVIDENCE_FILES_REFUSAL_KEY: Final = "errors.refused.refused_ledger_evidence_not_found"
_AT: Final = datetime(2026, 3, 14, 9, 30, tzinfo=UTC)
_EVENT_ID: Final = "e" * 64


def synthetic_digest(seed: str) -> str:
    """A stable 64-character lowercase hex identity derived from ``seed``."""
    return hashlib.sha256(seed.encode()).hexdigest()


def synthetic_evidence_id(index: int) -> str:
    """The sixteen-character evidence identity of the synthetic record ``index``."""
    return f"{index:016x}"


def synthetic_record(index: int, profile_id: UUID = EVIDENCE_FILES_PROFILE_ID) -> LedgerEvidenceRecordProjection:
    """One synthetic purchase-invoice evidence record."""
    digest = synthetic_digest(f"evidence-{index}")
    return LedgerEvidenceRecordProjection(
        evidence_id=synthetic_evidence_id(index),
        bucket_id=str(profile_id),
        source_path=f"factura-{index:04d}.pdf",
        source_sha256=digest,
        attachment_id=digest,
        media_kind=MediaKind.PDF,
        supplier="Suministros Delta SL",
        invoice_number=f"F-2026-{index:04d}",
        invoice_date="2026-03-14",
        taxable_base="100",
        iva_rate="21",
        iva_amount="21",
        notes="",
        created_at=_AT,
        updated_at=_AT,
    )


def synthetic_attachment(index: int) -> AttachmentReviewItem:
    """One synthetic stored attachment no invoice is linked to."""
    digest = synthetic_digest(f"attachment-{index}")
    return AttachmentReviewItem(
        attachment_id=digest,
        sha256=digest,
        mime_type="application/pdf",
        bytes_size=2048 + index,
        source=AttachmentSource.LOCAL_FILE,
        provider_locator="not-exposed",
        captured_at=(_AT + timedelta(minutes=index)).isoformat(),
        linked_invoice_ids=(),
        pending_review=True,
    )


def synthetic_dispatch(index: int, profile_id: UUID = EVIDENCE_FILES_PROFILE_ID) -> ConsentedDispatchProjection:
    """One synthetic consented dispatch of a document to a hosted reader."""
    return ConsentedDispatchProjection(
        profile_bucket_id=str(profile_id),
        evidence_content_address=synthetic_digest(f"evidence-{index}"),
        provider="provider-a",
        model="model-a",
        surface="invoice-extraction",
        recorded_at=_AT + timedelta(hours=index),
    )


def synthetic_review(
    reference: str, profile_id: UUID = EVIDENCE_FILES_PROFILE_ID
) -> LedgerEvidenceReviewViewProjection:
    """One synthetic draft review with a single blocking question."""
    return LedgerEvidenceReviewViewProjection(
        profile_id=profile_id,
        evidence_reference=reference,
        extractor="local-reader",
        drafted_at=_AT,
        draft=InvoiceDraftProjectionV1(
            supplier_name="Suministros Delta SL",
            invoice_number="F-2026-0001",
            invoice_date="2026-03-14",
            taxable_base=PublicDecimal(decimal="100"),
            iva_rate=PublicDecimal(decimal="21"),
            iva_amount=PublicDecimal(decimal="21"),
            grand_total=PublicDecimal(decimal="121"),
            currency="EUR",
            suggested_kind=InvoiceKind.RECEIVED,
        ),
        blockers=(
            ConfirmationBlockerProjectionV1(
                blocker_id="0123456789abcdef",
                reason=ConfirmationBlockReason.AMBIGUOUS_IDENTITY,
                field="supplier_tax_id",
            ),
        ),
    )


def _transaction(transaction_id: str, attachment_ids: tuple[str, ...]) -> LedgerTransactionProjection:
    return LedgerTransactionProjection(
        transaction_id=transaction_id,
        date="2026-03-14",
        booked_date="2026-03-14",
        value_date=None,
        amount="1250.00",
        currency="EUR",
        direction="outgoing",
        counterparty="Suministros Delta SL",
        description="Material de oficina",
        business_classification="business",
        business_pct=None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        irpf_category=None,
        m210_income_classification=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        purchase_invoice_evidence_id=None,
        invoice_id=None,
        attachment_ids=attachment_ids,
        notes="",
        lifecycle_state="active",
        classified_by="manual",
        classified_at=None,
        classification_reason="",
        classification_confidence=None,
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at=_AT.isoformat(),
        modified_at=_AT.isoformat(),
    )


@dataclass
class MemoryEvidenceFilesStore:
    """The profile's synthetic evidence, attachments, consent history and drafts."""

    profile_id: UUID = EVIDENCE_FILES_PROFILE_ID
    records: dict[str, LedgerEvidenceRecordProjection] = field(default_factory=dict)
    attachments: dict[str, AttachmentReviewItem] = field(default_factory=dict)
    transactions: dict[str, tuple[str, ...]] = field(default_factory=lambda: {LEDGER_TX_A: (), LEDGER_TX_B: ()})
    dispatches: list[ConsentedDispatchProjection] = field(default_factory=list)
    artefacts: list[CloudDerivedArtefactProjection] = field(default_factory=list)
    drafts: dict[str, LedgerEvidenceReviewViewProjection] = field(default_factory=dict)
    batch_documents: tuple[tuple[str, BatchItemStatus], ...] = ()
    batch_unreadable: tuple[str, ...] = ()
    batch_pause: InferencePause | None = None
    """The pause that closed the batch's reading, as the run reports it."""
    expired: bool = False
    refusing: set[str] = field(default_factory=set)
    """Door names that answer with the store's typed refusal."""
    requests: list[BaseModel] = field(default_factory=list)
    calls: list[tuple[str, bool]] = field(default_factory=list)
    """Each door call by name and whether it was made from a Textual worker."""
    transports: list[tuple[str, bool]] = field(default_factory=list)
    """Each transport crossing by name and whether it ran on an event-loop thread."""

    def seed_records(self, count: int) -> None:
        """Add ``count`` synthetic evidence records."""
        for index in range(1, count + 1):
            record = synthetic_record(index, self.profile_id)
            self.records[record.evidence_id] = record

    def seed_attachments(self, count: int) -> None:
        """Add ``count`` synthetic pending attachments."""
        for index in range(1, count + 1):
            item = synthetic_attachment(index)
            self.attachments[item.attachment_id] = item

    def seed_consent(self, count: int) -> None:
        """Add ``count`` synthetic consented dispatches and one hosted-reader draft for each."""
        for index in range(1, count + 1):
            self.dispatches.append(synthetic_dispatch(index, self.profile_id))
            self.artefacts.append(
                CloudDerivedArtefactProjection(
                    evidence_reference=synthetic_evidence_id(index),
                    provenance_stamp="hosted-reader",
                    transport="https",
                    drafted_at=_AT + timedelta(hours=index, minutes=5),
                )
            )

    # The twelve operations, applied to the store with their real request and result models.

    def query(self, request: LedgerEvidenceQueryRequest) -> LedgerEvidenceQueryProjection:
        rows = tuple(
            LedgerEvidenceAutomationRecordProjection.from_person_projection(record)
            for record in sorted(self.records.values(), key=lambda item: item.evidence_id)
            if request.evidence_id is None or record.evidence_id == request.evidence_id
        )
        return LedgerEvidenceQueryProjection(
            profile_id=self.profile_id, evidence_id=request.evidence_id, count=len(rows), rows=rows
        )

    def view(self, request: LedgerEvidenceViewRequest) -> LedgerEvidenceViewProjection:
        record = self.records.get(request.evidence_id)
        if record is None:
            return LedgerEvidenceViewProjection(profile_id=self.profile_id, outcome=LedgerEvidenceViewRefusal())
        return LedgerEvidenceViewProjection(
            profile_id=self.profile_id, outcome=LedgerEvidenceViewSuccess(record=record)
        )

    def update(self, request: LedgerEvidenceUpdateRequest) -> LedgerEvidenceUpdateProjection:
        current = self.records[request.evidence_id]
        changes = {name: getattr(request.patch, name) for name in request.patch_fields}
        changed = any(getattr(current, name) != value for name, value in changes.items())
        updated = (
            current.model_copy(update={**changes, "updated_at": current.updated_at + timedelta(days=1)})
            if changed
            else current
        )
        self.records[request.evidence_id] = updated
        return LedgerEvidenceUpdateProjection(
            profile_id=self.profile_id, record=updated, bucket_event_ids=(_EVENT_ID,) if changed else ()
        )

    def remove(self, request: LedgerEvidenceRemoveRequest) -> LedgerEvidenceRemoveProjection:
        record = self.records.pop(request.evidence_id)
        return LedgerEvidenceRemoveProjection(profile_id=self.profile_id, record=record, bucket_event_ids=(_EVENT_ID,))

    def batch(self, request: LedgerEvidenceBatchRequest) -> LedgerEvidenceBatchProjection:
        items = []
        for name, status in self.batch_documents:
            address = synthetic_digest(f"batch-{name}")
            refused = status == "refused"
            items.append(
                BatchItemResult(
                    content_address=address,
                    identity=f"{address}:{request.direction.value}",
                    direction=request.direction,
                    source_name=name,
                    status=status,
                    refusal_code="unsupported_document" if refused else None,
                    refusal_verdict=ledger_no_recovery_verdict(
                        LedgerPreconditionCondition.EVIDENCE_FILE_READABLE,
                        facts={"source_name": name, "file_readable": True},
                    )
                    if refused
                    else None,
                    needed_inference=False,
                )
            )
        unresolved = tuple(
            UnresolvedBatchSource(
                source_name=f"{request.source_directory}/{name}",
                refusal_code="unreadable_source",
                refusal_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.EVIDENCE_FILE_READABLE,
                    facts={"source_name": name, "file_readable": False},
                ),
            )
            for name in self.batch_unreadable
        )
        run = BatchRunResult(
            items=tuple(sorted(items, key=lambda item: item.content_address)),
            unresolved=unresolved,
            inference_pause=self.batch_pause,
        )
        writes = sum(1 for item in run.items if item.status in {"ingested", "pending_review"})
        incomplete = run.any_failed or run.any_deferred
        effect = (
            OperationEffect.NONE if writes == 0 else OperationEffect.PARTIAL if incomplete else OperationEffect.UPDATED
        )
        return LedgerEvidenceBatchProjection(
            profile_id=self.profile_id,
            write_count=writes,
            effect=effect,
            direction=request.direction,
            run=LedgerEvidenceBatchSnapshot.from_run(run),
        )

    def attachment_queue(
        self, _request: LedgerEvidenceAttachmentQueueRequest
    ) -> LedgerEvidenceAttachmentQueueProjection:
        rows = tuple(item for _key, item in sorted(self.attachments.items()) if item.pending_review)
        return LedgerEvidenceAttachmentQueueProjection(profile_id=self.profile_id, count=len(rows), rows=rows)

    def attachment_view(self, request: LedgerEvidenceAttachmentViewRequest) -> LedgerEvidenceAttachmentViewProjection:
        return LedgerEvidenceAttachmentViewProjection(
            profile_id=self.profile_id, item=self.attachments[request.attachment_id]
        )

    def consent_list(self, _request: LedgerEvidenceConsentListRequest) -> LedgerEvidenceConsentListProjection:
        return LedgerEvidenceConsentListProjection(
            profile_id=self.profile_id,
            survey=ConsentWithdrawalSurveyProjection(
                consented_dispatches=tuple(self.dispatches), cloud_derived_artefacts=tuple(self.artefacts)
            ),
        )

    def review_view(self, request: LedgerEvidenceReviewViewRequest) -> LedgerEvidenceReviewViewProjection:
        return self.drafts[request.evidence_reference]

    def review_summary(self, request: LedgerEvidenceReviewViewRequest) -> LedgerEvidenceReviewSummaryProjection:
        return LedgerEvidenceReviewSummaryProjection.from_review_view(self.drafts[request.evidence_reference])

    def _attachment_result(
        self, operation_id: LedgerAttachmentOperationId, transaction_id: str, attached: tuple[str, ...], changed: bool
    ) -> LedgerAttachmentOperationResult:
        return LedgerAttachmentOperationResult(
            outcome="updated",
            profile_id=self.profile_id,
            operation_id=operation_id,
            result=LedgerAttachmentProjection(
                profile_id=self.profile_id,
                operation_id=operation_id,
                transaction=_transaction(transaction_id, attached),
                review_status=LedgerReviewStatus.PENDING,
                bucket_event_ids=(_EVENT_ID,) if changed else (),
            ),
        )

    def _refused_attachment(
        self, operation_id: LedgerAttachmentOperationId, message: str
    ) -> LedgerAttachmentOperationResult:
        return LedgerAttachmentOperationResult(
            outcome="validation_error",
            profile_id=self.profile_id,
            operation_id=operation_id,
            validation_messages=(message,),
        )

    def attach(self, request: LedgerAttachRequest) -> LedgerAttachmentOperationResult:
        unknown = [item for item in request.attachment_ids if item not in self.attachments]
        if unknown:
            return self._refused_attachment(LEDGER_ATTACH_OPERATION_DEFINITION_ID, "attachment not found")
        current = self.transactions[request.transaction_id]
        attached = tuple(dict.fromkeys((*current, *request.attachment_ids)))
        self.transactions[request.transaction_id] = attached
        for item in request.attachment_ids:
            self.attachments[item] = self.attachments[item].model_copy(update={"pending_review": False})
        return self._attachment_result(
            LEDGER_ATTACH_OPERATION_DEFINITION_ID, request.transaction_id, attached, attached != current
        )

    def detach(self, request: LedgerDetachRequest) -> LedgerAttachmentOperationResult:
        current = self.transactions[request.transaction_id]
        if any(item not in current for item in request.attachment_ids):
            return self._refused_attachment(LEDGER_DETACH_OPERATION_DEFINITION_ID, "attachment is not linked")
        attached = tuple(item for item in current if item not in request.attachment_ids)
        self.transactions[request.transaction_id] = attached
        return self._attachment_result(LEDGER_DETACH_OPERATION_DEFINITION_ID, request.transaction_id, attached, True)

    def doors(self) -> LedgerEvidenceFilesDoorsV1:
        """The twelve doors over this store."""
        return LedgerEvidenceFilesDoorsV1(
            query=MemoryEvidenceFilesDoor(self, "query", self.query),
            view=MemoryEvidenceFilesDoor(self, "view", self.view),
            update=MemoryEvidenceFilesDoor(self, "update", self.update),
            remove=MemoryEvidenceFilesDoor(self, "remove", self.remove),
            batch=MemoryEvidenceFilesDoor(self, "batch", self.batch),
            attachment_queue=MemoryEvidenceFilesDoor(self, "attachment_queue", self.attachment_queue),
            attachment_view=MemoryEvidenceFilesDoor(self, "attachment_view", self.attachment_view),
            consent_list=MemoryEvidenceFilesDoor(self, "consent_list", self.consent_list),
            review_view=MemoryEvidenceFilesDoor(self, "review_view", self.review_view),
            review_summary=MemoryEvidenceFilesDoor(self, "review_summary", self.review_summary),
            attach=MemoryEvidenceFilesDoor(self, "attach", self.attach),
            detach=MemoryEvidenceFilesDoor(self, "detach", self.detach),
        )

    def requests_of[RequestT: BaseModel](self, request_type: type[RequestT]) -> list[RequestT]:
        """Every request of one operation the doors received, oldest first."""
        return [request for request in self.requests if isinstance(request, request_type)]


class MemoryEvidenceFilesDoor[RequestT: BaseModel, ResultT: BaseModel]:
    """One door over the store: the request crosses a thread, as the runtime door's transport does."""

    def __init__(self, store: MemoryEvidenceFilesStore, name: str, apply: Callable[[RequestT], ResultT]) -> None:
        """Bind the store, the door's name and the operation it applies."""
        self._store = store
        self.name = name
        self._apply = apply

    @property
    def profile_id(self) -> UUID:
        """The synthetic profile the store belongs to."""
        return self._store.profile_id

    async def __call__(self, request: RequestT) -> ResultT:
        """Apply one request off the event loop, or answer with the store's refusal or a lost session."""
        try:
            get_current_worker()
        except NoActiveWorker:
            in_worker = False
        else:
            in_worker = True
        self._store.calls.append((self.name, in_worker))
        if getattr(request, "profile_id", None) != self._store.profile_id:
            raise AssertionError("a request named another profile")
        self._store.requests.append(request)
        return await asyncio.to_thread(self._transport, request)

    def _transport(self, request: RequestT) -> ResultT:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_loop = False
        else:
            on_loop = True
        self._store.transports.append((self.name, on_loop))
        if self._store.expired:
            raise AccountSessionExpiredError()
        if self.name in self._store.refusing:
            error: CadrumoError = RecordedRegisteredError(
                EVIDENCE_FILES_REFUSAL_CODE, translated_message=EVIDENCE_FILES_REFUSAL_KEY
            )
            raise error
        return self._apply(request)


async def press(pilot: Pilot[None], button_id: str) -> None:
    """Press one button on the screen shown now, then settle."""
    pilot.app.screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


def text_of(screen: Widget, selector: str) -> str:
    """The text a static line shows."""
    return str(screen.query_one(selector, Static).render())


__all__ = [
    "EVIDENCE_FILES_PROFILE_ID",
    "EVIDENCE_FILES_REFUSAL_CODE",
    "EVIDENCE_FILES_REFUSAL_KEY",
    "MemoryEvidenceFilesDoor",
    "MemoryEvidenceFilesStore",
    "press",
    "synthetic_attachment",
    "synthetic_digest",
    "synthetic_dispatch",
    "synthetic_evidence_id",
    "synthetic_record",
    "synthetic_review",
    "text_of",
]
