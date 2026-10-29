"""Resolve and read evidence for model classification."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.config import Settings
from ...core.document_shape import PDF_CONTAINER_SHAPES
from ...core.errors.hierarchy import InternalInvariantError
from ...core.image_media_type import ImageMediaType, detect_image_media_type
from ...core.logging import get_logger
from ...core.model_roles import ModelRole
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.llm import (
    LLMClassificationResponse,
    LLMClassifier,
    LLMSplitProposer,
    LLMSplitResponse,
    PromptSpec,
)
from ...domain.transactions.models import Transaction
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .evidence_textlayer import extract_evidence_text
from .llm_classification_ports import (
    EvidenceImage,
    LLMClassificationPorts,
    VisionClassifier,
)
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

_logger = get_logger(__name__)

if TYPE_CHECKING:
    pass


# The CLI binary each subprocess provider shells out to. Used by


_SPLIT_NEEDS_IMAGE_EVIDENCE = (
    "proposing a split needs scanned or image evidence for the image-reading model; "
    "this transaction has no readable image evidence to route there"
)


@dataclass(frozen=True)
class ResolvedEvidence:
    """A transaction's linked evidence resolved for a read by role.

    Exactly one read mode is populated: ``text`` for a text-layer PDF (inlined into
    the prompt the text-extraction role reads) or ``images`` for a scan-only PDF /
    image (read in memory by the vision-transcription role). Either role's
    selected lane, when it reads off the host, needs the per-call consent. The
    ``images`` are transient
    FINANCIAL-derived bytes and MUST never be persisted or logged
    (``sensitive-financial-data-secure-storage-only``).
    """

    reference: str
    text: str | None
    images: tuple[EvidenceImage, ...]

    @property
    def is_images(self) -> bool:
        """Whether this evidence routes to the vision-transcription reader."""
        return bool(self.images)


def resolve_llm_evidence(
    transaction: Transaction,
    *,
    bucket_id: str,
    settings: Settings,
    ports: LLMClassificationPorts,
) -> ResolvedEvidence | None:
    """Resolve a transaction's linked evidence to its text or its page images, or ``None``.

    Returns ``None`` when the transaction has no linked evidence. A PDF with a
    text layer yields ``text``, which the text-extraction role reads. A scan-only
    PDF or an image yields base64 ``images``, which the vision-transcription role
    reads, and only while the profile's ``llm_vision`` capability is on. Each
    role is read by an agent run on the lane the service derives for it; a lane
    whose catalogue entry reads off the host refuses without the per-call
    consent. Bytes are read from secure storage into memory only; nothing is
    written to disk (``sensitive-financial-data-secure-storage-only``).

    Raises:
        PurchaseInvoiceEvidenceInputError: When the linked evidence cannot be read
            as a document or image, or image evidence meets a profile whose
            ``llm_vision`` capability is off.
    """
    evidence_id = transaction.purchase_invoice_evidence_id
    attachment_ids = transaction.attachment_ids
    if evidence_id is None and not attachment_ids:
        return None
    resolved = ports.resolve_evidence_input(bucket_id, evidence_id, attachment_ids)
    evidence_input, reference = resolved.evidence_input, resolved.reference
    if evidence_input.document_shape in PDF_CONTAINER_SHAPES:
        try:
            text = extract_evidence_text(evidence_input, text_layer_ports=ports.text_layer_ports)
        except PurchaseInvoiceEvidenceInputError:
            text = ""  # scan-only / no usable text layer -> vision path
        if text:
            return ResolvedEvidence(reference=reference, text=text, images=())
        images = tuple(
            EvidenceImage.from_base64(page, ImageMediaType.PNG) for page in ports.rasterise_pdf(evidence_input.data)
        )
    else:
        # An attachment is whatever format the operator supplied, so the type is
        # detected from the bytes and an unsupported one refuses here rather than
        # travelling to a provider under a guessed label.
        images = (
            EvidenceImage.from_base64(
                base64.b64encode(evidence_input.data).decode("ascii"),
                detect_image_media_type(evidence_input.data),
            ),
        )
    # Only image evidence reaches here. Gate it on the profile's llm_vision
    # capability — opting out disables scanned/image reading entirely (a typed
    # refusal, never a silent skip).
    from ...core.capabilities import ServiceCapability
    from ..user_profile.capabilities import resolve_active_capability

    if not resolve_active_capability(ServiceCapability.LLM_VISION, settings=settings).enabled:
        raise PurchaseInvoiceEvidenceInputError(
            "image reading is disabled for this profile; enable the llm_vision capability to read scanned or image "
            "evidence",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_VISION_CAPABILITY_ENABLED,
                facts={"llm_vision_enabled": False},
            ),
        )
    return ResolvedEvidence(reference=reference, text=None, images=images)


def classify_with_evidence(
    transaction: Transaction,
    evidence: ResolvedEvidence | None,
    *,
    text_classifier: LLMClassifier | None,
    spec: PromptSpec,
    vision_classifier: VisionClassifier | None,
    settings: Settings,
    ports: LLMClassificationPorts,
) -> tuple[LLMClassificationResponse, str]:
    """Classify through the agent by role: images to vision transcription, text or none to text extraction.

    Returns ``(response, provenance)``. Image evidence is read on the person's
    vision-transcription selection and needs no ``text_classifier``; text or no
    evidence is read on the text-extraction selection, so an absent
    ``text_classifier`` is resolved from ``ports`` rather than refused. A
    selected lane that reads off the host needs the per-call consent and
    refuses without it.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the role's reader is unavailable;
            the error carries the reader's exact precondition verdict.
        LLMClassifierError: When the reader call fails after its preconditions are
            confirmed satisfied.
    """
    if evidence is not None and evidence.is_images:
        # The vision path shells out through LLMClient.complete, which records
        # its own run-timing record -- do not double-record here.
        vision = vision_classifier or ports.make_vision_classifier(spec)
        images = evidence.images
        response = _reader_classification(
            ports.run_reader(
                ModelRole.VISION_TRANSCRIPTION,
                lambda: vision.classify(transaction, evidence_images=images),
            )
        )
        return response, vision.decided_by
    text = evidence.text if evidence is not None else None
    if text_classifier is None:
        # The text-extraction reader. Text-layer evidence takes the same agent
        # path, under the same consent rule, as scanned evidence, so how a
        # document happened to be produced never decides where it is read.
        local_text = ports.make_text_classifier(spec)
        return _reader_classification(
            ports.run_reader(
                ModelRole.TEXT_EXTRACTION,
                lambda: local_text.classify(transaction, evidence_text=text),
            )
        ), local_text.decided_by
    return _reader_classification(
        ports.record_classifier_run(
            lambda: text_classifier.classify(transaction, evidence_text=text),
            text_classifier.decided_by,
        )
    ), text_classifier.decided_by


def _reader_classification(result: object) -> LLMClassificationResponse:
    """Return one reader result as the classification the readers are declared to emit.

    The run ports are declared over an opaque result so run records and reader
    recovery stay reader-agnostic; this boundary states what this caller asked
    for, and refuses a result that is not it rather than carrying it further.
    """
    if not isinstance(result, LLMClassificationResponse):
        raise InternalInvariantError("ledger classification reader returned a non-classification result")
    return result


def _reader_split(result: object) -> LLMSplitResponse:
    """Return one reader result as the split proposal the readers are declared to emit."""
    if not isinstance(result, LLMSplitResponse):
        raise InternalInvariantError("ledger split reader returned a non-split result")
    return result


def split_with_evidence(
    transaction: Transaction,
    evidence: ResolvedEvidence | None,
    *,
    proposer: LLMSplitProposer | None,
    spec: PromptSpec,
    vision_classifier: VisionClassifier | None,
    settings: Settings,
    ports: LLMClassificationPorts,
) -> tuple[LLMSplitResponse, str]:
    """Propose a split, routing scan/image evidence to the vision-transcription reader.

    Raises:
        TransactionValidationError: When the evidence is not images and no
            ``proposer`` was injected, so no reader can propose a split.
    """
    if evidence is not None and evidence.is_images:
        # The vision path shells out through LLMClient.complete, which records
        # its own run-timing record -- do not double-record here.
        vision = vision_classifier or ports.make_vision_classifier(spec)
        images = evidence.images
        response = _reader_split(
            ports.run_reader(
                ModelRole.VISION_TRANSCRIPTION,
                lambda: vision.propose_split(transaction, evidence_images=images),
            )
        )
        return response, vision.decided_by
    if proposer is None:
        raise TransactionValidationError(
            _SPLIT_NEEDS_IMAGE_EVIDENCE,
            translated_message="application.ledger.errors.split_requires_image_evidence",
            context={"transaction_id": transaction.transaction_id},
        )
    text = evidence.text if evidence is not None else None
    return _reader_split(
        ports.record_classifier_run(
            lambda: proposer.propose_split(transaction, evidence_text=text),
            proposer.decided_by,
        )
    ), proposer.decided_by
