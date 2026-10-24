"""CLI composition for the ledger LLM classification application port."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

import httpx

from ..adapters.inbound.einvoice.shape import probe_document_shape
from ..adapters.outbound.llm.errors import LLMCacheError, LLMProviderError
from ..adapters.outbound.llm.models import MultimodalImageInput
from ..adapters.outbound.llm.providers.local import rasterise_pdf_pages_to_base64_png
from ..adapters.outbound.llm.role_fitness import probe_text_extraction_fitness
from ..adapters.outbound.llm.text_classifier import LocalTextLLMClassifier
from ..adapters.outbound.llm.vision_classifier import LocalVisionLLMClassifier
from ..adapters.persistence.llm.run_records import LLMRunRecord, LLMRunRecorder
from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.ledger.evidence import PurchaseInvoiceEvidenceService
from ..application.ledger.evidence_errors import (
    PurchaseInvoiceEvidenceReaderError,
    evidence_reader_refusal_key,
)
from ..application.ledger.evidence_input import (
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ..application.ledger.evidence_input_ports import EvidenceInputPorts
from ..application.ledger.evidence_reference import (
    find_bytes_bearing_evidence_record,
    refuse_reference_without_document_bytes,
)
from ..application.ledger.llm_classification_ports import (
    EvidenceImage,
    LLMClassificationPorts,
    ResolvedEvidenceInput,
)
from ..application.ledger.preconditions import LedgerPreconditionCondition
from ..application.local_reader import admit_local_reader, probe_local_reader
from ..application.operator_actions.models import PreconditionVerdict
from ..core.config import Settings
from ..core.model_catalogue import ModelRole
from ..core.time.clock import now
from ..domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ..domain.transactions.errors import LLMClassifierError, TransactionValidationError
from ..domain.transactions.llm import LLMClassificationResponse, LLMClassifier, PromptSpec
from ..domain.transactions.models import Transaction
from .adapter_composition import build_ledger_evidence_ports
from .ledger_evidence_extraction_composition import evidence_text_layer_ports


def _reader_unavailable(verdict: PreconditionVerdict) -> PurchaseInvoiceEvidenceReaderError:
    """Return the ledger reader refusal carrying the reader probe's own verdict."""
    return PurchaseInvoiceEvidenceReaderError(
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value,
        translated_message=evidence_reader_refusal_key(verdict),
        precondition_verdict=verdict,
    )


def _require_reader(role: ModelRole, settings: Settings) -> None:
    """Refuse before the read when the runtime cannot run ``role``'s model.

    Asked of the runtime ahead of the read rather than inferred from its
    failure, so a missing model or an unanswering runtime reaches the operator
    as the probe's verdict, naming the setup that supplies it. A model read
    with for the first time on its current weights is measured for fitness
    here, before the read.
    """
    status = admit_local_reader(role, settings, text_probe=probe_text_extraction_fitness)
    if not status.available and status.precondition_verdict is not None:
        raise _reader_unavailable(status.precondition_verdict)


class VisionReader:
    """Convert application evidence values into the adapter's transport values.

    ``settings`` names the vision model this reader loads, including a per-read
    override, so the pre-read check asks about the model the read will use.
    """

    def __init__(self, reader: LocalVisionLLMClassifier, *, settings: Settings) -> None:
        self._reader = reader
        self._settings = settings

    @property
    def decided_by(self) -> str:
        return self._reader.decided_by

    def classify(self, transaction: Transaction, *, evidence_images: tuple[EvidenceImage, ...]):
        _require_reader(ModelRole.VISION_TRANSCRIPTION, self._settings)
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
        _require_reader(ModelRole.VISION_TRANSCRIPTION, self._settings)
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


def _vision_reader_settings(settings: Settings, model: str | None) -> Settings:
    """Return ``settings`` naming the vision model one read loads, honouring a per-read override."""
    if model is None:
        return settings
    return settings.model_copy(update={"cadrumo_llm_ollama_vision_model": model})


class TextReader:
    """Adapt the local text reader to the application classifier protocol."""

    def __init__(self, reader: LocalTextLLMClassifier, *, settings: Settings) -> None:
        self._reader = reader
        self._settings = settings

    @property
    def decided_by(self) -> str:
        return self._reader.decided_by

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        _require_reader(ModelRole.TEXT_EXTRACTION, self._settings)
        return self._reader.classify(transaction, evidence_text=evidence_text)


@dataclass(frozen=True)
class LedgerLlmComposition:
    """Composed LLM classification ports and their event repository."""

    ports: LLMClassificationPorts
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


def compose_ledger_llm(*, bucket_id: str, settings: Settings) -> LedgerLlmComposition:
    """Bind storage, local readers, and run records for one CLI ledger invocation."""
    evidence_ports = build_ledger_evidence_ports(bucket_id=bucket_id)
    evidence_input_ports = EvidenceInputPorts(document_shape_probe=probe_document_shape)
    text_layer_ports = evidence_text_layer_ports()

    def resolve_evidence_input(
        resolved_bucket_id: str, evidence_id: str | None, attachment_ids: tuple[str, ...]
    ) -> ResolvedEvidenceInput:
        store = AttachmentStore(objects=secure_object_repository_for_bucket(resolved_bucket_id, settings))
        record = (
            find_bytes_bearing_evidence_record(
                evidence_id,
                evidence_records=PurchaseInvoiceEvidenceService(ports=evidence_ports).list_all(
                    bucket_id=resolved_bucket_id
                ),
            )
            if evidence_id is not None
            else None
        )
        if record is not None:
            return ResolvedEvidenceInput(
                evidence_input=resolve_purchase_invoice_evidence_input(record, store=store, ports=evidence_input_ports),
                reference=record.evidence_id,
            )
        if attachment_ids:
            return ResolvedEvidenceInput(
                evidence_input=resolve_attachment_evidence_input(
                    attachment_ids[0], store=store, ports=evidence_input_ports
                ),
                reference=attachment_ids[0],
            )
        if evidence_id is None:
            raise TransactionValidationError(
                "evidence resolution reached the document-bytes refusal without an evidence id"
            )
        raise refuse_reference_without_document_bytes(evidence_id)

    def run_reader(role: ModelRole, run: Callable[[], object]) -> object:
        try:
            return run()
        except (httpx.HTTPError, LLMProviderError) as exc:
            # The role being read, not a fixed one: a text read failing on a
            # host that holds only the vision model is still the text reader
            # missing. The readers check before reading; this covers a runtime
            # that stopped or lost the model between that check and the read.
            status = probe_local_reader(role, settings)
            if status.precondition_verdict is not None:
                raise _reader_unavailable(status.precondition_verdict) from exc
            raise LLMClassifierError("ledger.evidence.reader.operation_failed") from exc

    def record_classifier_run(run: Callable[[], object], provider: str) -> object:
        started_at = now()
        clock_start = time.monotonic()
        recorder = LLMRunRecorder()

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

    def make_text_classifier(spec: PromptSpec, /) -> LLMClassifier:
        return TextReader(LocalTextLLMClassifier(spec=spec, settings=settings), settings=settings)

    ports = LLMClassificationPorts(
        resolve_evidence_input=resolve_evidence_input,
        text_layer_ports=text_layer_ports,
        rasterise_pdf=rasterise_pdf_pages_to_base64_png,
        make_text_classifier=make_text_classifier,
        make_vision_classifier=lambda spec, model: VisionReader(
            LocalVisionLLMClassifier(spec=spec, settings=settings, model=model),
            settings=_vision_reader_settings(settings, model),
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
