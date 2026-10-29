"""A failed vision read is explained by its own verdict, never by a guessed local setup.

Every vision read goes through the agent service, whose refusal carries the
verdict the person needs: the selection to make or the setup to run. The router
reports that verdict unchanged. A failure that carries no verdict is a reader
that did not answer; the router names the unavailable reader and points at no
setup, because nothing it could probe knows which lane the agent service derived.
The transcription port is the input under test.
"""

from __future__ import annotations

import hashlib

import pytest

from ....core.config import Settings
from ....core.document_shape import DocumentShape
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.iva.regime_legend import resolve_regime_legends
from ....tests.llm_vision_evidence_support import png_image
from ...operator_actions.models import PreconditionVerdict
from ...probe_outcomes import ProbePreconditionCondition, provisioning_setup_verdict
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


def _ports_whose_vision_read_fails(verdict: PreconditionVerdict | None) -> InvoiceDraftExtractionPorts:
    def failing_vision_read(
        _images: tuple[VisionImage, ...],
        _source_sha256: str,
        _settings: Settings,
        _consent_token: EvidenceConsentProof | None,
        /,
    ) -> DocumentTranscription:
        raise InvoiceDraftReaderUnavailableError(
            _ProviderReadFailedError("provider did not answer"), precondition_verdict=verdict
        )

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


def _refusal(verdict: PreconditionVerdict | None) -> PurchaseInvoiceEvidenceReaderError:
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        invoice_draft_extraction_module.extract_invoice_draft_from_evidence(
            bucket_id="c" * 64,
            evidence_id="d" * 16,
            settings=Settings(),
            ports=_ports_whose_vision_read_fails(verdict),
            operation=operation,
            legends=resolve_regime_legends(
                operation=operation, effective_date=default_invoice_extraction_period().end_date
            ),
        )
    return raised.value


def test_a_failed_read_without_a_verdict_names_the_reader_and_no_setup() -> None:
    verdict = _refusal(None).terminal_precondition_verdict

    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value
    assert verdict.action is None, "a reader that did not answer was explained by a guessed setup"


def test_a_refused_read_reports_the_services_own_verdict_unchanged() -> None:
    service_verdict = provisioning_setup_verdict(
        ProbePreconditionCondition.ROLE_MODEL_INSTALLED,
        action_id=_LOCAL_AI_SETUP,
        facts={"role": "vision_transcription", "role_model_installed": False},
    )

    verdict = _refusal(service_verdict).terminal_precondition_verdict

    assert verdict == service_verdict
