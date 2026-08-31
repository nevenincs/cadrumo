"""Real-behaviour gates for the deterministic acquisition-stage transcription.

Builds real multi-page text-bearing PDFs in memory with reportlab, wraps them as
an :class:`EvidenceInput`, and asserts the transcription carries the document's
own printed forms and reading order. No mocks, no fixture files on disk.

Every printed-form assertion is written against the **source literal** the PDF
was authored from -- the module constants below -- never against the
transcription's own output. An output-versus-output equality still passes when
both sides normalise identically, which is exactly the regression this gate
exists to catch.
"""

from __future__ import annotations

import hashlib
from importlib.metadata import version

import pytest

from ....core.field_origin import FieldOrigin
from ....tests.pdf_fixtures import multi_page_text_pdf_bytes
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..evidence import PurchaseInvoiceEvidenceInputError
from ..evidence_input import EvidenceInput
from ..evidence_textlayer import (
    TEXT_LAYER_TRANSCRIBER_NAME,
    text_layer_transcriber_identity,
    transcribe_text_layer,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Printed forms exactly as a Spanish invoice renders them. Grouped with dots,
#: decimal comma. The grounding stage looks for these verbatim.
_PRINTED_BASE = "2.420,00"
_PRINTED_CUOTA = "508,20"
_PRINTED_TOTAL = "2.928,20"

#: The machine-normalised forms none of the above may ever become.
_NORMALISED_FORMS = ("2420.00", "2420,00", "2928.20", "508.20")

_PAGE_ONE_LINES = (
    "FACTURA A-2026-0117",
    f"Base imponible {_PRINTED_BASE}",
    f"Cuota IVA 21% {_PRINTED_CUOTA}",
)
_PAGE_TWO_LINES = (
    "Continuacion pagina 2",
    f"Total factura {_PRINTED_TOTAL}",
)


def _evidence_input(data: bytes, mime_type: str) -> EvidenceInput:
    return EvidenceInput(
        mime_type=mime_type,
        data=data,
        content_sha256=hashlib.sha256(data).hexdigest(),
        attachment_id="b" * 64,
    )


@pytest.fixture
def invoice_evidence() -> EvidenceInput:
    return _evidence_input(
        multi_page_text_pdf_bytes(_PAGE_ONE_LINES, _PAGE_TWO_LINES),
        "application/pdf",
    )


@pytest.fixture
def transcription(invoice_evidence: EvidenceInput) -> DocumentTranscription:
    return transcribe_text_layer(invoice_evidence)


class TestPrintedFormsSurviveVerbatim:
    """The document's own printed forms reach the transcription unrewritten."""

    @pytest.mark.parametrize("printed", [_PRINTED_BASE, _PRINTED_CUOTA, _PRINTED_TOTAL])
    def test_source_literal_occurs_in_transcription(
        self,
        transcription: DocumentTranscription,
        printed: str,
    ) -> None:
        assert printed in transcription.text

    @pytest.mark.parametrize("normalised", _NORMALISED_FORMS)
    def test_no_normalised_form_is_introduced(
        self,
        transcription: DocumentTranscription,
        normalised: str,
    ) -> None:
        assert normalised not in transcription.text


class TestReadingOrder:
    """Pages arrive in the document's own order, and every page is read."""

    def test_page_two_content_follows_page_one(self, transcription: DocumentTranscription) -> None:
        first = transcription.text.index(_PAGE_ONE_LINES[0])
        second = transcription.text.index(_PAGE_TWO_LINES[0])
        assert first < second

    def test_lines_within_a_page_keep_their_printed_order(
        self,
        transcription: DocumentTranscription,
    ) -> None:
        positions = [transcription.text.index(line) for line in _PAGE_ONE_LINES]
        assert positions == sorted(positions)

    def test_page_count_matches_the_authored_pages(self, transcription: DocumentTranscription) -> None:
        assert transcription.page_count == 2


class TestProvenanceStamp:
    """The transcription cites the reader that actually produced it."""

    def test_origin_is_the_text_layer_acquisition_path(self, transcription: DocumentTranscription) -> None:
        assert transcription.transcriber.origin is FieldOrigin.TEXT_LAYER

    def test_reader_is_named_and_revisioned_truthfully(self, transcription: DocumentTranscription) -> None:
        assert transcription.transcriber.name == TEXT_LAYER_TRANSCRIBER_NAME
        assert transcription.transcriber.revision == version("pdfplumber")

    def test_identity_helper_agrees_with_the_stamped_transcription(
        self,
        transcription: DocumentTranscription,
    ) -> None:
        assert transcription.transcriber == text_layer_transcriber_identity()

    def test_content_address_is_the_source_bytes(
        self,
        transcription: DocumentTranscription,
        invoice_evidence: EvidenceInput,
    ) -> None:
        assert transcription.source_content_sha256 == invoice_evidence.content_sha256


class TestSanctionedDurableRoute:
    """The cache pair round-trips the transcription without loosening it."""

    def test_cache_entry_restores_an_equal_transcription(self, transcription: DocumentTranscription) -> None:
        restored = transcription.to_cache_entry().to_transcription()

        assert restored.text == transcription.text
        assert restored.page_count == transcription.page_count
        assert restored.source_content_sha256 == transcription.source_content_sha256
        assert restored.transcriber == transcription.transcriber

    def test_cached_printed_forms_still_match_the_source_literal(
        self,
        transcription: DocumentTranscription,
    ) -> None:
        restored = transcription.to_cache_entry().to_transcription()

        assert _PRINTED_TOTAL in restored.text

    def test_restored_transcription_still_refuses_serialization(
        self,
        transcription: DocumentTranscription,
    ) -> None:
        restored = transcription.to_cache_entry().to_transcription()

        with pytest.raises(NotImplementedError):
            restored.model_dump()


class TestRefusals:
    """Evidence with no text layer refuses, and the intact case proves the route."""

    def test_positive_control_a_text_native_pdf_transcribes(
        self,
        invoice_evidence: EvidenceInput,
    ) -> None:
        assert transcribe_text_layer(invoice_evidence).page_count == 2

    def test_image_evidence_is_refused(self) -> None:
        image = _evidence_input(b"\x89PNG\r\n\x1a\nnot-a-pdf", "image/png")

        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            transcribe_text_layer(image)

    def test_pdf_without_a_text_layer_is_refused(self) -> None:
        blank = _evidence_input(multi_page_text_pdf_bytes(()), "application/pdf")

        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            transcribe_text_layer(blank)


def test_defining_modules_own_the_acquisition_record() -> None:
    assert DocumentTranscription.__module__ == "cadrumo.application.ledger.document_transcription"
    assert TranscriberIdentity.__module__ == "cadrumo.application.ledger.document_transcription"
    assert TranscriberIdentity is type(text_layer_transcriber_identity())
