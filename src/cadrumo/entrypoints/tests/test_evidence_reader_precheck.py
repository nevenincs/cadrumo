"""Evidence draft extraction asks the runtime for its reader before it reads.

Drives the composed extraction readers against a real loopback runtime that
answers its model inventory and records every read it is sent. Only evidence
resolution is supplied directly, so no stored record is needed; the text layer,
the label rules, the reader probe and the readers are production code.

A missing model or an unanswering runtime must refuse with the probe's verdict,
which names the local AI setup, and must do so before any read is sent. A
partial label reading stays a success and carries the same cause and action.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import replace
from http import HTTPStatus
from typing import ClassVar, override

import pytest

from ...adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ...application.ledger.evidence_input import EvidenceInput
from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from ...application.ledger.invoice_draft_extraction_ports import InvoiceDraftExtractionPorts
from ...application.ledger.invoice_draft_records import InvoiceDraft, LabelReadingFallbackCause
from ...application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from ...application.local_reader import configured_role_model
from ...application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ...core.config import Settings, load_settings, override_settings
from ...core.document_shape import DocumentShape
from ...core.errors.error_codes import build_error_envelope
from ...core.model_catalogue import ModelRole
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.iva.regime_legend import resolve_regime_legends
from ...tests.llm_vision_evidence_support import png_image
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...tests.pdf_fixtures import text_pdf_bytes
from ..adapter_composition import build_ledger_evidence_ports
from ..ledger_evidence_extraction_composition import invoice_draft_extraction_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "5c1e3f7a-2b4d-4e6f-8a9b-0c1d2e3f4a5b"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"

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


class _InventoryRuntime(SilentLoopbackHandler):
    """A real runtime endpoint that answers its inventory and records every read it is sent."""

    installed: ClassVar[tuple[str, ...]] = ()
    reads: ClassVar[list[str]] = []

    @override
    def do_GET(self) -> None:
        names = self.installed if self.path == "/api/tags" else ()
        write_json_response(self, {"models": [{"name": name, "size": 1} for name in names]}, status=HTTPStatus.OK)

    @override
    def do_POST(self) -> None:
        # Recorded, then refused: every case here asserts that no read is sent.
        self.reads.append(self.path)
        self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


@contextmanager
def _runtime_holding(*roles: ModelRole) -> Generator[Settings]:
    """Serve a runtime holding the configured models of ``roles`` and no others."""
    _InventoryRuntime.reads = []
    _InventoryRuntime.installed = tuple(model for role in roles if (model := configured_role_model(role)) is not None)
    with (
        serving_loopback(_InventoryRuntime, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield load_settings()


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


def test_a_partial_label_reading_stands_and_names_the_local_ai_setup(operation: PinnedAuthorityOperation) -> None:
    """The text model is missing: the label reading is still the result, and it says what would finish it."""
    with _runtime_holding(ModelRole.VISION_TRANSCRIPTION) as settings:
        draft = _extract(_text_pdf(_PARTIAL_LABELS), settings, operation)

    assert _InventoryRuntime.reads == [], "the fill was attempted before the reader was checked"
    assert draft.supplier_tax_id == "B92000082"
    fallback = draft.label_reading_fallback
    assert fallback is not None
    assert fallback.cause is LabelReadingFallbackCause.READER_UNAVAILABLE
    assert fallback.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert fallback.recovery_action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_text_read_with_nothing_to_stand_on_refuses_with_the_probe_verdict(
    operation: PinnedAuthorityOperation,
) -> None:
    """No label reads and the text model is missing: the refusal is the probe's, naming setup."""
    with (
        _runtime_holding(ModelRole.VISION_TRANSCRIPTION) as settings,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _extract(_text_pdf(_NO_LABELS), settings, operation)

    assert _InventoryRuntime.reads == []
    assert build_error_envelope(raised.value).code == "REFUSED_LEDGER_EVIDENCE_READER"
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert verdict.evidence[0].values["role"] == ModelRole.TEXT_EXTRACTION.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_an_image_with_no_vision_model_refuses_before_the_transcription(operation: PinnedAuthorityOperation) -> None:
    """The vision reader is checked on its own role; an installed text model does not admit it."""
    with (
        _runtime_holding(ModelRole.TEXT_EXTRACTION) as settings,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _extract(_evidence(png_image(), DocumentShape.IMAGE, "image/png"), settings, operation)

    assert _InventoryRuntime.reads == []
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert verdict.evidence[0].values["role"] == ModelRole.VISION_TRANSCRIPTION.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_an_image_with_no_text_model_refuses_before_the_vision_read(operation: PinnedAuthorityOperation) -> None:
    """A transcription is always read by the text model next, so its absence stops the vision read too."""
    with (
        _runtime_holding(ModelRole.VISION_TRANSCRIPTION) as settings,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _extract(_evidence(png_image(), DocumentShape.IMAGE, "image/png"), settings, operation)

    assert _InventoryRuntime.reads == [], "the vision read ran although its transcription could not be read"
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert verdict.evidence[0].values["role"] == ModelRole.TEXT_EXTRACTION.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_an_unanswering_runtime_refuses_with_the_local_ai_setup(operation: PinnedAuthorityOperation) -> None:
    """Nothing listens on the endpoint: the refusal says the runtime did not answer and names setup."""
    with (
        override_settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT),
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _extract(_text_pdf(_NO_LABELS), load_settings(), operation)

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
    assert verdict.evidence[0].values["runtime_reachable"] is False
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
