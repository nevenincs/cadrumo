"""CLI composition for the ledger LLM classification application port."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

import httpx

from ...adapters.outbound.llm.errors import LLMCacheError, LLMProviderError
from ...adapters.outbound.llm.models import MultimodalImageInput
from ...adapters.outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png
from ...adapters.outbound.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ...adapters.outbound.llm.text_classifier import LocalTextLLMClassifier
from ...adapters.outbound.llm.vision_classifier import LocalVisionLLMClassifier
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ...application.ledger.evidence_input import (
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ...application.ledger.evidence_reference import (
    find_bytes_bearing_evidence_record,
    refuse_reference_without_document_bytes,
)
from ...application.ledger.llm_classification_ports import (
    EvidenceImage,
    LLMClassificationPorts,
    ResolvedEvidenceInput,
)
from ...application.ledger.preconditions import LedgerPreconditionCondition
from ...application.provisioning import probe_ollama_vision
from ...core.config import Settings
from ...core.time.clock import now
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.transactions.errors import LLMClassifierError, TransactionValidationError
from ...domain.transactions.models import Transaction


class _VisionReader:
    """Convert application evidence values into the adapter's transport values."""

    def __init__(self, reader: LocalVisionLLMClassifier) -> None:
        self._reader = reader

    @property
    def decided_by(self) -> str:
        return self._reader.decided_by

    def classify(self, transaction: Transaction, *, evidence_images: tuple[EvidenceImage, ...]):
        return self._reader.classify(
            transaction,
            evidence_images=tuple(
                MultimodalImageInput(
                    content_sha256=image.content_sha256,
                    base64_data=image.base64_data,
                    media_type=image.media_type,
                )
                for image in evidence_images
            ),
        )

    def propose_split(self, transaction: Transaction, *, evidence_images: tuple[EvidenceImage, ...]):
        return self._reader.propose_split(
            transaction,
            evidence_images=tuple(
                MultimodalImageInput(
                    content_sha256=image.content_sha256,
                    base64_data=image.base64_data,
                    media_type=image.media_type,
                )
                for image in evidence_images
            ),
        )


@dataclass(frozen=True)
class LedgerLlmComposition:
    ports: LLMClassificationPorts
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


def compose_ledger_llm(*, bucket_id: str, settings: Settings) -> LedgerLlmComposition:
    """Bind storage, local readers, and telemetry for one CLI ledger invocation."""

    def resolve_evidence_input(
        resolved_bucket_id: str, evidence_id: str | None, attachment_ids: tuple[str, ...]
    ) -> ResolvedEvidenceInput:
        store = AttachmentStore(objects=secure_object_repository_for_bucket(resolved_bucket_id, settings))
        record = (
            find_bytes_bearing_evidence_record(
                evidence_id,
                evidence_records=PurchaseInvoiceEvidenceService(settings=settings).list_all(
                    bucket_id=resolved_bucket_id
                ),
            )
            if evidence_id is not None
            else None
        )
        if record is not None:
            return ResolvedEvidenceInput(
                evidence_input=resolve_purchase_invoice_evidence_input(record, store=store),
                reference=record.evidence_id,
            )
        if attachment_ids:
            return ResolvedEvidenceInput(
                evidence_input=resolve_attachment_evidence_input(attachment_ids[0], store=store),
                reference=attachment_ids[0],
            )
        if evidence_id is None:
            raise TransactionValidationError(
                "evidence resolution reached the document-bytes refusal without an evidence id"
            )
        raise refuse_reference_without_document_bytes(evidence_id)

    def run_reader(run: Callable[[], object]) -> object:
        try:
            return run()
        except (httpx.HTTPError, LLMProviderError) as exc:
            status = probe_ollama_vision(settings)
            if status.precondition_verdict is not None:
                raise PurchaseInvoiceEvidenceInputError(
                    LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value,
                    precondition_verdict=status.precondition_verdict,
                ) from exc
            raise LLMClassifierError("ledger.evidence.reader.operation_failed") from exc

    def record_classifier_run(run: Callable[[], object], provider: str) -> object:
        started_at = now()
        clock_start = time.monotonic()
        recorder = LLMRunTelemetryRecorder()

        def record(succeeded: bool, error_kind: str) -> None:
            try:
                recorder.record(
                    LLMRunRecord(
                        run_id=uuid4().hex,
                        caller="cadrumo.application.ledger.llm_classification",
                        duration_ms=max(0, round((time.monotonic() - clock_start) * 1000)),
                        succeeded=succeeded,
                        error_kind=error_kind,
                        started_at=started_at,
                        provider=provider,
                    )
                )
            except LLMCacheError:
                return

        try:
            result = run()
        except Exception as exc:
            record(False, type(exc).__name__)
            raise
        record(True, "")
        return result

    ports = LLMClassificationPorts(
        resolve_evidence_input=resolve_evidence_input,
        rasterise_pdf=rasterise_pdf_pages_to_base64_png,
        make_text_classifier=lambda spec: LocalTextLLMClassifier(spec=spec, settings=settings),
        make_vision_classifier=lambda spec, model: _VisionReader(
            LocalVisionLLMClassifier(spec=spec, settings=settings, model=model)
        ),
        run_reader=run_reader,
        record_classifier_run=record_classifier_run,
    )
    return LedgerLlmComposition(
        ports=ports,
        bucket_event_repository=BucketEventHistoryRepository(
            objects=secure_object_repository_for_bucket(bucket_id, settings)
        ),
    )


__all__ = ["LedgerLlmComposition", "compose_ledger_llm"]
