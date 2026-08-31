"""On-host text-layer extraction from in-memory evidence bytes.

Runs the in-tree pdfplumber text extractor over a resolved
:class:`EvidenceInput`'s in-memory bytes, fully on-host. Nothing is written to
disk and nothing leaves the machine (sensitive-financial-data-secure-storage-only).
This is the cheapest on-host reader and covers text-native PDFs; image evidence
and scan-only PDFs have no usable text layer and must go through the on-host
vision reader instead.

This module is the deterministic half of the ingestion pipeline's acquisition
stage: :func:`transcribe_text_layer` projects the extracted pages into a
:class:`~cadrumo.application.ledger.document_transcription.DocumentTranscription`, the typed record every
later stage reads instead of the bytes. The projection **transforms nothing**.
Reading order is the extractor's page order, and printed forms survive verbatim:
``2.420,00`` stays ``2.420,00``, because the grounding stage verifies a candidate
value by finding its printed form in this text, so normalising here would delete
the evidence that check runs against.
"""

from __future__ import annotations

from importlib.metadata import version

from ...adapters.inbound.pdf import extract_pages_text_from_bytes
from ...core.document_shape import PDF_CONTAINER_SHAPES
from ...core.field_origin import FieldOrigin
from ...core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from .document_transcription import DocumentTranscription, TranscriberIdentity
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .evidence_input import EvidenceInput
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

__all__ = [
    "TEXT_LAYER_TRANSCRIBER_NAME",
    "extract_evidence_pages",
    "extract_evidence_text",
    "text_layer_transcriber_identity",
    "transcribe_text_layer",
]


TEXT_LAYER_TRANSCRIBER_NAME = "pdfplumber"
"""The concrete reader behind the deterministic acquisition path.

Names the library that actually maps bytes to text rather than a coarse label
like ``text-layer``: two extractors disagree on reading order and on where a
ligature or a thousands separator lands, so which one produced a transcription
is exactly what the provenance stamp exists to record.
"""


def _text_layer_transcriber_revision() -> str:
    """Return the installed pdfplumber version, the extractor's real revision.

    Read from the installed distribution rather than restated as a constant. A
    hand-maintained revision is a stamp that can lie the moment the dependency
    moves, and the dependency moving is precisely what changes the output; read
    this way, an upgrade re-keys the transcription cache on its own.
    """
    return version("pdfplumber")


def text_layer_transcriber_identity() -> TranscriberIdentity:
    """Return the provenance stamp for the deterministic text-layer read."""
    return TranscriberIdentity(
        origin=FieldOrigin.TEXT_LAYER,
        name=TEXT_LAYER_TRANSCRIBER_NAME,
        # Stated rather than defaulted, like every other axis here. This reader
        # is a deterministic in-process extractor with no transport at all, so
        # on-host is a fact about it rather than a fallback.
        transport=LOCAL_TRANSPORT_LABEL,
        revision=_text_layer_transcriber_revision(),
    )


def extract_evidence_pages(evidence: EvidenceInput) -> tuple[str, ...]:
    """Return the on-host text layer of a PDF ``EvidenceInput``, page by page.

    Args:
        evidence: Resolved in-memory evidence bytes.

    Returns:
        One string per page in the document's own page order. A page carrying no
        text keeps its slot as the empty string, so the tuple length is the page
        count and the reading order is positional.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the evidence is not a PDF, or the
            PDF has no usable text layer (scan-only / XFA) -- the caller falls back
            to the on-host vision reader in that case.
    """
    if evidence.document_shape not in PDF_CONTAINER_SHAPES:
        raise PurchaseInvoiceEvidenceInputError(
            "evidence has no text layer (not a PDF); use the on-host vision reader",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_TEXT_LAYER_AVAILABLE,
                facts={"pdf_layer_present": False},
            ),
        )
    return extract_pages_text_from_bytes(
        evidence.data,
        error_class=PurchaseInvoiceEvidenceInputError,
        pdf_label="the invoice PDF",
    )


def extract_evidence_text(evidence: EvidenceInput) -> str:
    """Return the on-host text layer of a PDF ``EvidenceInput`` as one string.

    Args:
        evidence: Resolved in-memory evidence bytes.

    Returns:
        The concatenated per-page text of the PDF (empty pages dropped).

    Raises:
        PurchaseInvoiceEvidenceInputError: When the evidence is not a PDF, or the
            PDF has no usable text layer (scan-only / XFA).
    """
    return "\n".join(page for page in extract_evidence_pages(evidence) if page)


def transcribe_text_layer(evidence: EvidenceInput) -> DocumentTranscription:
    """Return the acquisition-stage transcription of a text-native PDF.

    The deterministic acquisition path: it reads, it does not interpret. The text
    is the extractor's own output joined in page order with nothing rewritten, so
    every printed form the document carries reaches the grounding stage intact.

    Args:
        evidence: Resolved in-memory evidence bytes.

    Returns:
        The transcription, stamped :attr:`~cadrumo.core.FieldOrigin.TEXT_LAYER`
        with the extractor that produced it and content-addressed to the source
        bytes.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the evidence is not a PDF, or the
            PDF has no usable text layer (scan-only / XFA).
    """
    pages = extract_evidence_pages(evidence)
    return DocumentTranscription(
        text="\n".join(page for page in pages if page),
        page_count=len(pages),
        source_content_sha256=evidence.content_sha256,
        transcriber=text_layer_transcriber_identity(),
    )
