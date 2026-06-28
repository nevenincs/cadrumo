"""On-host text-layer extraction from in-memory evidence bytes.

Runs the in-tree pdfplumber text extractor over a resolved
:class:`EvidenceInput`'s in-memory bytes, fully on-host. Nothing is written to
disk and nothing leaves the machine (sensitive-financial-data-secure-storage-only).
This is the cheapest on-host reader and covers text-native PDFs; image evidence
and scan-only PDFs have no usable text layer and must go through the on-host
vision reader instead.
"""

from __future__ import annotations

from ...adapters.inbound.pdf._pdfplumber import extract_pages_text_from_bytes
from ._evidence import MediaKind, PurchaseInvoiceEvidenceInputError
from ._evidence_input import EvidenceInput

__all__ = ["extract_evidence_text"]


def extract_evidence_text(evidence: EvidenceInput) -> str:
    """Return the on-host text layer of a PDF ``EvidenceInput`` as one string.

    Args:
        evidence: Resolved in-memory evidence bytes.

    Returns:
        The concatenated per-page text of the PDF (empty pages dropped).

    Raises:
        PurchaseInvoiceEvidenceInputError: When the evidence is not a PDF, or the
            PDF has no usable text layer (scan-only / XFA) -- the caller falls back
            to the on-host vision reader in that case.
    """
    if evidence.media_kind is not MediaKind.PDF:
        raise PurchaseInvoiceEvidenceInputError(
            "evidence has no text layer (not a PDF); use the on-host vision reader",
            suggestion="aeat app ledger evidence list",
        )
    pages = extract_pages_text_from_bytes(
        evidence.data,
        error_class=PurchaseInvoiceEvidenceInputError,
        pdf_label="the invoice PDF",
    )
    return "\n".join(page for page in pages if page)
