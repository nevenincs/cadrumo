"""A failed vision read names the local AI setup only when the read ran on the local AI.

The vision lane asks the local reader probe why a transcription failed when the
failure carries no verdict of its own. That probe measures the local runtime,
so it explains an on-host read only: an off-host read that failed while the
local runtime is also absent must not tell the person to set up a local AI they
did not choose to read with. The probe is real and asks a closed loopback port;
the transcription port is the input under test, failing without a verdict.
"""

from __future__ import annotations

import hashlib

import pytest

from ....core.config import Settings
from ....core.config_support import LLMProvider
from ....core.document_shape import DocumentShape
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.iva.regime_legend import resolve_regime_legends
from ....tests.llm_vision_evidence_support import png_image
from .. import invoice_draft_extraction as invoice_draft_extraction_module
from ..document_transcription import DocumentTranscription
from ..evidence_errors import PurchaseInvoiceEvidenceReaderError
from ..evidence_input import EvidenceInput
from ..evidence_input_ports import EvidenceInputPorts
from ..invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    InvoiceDraftReaderUnavailableError,
    VisionImage,
)
from ..invoice_draft_records import InvoiceDraft
from ..invoice_extraction_authority import default_invoice_extraction_period
from ..preconditions import LedgerPreconditionCondition
from ..structured_invoice_ports import StructuredInvoiceRecord
from ._evidence_textlayer_test_support import text_layer_ports_for_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A port nothing listens on, so the local runtime genuinely does not answer.
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"
_LOCAL_AI_SETUP = "operator.provision.local_ai"


class _ProviderReadFailedError(Exception):
    """The provider the read was routed to did not answer."""


def _image_evidence() -> EvidenceInput:
    payload = png_image()
    return EvidenceInput(
        mime_type="image/png",
        document_shape=DocumentShape.IMAGE,
        data=payload,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        attachment_id="b" * 64,
    )


def _ports_whose_vision_read_fails() -> InvoiceDraftExtractionPorts:
    def failing_vision_read(
        _images: tuple[VisionImage, ...],
        _source_sha256: str,
        _settings: Settings,
        _off_host_provider: LLMProvider | None,
        _consent_token: EvidenceConsentProof | None,
        /,
    ) -> DocumentTranscription:
        raise InvoiceDraftReaderUnavailableError(_ProviderReadFailedError("provider did not answer"))

    def text_reader_was_not_expected(*_args: object) -> InvoiceDraft:
        raise AssertionError("an image carries no text layer to read")

    def structured_reader_was_not_expected(data: bytes) -> StructuredInvoiceRecord:
        del data
        raise AssertionError("an image carries no structured record")

    return InvoiceDraftExtractionPorts(
        resolve_evidence_input=lambda *args, **kwargs: _image_evidence(),
        evidence_input_ports=EvidenceInputPorts(document_shape_probe=lambda data: DocumentShape.IMAGE),
        text_layer_ports=text_layer_ports_for_pages(("",)),
        parse_structured_invoice=structured_reader_was_not_expected,
        read_text=text_reader_was_not_expected,
        propose_supply_nature=lambda *args, **kwargs: None,
        rasterise_pdf=lambda _data: (),
        transcribe_vision=failing_vision_read,
        consent_binding_error=lambda _facts: RuntimeError("consent binding was not expected"),
    )


def _refusal(provider: LLMProvider | None) -> PurchaseInvoiceEvidenceReaderError:
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        invoice_draft_extraction_module.extract_invoice_draft_from_evidence(
            bucket_id="c" * 64,
            evidence_id="d" * 16,
            settings=Settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT),
            off_host_provider=provider,
            ports=_ports_whose_vision_read_fails(),
            operation=operation,
            legends=resolve_regime_legends(
                operation=operation, effective_date=default_invoice_extraction_period().end_date
            ),
        )
    return raised.value


def test_a_failed_off_host_read_names_no_local_ai_setup() -> None:
    verdict = _refusal(LLMProvider.AGENT).terminal_precondition_verdict

    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value
    assert verdict.action is None, "an off-host read was told to set up the local AI"


@pytest.mark.parametrize("provider", [None, LLMProvider.LOCAL], ids=["default", "local"])
def test_a_failed_on_host_read_is_explained_by_the_local_reader_probe(provider: LLMProvider | None) -> None:
    verdict = _refusal(provider).terminal_precondition_verdict

    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _LOCAL_AI_SETUP
