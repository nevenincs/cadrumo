"""The shape probe classifies the batch reader-role corpus by content.

The batch inference lane decides which reader role a document reaches from the
shape this probe answers. The application suite proves the shape-to-role table
through its probe port; this suite proves the other half against real corpus
bytes: a text-layer PDF, a photographed receipt and a structured invoice each
carry the shape their reader role is declared for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.document_shape import STRUCTURED_DOCUMENT_SHAPES, DocumentShape
from ..shape import probe_document_shape

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_CORPUS = Path(__file__).resolve().parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"


def _read(name: str) -> bytes:
    return (_CORPUS / name).read_bytes()


def test_a_text_layer_pdf_is_probed_as_text_readable() -> None:
    """The layout PDF carries a text layer, so it reaches the text reader, not vision."""
    assert probe_document_shape(_read("com_2026_0005_layout_minimal.pdf")) is DocumentShape.PDF_TEXT_LAYER


def test_a_photographed_receipt_is_probed_as_an_image() -> None:
    """A JPEG receipt is readable only by the vision reader."""
    assert probe_document_shape(_read("commons_invoice_1.jpg")) is DocumentShape.IMAGE


def test_a_structured_invoice_is_probed_as_a_structured_record() -> None:
    """An EN16931 UBL invoice is read exactly and reaches no model reader."""
    shape = probe_document_shape(_read("en16931_ubl_export_third_country_invoice.xml"))

    assert shape in STRUCTURED_DOCUMENT_SHAPES
