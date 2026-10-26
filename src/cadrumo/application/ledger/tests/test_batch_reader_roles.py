"""Each batch document names the reader role its bytes will reach.

The role follows the probed shape of the document's bytes, so a text-layer PDF
reaches the text reader and a scan or an image the vision one. Which shape a
document's bytes carry is the inbound shape probe's answer and is proven
against the evidence corpus in that adapter's own suite; here each shape is
supplied through the application-owned probe port. How a refused role closes
for the rest of a run is proven through the registered batch operation in the
entrypoint suite.
"""

from __future__ import annotations

import pytest

from ....core.document_shape import DocumentShape
from ....core.model_roles import ModelRole
from ..batch_ingest import _reader_role_for
from ..evidence_input_ports import EvidenceDocumentShapeProbe

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

#: Every shape the probe can answer, with the reader role it must reach. Spelled
#: out rather than derived from the shape sets, so a new shape fails here until
#: someone decides which reader it belongs to.
_ROLE_BY_SHAPE: dict[DocumentShape, ModelRole | None] = {
    DocumentShape.XML_CII: None,
    DocumentShape.XML_UBL: None,
    DocumentShape.XML_FACTURAE: None,
    DocumentShape.PDF_EMBEDDED_XML: None,
    DocumentShape.XML_AEAT_SII: None,
    DocumentShape.XML_AEAT_VERIFACTU: None,
    DocumentShape.PDF_TEXT_LAYER: ModelRole.TEXT_EXTRACTION,
    DocumentShape.PDF_SCAN: ModelRole.VISION_TRANSCRIPTION,
    DocumentShape.IMAGE: ModelRole.VISION_TRANSCRIPTION,
    DocumentShape.UNKNOWN: None,
}


def _probe_answering(shape: DocumentShape, *, expected_data: bytes) -> EvidenceDocumentShapeProbe:
    """Return a shape probe that answers ``shape`` for exactly the bytes it is handed."""

    def probe(data: bytes) -> DocumentShape:
        assert data == expected_data, "the role must be read off the document's own bytes"
        return shape

    return probe


def test_every_shape_has_a_declared_reader_role() -> None:
    """ANCHOR: the table below covers the whole shape vocabulary, so no shape is untested."""
    assert set(_ROLE_BY_SHAPE) == set(DocumentShape)


@pytest.mark.parametrize(("shape", "expected"), list(_ROLE_BY_SHAPE.items()))
def test_each_document_names_the_reader_role_it_will_reach(shape: DocumentShape, expected: ModelRole | None) -> None:
    """DISCRIMINATING: the role follows the probed shape of the bytes, never a file name."""
    data = f"document probed as {shape.value}".encode()

    assert _reader_role_for(data, document_shape_probe=_probe_answering(shape, expected_data=data)) is expected
