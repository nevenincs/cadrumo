"""Closed taxonomy of evidence-document shapes derived from content bytes.

Replaces the two-member ``MediaKind`` (``PDF`` / ``IMAGE``) that was derived
from a *declared* MIME type. That derivation could not see inside a document,
so a ZUGFeRD / Factur-X invoice -- a PDF that carries a complete machine-
readable EN16931 XML payload as an embedded file -- was indistinguishable from
a scan of a paper receipt. Both answered ``PDF``, and the most exactly readable
document in the corpus was read as rendered prose.

The shape is therefore derived from the bytes themselves. It exists so a reader
can ask *what can be recovered exactly from this document* before choosing a
strategy, and so the routing order is inspectable: a document carrying a
structured record reaches no model at all.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["AEAT_RECORD_BATCH_SHAPES", "PDF_CONTAINER_SHAPES", "STRUCTURED_DOCUMENT_SHAPES", "DocumentShape"]


class DocumentShape(StrEnum):
    """What a resolved evidence document actually is, by content.

    Members are ordered from most to least exactly readable. The three
    ``XML_*`` members and :attr:`PDF_EMBEDDED_XML` all carry a structured
    record; everything below them requires text extraction or a model.
    """

    XML_CII = "xml_cii"
    """Standalone EN16931 Cross Industry Invoice (UN/CEFACT syntax)."""

    XML_UBL = "xml_ubl"
    """Standalone EN16931 UBL invoice (OASIS syntax)."""

    XML_FACTURAE = "xml_facturae"
    """Standalone Facturae 3.2.x invoice (the Spanish national format)."""

    PDF_EMBEDDED_XML = "pdf_embedded_xml"
    """PDF carrying a structured invoice as an embedded file (ZUGFeRD / Factur-X)."""

    XML_AEAT_SII = "xml_aeat_sii"
    """AEAT SII submission: a BATCH of ledger records, not one invoice document.

    Deliberately not a member of :data:`STRUCTURED_DOCUMENT_SHAPES`. That set
    routes a document into the single-invoice reader, and one SII file declares
    its record collections at ``maxOccurs=10000``; routing a batch into a
    singular reader would silently keep the first record and discard the rest.
    Which family each record belongs to -- facturas emitidas, recibidas, a baja,
    or one of the twelve non-invoice families -- is classified per RECORD, never
    per file.
    """

    XML_AEAT_VERIFACTU = "xml_aeat_verifactu"
    """VERI*FACTU submission: a batch of registro de facturacion records.

    Not a member of :data:`STRUCTURED_DOCUMENT_SHAPES`, for the same reason as
    :attr:`XML_AEAT_SII`. Its ``RegistroFactura`` is a CHOICE of ``RegistroAlta``
    or ``RegistroAnulacion`` repeated to ``maxOccurs=1000``, so a single
    submission may MIX registrations and cancellations and cannot be classified
    from the file alone.
    """

    PDF_TEXT_LAYER = "pdf_text_layer"
    """PDF with an extractable text layer but no structured record."""

    PDF_SCAN = "pdf_scan"
    """PDF whose pages carry no extractable text; readable only by rasterising."""

    IMAGE = "image"
    """A bare image of a document."""

    UNKNOWN = "unknown"
    """Bytes matching no recognised shape. Never guessed at, always refused."""


STRUCTURED_DOCUMENT_SHAPES: frozenset[DocumentShape] = frozenset(
    {
        DocumentShape.XML_CII,
        DocumentShape.XML_UBL,
        DocumentShape.XML_FACTURAE,
        DocumentShape.PDF_EMBEDDED_XML,
    },
)
"""Shapes carrying a structured SINGLE-INVOICE record, readable with no model.

Membership means "one document, one invoice, readable by
``parse_einvoice_document``". The AEAT record-batch shapes are excluded on
purpose: they are equally structured and equally model-free, but they carry a
COLLECTION of ledger records, so admitting them here would route a batch into a
reader that returns one invoice and silently drop every record after the first.
No single-invoice reader accepts them: the evidence path leaves them outside
this set and refuses them as filing artefacts until a dedicated reconciliation
reader exists. A future reader would need a collection return type rather than
silently discarding records.

Hand-listed rather than derived, so adding a structured member forces a
deliberate decision about which of the two readers it belongs to.
"""

PDF_CONTAINER_SHAPES: frozenset[DocumentShape] = frozenset(
    {
        DocumentShape.PDF_EMBEDDED_XML,
        DocumentShape.PDF_TEXT_LAYER,
        DocumentShape.PDF_SCAN,
    },
)
"""Shapes whose bytes are a PDF, whatever the PDF turns out to carry.

The read paths that rasterise pages, or try a text layer before falling back to
vision, need exactly this question: is this a PDF container? They previously
asked it of ``MediaKind``, which is derived from the STORED MIME TYPE -- a label
the producer attached, which cannot see inside the document. That is the same
blindness the shape probe exists to remove, so asking the label was the one
remaining way a caller could be told "PDF" by something that never opened it.

Hand-listed for the same reason as the sets above: a new PDF-carrying shape
should force a decision about whether page rasterisation is meaningful for it,
rather than being swept in by a name prefix.
"""

AEAT_RECORD_BATCH_SHAPES: frozenset[DocumentShape] = frozenset(
    {
        DocumentShape.XML_AEAT_SII,
        DocumentShape.XML_AEAT_VERIFACTU,
    },
)
"""Shapes carrying a batch of AEAT ledger records rather than one invoice.

These are FILING ARTEFACTS -- records the taxpayer has already declared to
AEAT -- not invoice documents a counterparty issued. The distinction matters
downstream: a record the filer produced is not evidence of what a counterparty
billed, and this codebase draws that line sharply elsewhere.
"""
