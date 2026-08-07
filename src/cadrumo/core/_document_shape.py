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

__all__ = ["STRUCTURED_DOCUMENT_SHAPES", "DocumentShape"]


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
"""Shapes carrying a structured record, readable exactly with no model.

Derived from the enum rather than hand-listed, so a new structured member
cannot be added without a deliberate decision about its membership here.
"""
