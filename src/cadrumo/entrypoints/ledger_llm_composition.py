"""CLI composition for the ledger LLM classification application port."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from uuid import uuid4

import httpx

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal, ModelRunRefusalCode, ModelRunTaskKind

from ..adapters.inbound.einvoice.shape import probe_document_shape
from ..adapters.outbound.llm.consent import EvidenceConsentToken, mint_granted_consent_token
from ..adapters.outbound.llm.errors import (
    LLMCacheError,
    LLMConfigError,
    LLMConsentError,
    LLMContentionError,
    LLMProviderError,
)
from ..adapters.outbound.llm.models import MultimodalImageInput
from ..adapters.outbound.llm.pdf_rasterisation import rasterise_pdf_pages_to_base64_png
from ..adapters.outbound.llm.providers.agent import model_run_refusal_error
from ..adapters.outbound.llm.text_classifier import TextLLMClassifier
from ..adapters.outbound.llm.vision_classifier import VisionLLMClassifier
from ..adapters.persistence.llm.run_records import LLMRunRecord, LLMRunRecorder
from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.ledger.classification_job_consent import off_host_consent_refused
from ..application.ledger.classification_job_contracts import LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID
from ..application.ledger.classification_job_ports import ClassificationJobReader, ClassificationJobReaderFactory
from ..application.ledger.classification_job_run import MODEL_RUN_REFUSAL_CONTEXT_KEY
from ..application.ledger.evidence import PurchaseInvoiceEvidenceService
from ..application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
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
from ..application.ledger.off_host_consent_refusal import off_host_consent_required
from ..application.ledger.preconditions import LedgerPreconditionCondition
from ..application.ledger.read_ports import LedgerReadPortsFactory
from ..application.ledger.reading_model_refusal import (
    model_run_refusal_code,
    reader_refusal_locale_key,
    reader_refusal_next_step,
)
from ..application.operations.model_runs import current_model_run_port
from ..application.operator_actions.models import PreconditionVerdict
from ..application.user_profile.capabilities import cloud_evidence_upload_eligible_for_active_profile
from ..core.config import Settings, load_settings
from ..core.model_roles import ModelRole
from ..core.time.clock import now
from ..domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.evidence_consent.grant import ConsentGrantStanding
from ..domain.transactions.classification_job import ClassificationJobConsent, ClassificationJobLane
from ..domain.transactions.errors import LLMClassifierError, TransactionValidationError
from ..domain.transactions.llm import LLMClassificationResponse, LLMClassifier, PromptSpec
from ..domain.transactions.models import Transaction
from .adapter_composition_work_ports import build_ledger_evidence_ports
from .ledger_classification_consent_composition import LedgerClassificationConsentGrants
from .ledger_evidence_extraction_composition import evidence_text_layer_ports


def _reader_unavailable(verdict: PreconditionVerdict) -> PurchaseInvoiceEvidenceReaderError:
    """Return the ledger reader refusal carrying the agent's own verdict."""
    refusal_code = model_run_refusal_code(verdict)
    return PurchaseInvoiceEvidenceReaderError(
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value,
        translated_message=reader_refusal_locale_key(refusal_code),
        precondition_verdict=verdict,
        next_step=reader_refusal_next_step(refusal_code),
    )


class VisionReader:
    """Convert application evidence values into the adapter's transport values."""

    def __init__(self, reader: VisionLLMClassifier) -> None:
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


class TextReader:
    """Adapt the local text reader to the application classifier protocol."""

    def __init__(self, reader: TextLLMClassifier) -> None:
        self._reader = reader

    @property
    def decided_by(self) -> str:
        return self._reader.decided_by

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        return self._reader.classify(transaction, evidence_text=evidence_text)


async def resolve_reading_lane(role: ModelRole, *, task_kind: ModelRunTaskKind | None = None) -> ModelRunLane:
    """Return the lane the agent service would read with for ``role`` doing ``task_kind``.

    The agent service answers with the lane the person set for ``task_kind``, else the one ``role`` reads with,
    as the classification review resolves it.

    The lookup is the running operation's own model-run port; outside an
    operation there is none, and the read is refused as an unreachable service.
    A refused lookup is raised as the ledger's reader refusal with the
    service's verdict, or as the off-host consent refusal with its remedies.
    Nothing is sent to a model.
    """
    port = current_model_run_port()
    answer = (
        ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
        if port is None
        else await port.lookup(role, task_kind=task_kind)
    )
    if isinstance(answer, ModelRunLane):
        return answer
    error = model_run_refusal_error(answer, role=role)
    if isinstance(error, LLMConsentError) and error.terminal_precondition_verdict is not None:
        raise off_host_consent_required(error.terminal_precondition_verdict) from error
    if isinstance(error, LLMConfigError) and error.terminal_precondition_verdict is not None:
        raise _reader_unavailable(error.terminal_precondition_verdict) from error
    raise error


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
        del role
        try:
            return run()
        except LLMConfigError as exc:
            # The agent service's typed refusal -- no selection for the role, a
            # model not installed, a lane that does not take the input -- names
            # the selection or setup action itself. It reaches the operator as
            # it is; no other lane or model is tried.
            verdict = exc.terminal_precondition_verdict
            if verdict is not None:
                raise _reader_unavailable(verdict) from exc
            raise LLMClassifierError("ledger.evidence.reader.operation_failed") from exc
        except LLMConsentError as exc:
            # A read the selected off-host model may not take without consent is
            # neither a fault of the document nor an unavailable reader: it is
            # refused as what it is, with the two remedies it serves.
            consent_verdict = exc.terminal_precondition_verdict
            if consent_verdict is not None:
                raise off_host_consent_required(consent_verdict) from exc
            raise LLMClassifierError("ledger.evidence.reader.operation_failed") from exc
        except (httpx.HTTPError, LLMProviderError) as exc:
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
        return TextReader(TextLLMClassifier(spec=spec, settings=settings))

    ports = LLMClassificationPorts(
        resolve_evidence_input=resolve_evidence_input,
        text_layer_ports=text_layer_ports,
        rasterise_pdf=rasterise_pdf_pages_to_base64_png,
        make_text_classifier=make_text_classifier,
        make_vision_classifier=lambda spec: VisionReader(VisionLLMClassifier(spec=spec, settings=settings)),
        run_reader=run_reader,
        record_classifier_run=record_classifier_run,
    )
    return LedgerLlmComposition(
        ports=ports,
        bucket_event_repository=BucketEventHistoryRepository(
            objects=secure_object_repository_for_bucket(bucket_id, settings)
        ),
    )


def _model_run_failure(code: str) -> LLMClassifierError:
    """One movement's failed model run, naming the agent's refusal code and nothing it read."""
    return LLMClassifierError("ledger.evidence.reader.operation_failed", context={MODEL_RUN_REFUSAL_CONTEXT_KEY: code})


def _typed_run_failures(run: Callable[[], object]) -> Callable[[], object]:
    """Run one classification read, naming why a model run failed so a job records its cause.

    A refusal that concerns the reader or the consent keeps its verdict and is
    refused by the ledger's reader port as it is for a review. A model that does
    not fit in free memory is the reader being unavailable. Any other failed run
    names the agent's refusal code; a reply the parse did not accept passes
    through unchanged.
    """

    def guarded() -> object:
        try:
            return run()
        except LLMContentionError as exc:
            verdict = exc.terminal_precondition_verdict
            if verdict is None:
                raise _model_run_failure(ModelRunRefusalCode.MODEL_DOES_NOT_FIT.value) from exc
            raise _reader_unavailable(verdict) from exc
        except LLMProviderError as exc:
            code = (exc.context or {}).get(MODEL_RUN_REFUSAL_CONTEXT_KEY)
            raise _model_run_failure(code if isinstance(code, str) else ModelRunRefusalCode.RUN_FAILED.value) from exc
        except httpx.TimeoutException as exc:
            raise _model_run_failure(ModelRunRefusalCode.TIMEOUT.value) from exc
        except httpx.HTTPError as exc:
            raise _model_run_failure(ModelRunRefusalCode.RUN_FAILED.value) from exc

    return guarded


def _granted_read_token(
    grants: LedgerClassificationConsentGrants,
    *,
    bucket_id: str,
    lane: ClassificationJobLane,
    consent: ClassificationJobConsent | None,
    job_id: str,
    content_address: str,
) -> EvidenceConsentToken:
    """Mint the consent of one off-host read from the job's grant, checked in the consent ledger now."""
    standing = (
        ConsentGrantStanding.MISSING
        if consent is None
        else grants.standing(bucket_id=bucket_id, lane=lane, consent=consent, job_id=job_id)
    )
    settings = load_settings()
    try:
        return mint_granted_consent_token(
            settings=settings,
            profile_eligible=cloud_evidence_upload_eligible_for_active_profile(settings=settings),
            grant_covers_read=standing is ConsentGrantStanding.VALID,
            surface=LEDGER_CLASSIFY_JOB_RUN_DEFINITION_ID,
            evidence_content_address=content_address,
        )
    except LLMConsentError as exc:
        raise off_host_consent_refused(consent_present=consent is not None, standing=standing) from exc


def classification_job_reader_factory(
    *, settings: Settings, reads: LedgerReadPortsFactory, grants: LedgerClassificationConsentGrants
) -> ClassificationJobReaderFactory:
    """Bind the reader a classification job's run reads with: the review's own classification reader.

    The reader is the one :func:`compose_ledger_llm` composes for a review, with
    each failed model run naming its cause. On a lane that reads off this
    computer each read mints its own consent from the job's grant, checked in
    the consent ledger at that moment and bound to the revision of the movement
    it sends; the dispatch point records the read in the consent ledger before
    anything leaves. A read the grant no longer covers is refused unsent.
    """

    def compose(
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
        lane: ClassificationJobLane,
        consent: ClassificationJobConsent | None,
        job_id: str,
    ) -> ClassificationJobReader:
        llm = compose_ledger_llm(bucket_id=bucket_id, settings=settings).ports
        shared_reader = llm.run_reader

        def run_reader(role: ModelRole, run: Callable[[], object]) -> object:
            return shared_reader(role, _typed_run_failures(run))

        def llm_for(content_address: str) -> LLMClassificationPorts:
            if not lane.reads_off_host:
                return replace(llm, run_reader=run_reader)
            token = _granted_read_token(
                grants, bucket_id=bucket_id, lane=lane, consent=consent, job_id=job_id, content_address=content_address
            )

            def make_text_classifier(spec: PromptSpec, /) -> LLMClassifier:
                return TextReader(TextLLMClassifier(spec=spec, settings=settings, consent_token=token))

            return replace(llm, run_reader=run_reader, make_text_classifier=make_text_classifier)

        return ClassificationJobReader(
            transactions=reads(bucket_id=bucket_id, operation=operation).transaction_repository,
            llm_for=llm_for,
            settings=settings,
        )

    return compose


__all__ = [
    "LedgerLlmComposition",
    "classification_job_reader_factory",
    "compose_ledger_llm",
    "resolve_reading_lane",
]
