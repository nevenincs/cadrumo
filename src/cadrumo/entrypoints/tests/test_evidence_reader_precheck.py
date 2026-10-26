"""Evidence draft extraction reports a refused reader with the service's typed verdict.

Drives the composed extraction readers through the production client and agent
adapter against a recording stand-in for the agent service behind the model-run
port. Only evidence resolution is supplied directly, so no stored record is
needed; the text layer, the label rules and the readers are production code.

A role with no selection, or no service at all, must refuse with the typed
verdict naming that refusal, without a run and without trying another lane or
model. A partial label reading stays a success and carries the same cause.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import replace

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...adapters.outbound.llm.tests.model_run_support import ON_HOST_LANE, serving_agent
from ...adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ...application.ledger.evidence_input import EvidenceInput
from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from ...application.ledger.invoice_draft_extraction_ports import InvoiceDraftExtractionPorts
from ...application.ledger.invoice_draft_records import InvoiceDraft, LabelReadingFallbackCause
from ...application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from ...application.operator_actions.models import PreconditionVerdict
from ...core.config import Settings, load_settings
from ...core.document_shape import DocumentShape
from ...core.errors.error_codes import build_error_envelope
from ...core.model_roles import ModelRole
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.iva.regime_legend import resolve_regime_legends
from ...tests.llm_vision_evidence_support import png_image
from ...tests.pdf_fixtures import text_pdf_bytes
from ..adapter_composition import build_ledger_evidence_ports
from ..ledger_evidence_extraction_composition import invoice_draft_extraction_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "5c1e3f7a-2b4d-4e6f-8a9b-0c1d2e3f4a5b"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)

#: A simplified invoice whose labels read the supplier's tax id and the totals
#: but print no supplier name, so the model was to fill one field.
_PARTIAL_LABELS = (
    "Estacion de Servicio Albufera SL",
    "NIF: B92000082",
    "FACTURA SIMPLIFICADA",
    "No: T-0042-2026",
    "Fecha: 14.02.2026",
    "Base imponible 60,00",
    "IVA 21% 12,60",
    "Total (IVA incluido) 72,60 EUR",
)

#: Figures with no label the rules read, so nothing can stand without the model.
_NO_LABELS = ("B1234567X B17283946 766,30",)

_AGENT_RUN_CONDITION = "llm.agent.model_run_completed"


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _evidence(data: bytes, shape: DocumentShape, mime_type: str) -> EvidenceInput:
    return EvidenceInput(
        mime_type=mime_type,
        document_shape=shape,
        data=data,
        content_sha256=hashlib.sha256(data).hexdigest(),
        attachment_id="d" * 64,
    )


def _ports(evidence: EvidenceInput) -> InvoiceDraftExtractionPorts:
    """The composed readers, with evidence resolution handed the document directly."""
    return replace(
        invoice_draft_extraction_ports(evidence_ports=build_ledger_evidence_ports(bucket_id=_BUCKET_ID)),
        resolve_evidence_input=lambda *_args: evidence,
    )


def _extract(evidence: EvidenceInput, settings: Settings, operation: PinnedAuthorityOperation) -> InvoiceDraft:
    return extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        attachment_id=evidence.attachment_id,
        settings=settings,
        ports=_ports(evidence),
        operation=operation,
        legends=resolve_regime_legends(
            operation=operation, effective_date=default_invoice_extraction_period().end_date
        ),
    )


def _text_pdf(lines: tuple[str, ...]) -> EvidenceInput:
    return _evidence(text_pdf_bytes(lines), DocumentShape.PDF_TEXT_LAYER, "application/pdf")


def _assert_refusal(verdict: PreconditionVerdict | None, code: ModelRunRefusalCode, role: ModelRole) -> None:
    assert verdict is not None
    assert verdict.failed_condition_id == _AGENT_RUN_CONDITION
    assert verdict.evidence[0].values["model_run_refusal"] == code.value
    assert verdict.evidence[0].values["model_role"] == role.value


def test_a_partial_label_reading_stands_and_names_the_missing_selection(operation: PinnedAuthorityOperation) -> None:
    """The text role has no selection: the label reading is still the result, and it says why it is partial."""
    with serving_agent(lane=ON_HOST_LANE, lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service:
        draft = _extract(_text_pdf(_PARTIAL_LABELS), load_settings(), operation)

    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert service.runs == [], "a role with no selection must not be run"
    assert draft.supplier_tax_id == "B92000082"
    fallback = draft.label_reading_fallback
    assert fallback is not None
    assert fallback.cause is LabelReadingFallbackCause.READER_UNAVAILABLE
    assert fallback.failed_condition_id == _AGENT_RUN_CONDITION


def test_a_text_read_with_nothing_to_stand_on_refuses_with_the_typed_refusal(
    operation: PinnedAuthorityOperation,
) -> None:
    """No label reads and the text role has no selection: the refusal carries ``no_selection``."""
    with (
        serving_agent(lane=ON_HOST_LANE, lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _extract(_text_pdf(_NO_LABELS), load_settings(), operation)

    assert service.runs == []
    assert build_error_envelope(raised.value).code == "REFUSED_LEDGER_EVIDENCE_READER"
    _assert_refusal(
        raised.value.terminal_precondition_verdict, ModelRunRefusalCode.NO_SELECTION, ModelRole.TEXT_EXTRACTION
    )


def test_an_image_with_no_vision_selection_refuses_before_any_run(operation: PinnedAuthorityOperation) -> None:
    """The vision role is asked for on its own; its refusal is the result, and nothing is run."""
    with (
        serving_agent(lane=ON_HOST_LANE, lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _extract(_evidence(png_image(), DocumentShape.IMAGE, "image/png"), load_settings(), operation)

    assert service.lookups == [ModelRole.VISION_TRANSCRIPTION]
    assert service.runs == []
    _assert_refusal(
        raised.value.terminal_precondition_verdict, ModelRunRefusalCode.NO_SELECTION, ModelRole.VISION_TRANSCRIPTION
    )


def test_no_running_service_refuses_as_service_unavailable(operation: PinnedAuthorityOperation) -> None:
    """Outside a running operation no service can be asked; the refusal says so."""
    with pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised:
        _extract(_text_pdf(_NO_LABELS), load_settings(), operation)

    _assert_refusal(
        raised.value.terminal_precondition_verdict, ModelRunRefusalCode.SERVICE_UNAVAILABLE, ModelRole.TEXT_EXTRACTION
    )
