"""The label reader reads what labels assign, and declines everything else.

Positive cases cover one layout each; negative cases prove a figure that does
not reconcile, an identifier that fails its control character and an amount
whose separator is undecidable are left empty with a finding rather than read.
The tampering cases take each clean layout, change one printed figure, and
require the reading to stop standing on its own.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

from ....core.config import Settings
from ....core.config_support import LLMProvider
from ....core.document_shape import DocumentShape
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....domain.iva.regime_legend import resolve_regime_legends
from ..document_transcription import DocumentTranscription
from ..evidence_input import EvidenceInput
from ..evidence_input_ports import EvidenceInputPorts
from ..evidence_textlayer import text_layer_transcriber_identity
from ..grounded_reading import ground_draft_against_transcription
from ..invoice_draft_extraction import extract_invoice_draft_from_evidence
from ..invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    InvoiceDraftReaderUnavailableError,
    VisionImage,
)
from ..invoice_draft_records import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft
from ..invoice_extraction_authority import default_invoice_extraction_period
from ..invoice_label_reader import (
    LabelReading,
    merge_label_reading_with_model_draft,
    read_invoice_fields_by_labels,
    text_layer_reads_completely_by_labels,
)
from ..structured_invoice_ports import StructuredInvoiceRecord
from ._evidence_textlayer_test_support import refusing_text_layer_ports, text_layer_ports_for_pages

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILER = "12345678Z"

_SINGLE_RATE = """FACTURA
Proveedor: Hardware Profesional Sur SL
NIF: B92000090
Numero de factura: A-0003
Fecha de expedicion: 2026-03-27
Destinatario: Javier Ortega Llorens NIF: 12345678Z
Concepto: Ordenador portatil profesional
Base imponible: 1200.00 EUR
Tipo IVA: 21%
Cuota IVA: 252.00 EUR
Total factura: 1452.00 EUR"""

_TWO_RATE_TABLE = """FACTURA
Emisor: Distribuciones Levante SL
CIF: B92000017
Cliente: Javier Ortega Llorens
NIF: 12345678Z
Número de factura: 2026/0117
Fecha de factura: 12/04/2026
Base imponible % IVA Cuota IVA Total
1.000,00 21% 210,00 1.210,00
250,00 10% 25,00 275,00
Total factura: 1.485,00 €"""

_RECARGO = """FACTURA
Proveedor: Mayorista Textil del Turia SA
CIF: A92000074
Destinatario: Javier Ortega Llorens
NIF: 12345678Z
Nº factura: MT-26-0045
Fecha: 03/02/2026
Base imponible: 500,00 €
IVA 21 %: 105,00 €
Recargo de equivalencia 5,2 %: 26,00 €
Total factura: 631,00 €"""

_RETENTION = """EMISOR
Laura Pérez Consultoría
NIF: 00000000T
CLIENTE
Beta Logistica Mediterranea SL
CIF: B92000025
Factura nº F-2026-001
Fecha de expedición: 03-02-2026
Base imponible 1.500,00
IVA (21%) 315,00
Retención IRPF (15%) -225,00
Total factura 1.815,00 EUR
Total a pagar 1.590,00 EUR
Retención IRPF 15% (art. 95 RIRPF)."""

_CATALAN = """FACTURA
Proveïdor: Hotel Mirador Castelló SL
NIF: B92000108
Client: Javier Ortega Llorens
NIF: 12345678Z
Número de factura: HM-0931
Data d'expedició: 22 de maig de 2026
Base imposable: 90,00 €
Quota IVA 10 %: 9,00 €
Total factura: 99,00 €"""

_ENGLISH_REVERSE_CHARGE = """INVOICE
Supplier: Nordwerk Software GmbH
VAT ID: DE123456789
Bill to: Hardware Profesional Sur SL
VAT ID: ESB92000090
Invoice No.: INV-2026-117
Invoice date: March 3, 2026
Net amount: 1250.00 EUR
VAT 0%: 0.00 EUR (reverse charge, Art. 196 Directive 2006/112/EC)
Total: 1250.00 EUR"""

_SIMPLIFIED = """Estación de Servicio Albufera SL
NIF: B92000082
FACTURA SIMPLIFICADA
Nº: T-0042-2026
Fecha: 14.02.2026
Base imponible 60,00
IVA 21% 12,60
Total (IVA incluido) 72,60 €"""

_RECTIFICATIVA = """FACTURA RECTIFICATIVA
Emisor: Lucia Fernandez Ortega
NIF: 45678912S
Cliente: Grupo Consultor Meridiano SL
NIF: B01000017
Numero de factura: R-2026/003
Fecha de factura: 14/04/2026
Base imponible: -400,00 EUR
IVA (21%): -84,00 EUR
TOTAL FACTURA: -484,00 EUR
Retencion IRPF (15%): --60,00 EUR
LIQUIDO A PERCIBIR: -424,00 EUR"""


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _transcription(text: str) -> DocumentTranscription:
    return DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        transcriber=text_layer_transcriber_identity(),
    )


def _read(text: str, operation: PinnedAuthorityOperation) -> LabelReading:
    return read_invoice_fields_by_labels(_transcription(text), operation=operation)


def _grounded(text: str, operation: PinnedAuthorityOperation, *, filer: str = _FILER) -> InvoiceDraft:
    reading = _read(text, operation)
    return ground_draft_against_transcription(
        draft=reading.draft,
        transcription=_transcription(text),
        legends=resolve_regime_legends(
            operation=operation, effective_date=default_invoice_extraction_period().end_date
        ),
        operation=operation,
        taxpayer_tax_id=filer,
    )


def _values(draft: InvoiceDraft, fields: dict[str, object]) -> dict[str, object]:
    return {name: getattr(draft, name) for name in fields}


_LAYOUTS: dict[str, tuple[str, str, dict[str, object]]] = {
    "single_rate": (
        _SINGLE_RATE,
        _FILER,
        {
            "invoice_number": "A-0003",
            "invoice_date": "2026-03-27",
            "supplier_name": "Hardware Profesional Sur SL",
            "supplier_tax_id": "B92000090",
            "customer_name": "Javier Ortega Llorens",
            "customer_tax_id": "12345678Z",
            "taxable_base": Decimal("1200.00"),
            "iva_rate": Decimal("21"),
            "iva_amount": Decimal("252.00"),
            "grand_total": Decimal("1452.00"),
            "currency": "EUR",
        },
    ),
    "two_rate_table": (
        _TWO_RATE_TABLE,
        _FILER,
        {
            "invoice_number": "2026/0117",
            "invoice_date": "2026-04-12",
            "supplier_tax_id": "B92000017",
            "customer_tax_id": "12345678Z",
            "taxable_base": Decimal("1250.00"),
            "iva_rate": None,
            "iva_amount": Decimal("235.00"),
            "grand_total": Decimal("1485.00"),
            "currency": "EUR",
        },
    ),
    "recargo": (
        _RECARGO,
        _FILER,
        {
            "invoice_number": "MT-26-0045",
            "invoice_date": "2026-02-03",
            "taxable_base": Decimal("500.00"),
            "iva_rate": Decimal("21"),
            "iva_amount": Decimal("105.00"),
            "recargo_amount": Decimal("26.00"),
            "grand_total": Decimal("631.00"),
        },
    ),
    "retention": (
        _RETENTION,
        "00000000T",
        {
            "invoice_number": "F-2026-001",
            "supplier_name": "Laura Pérez Consultoría",
            "customer_name": "Beta Logistica Mediterranea SL",
            "retencion_rate": Decimal("15"),
            "retencion_amount": Decimal("225.00"),
            "grand_total": Decimal("1815.00"),
        },
    ),
    "catalan": (
        _CATALAN,
        _FILER,
        {
            "supplier_name": "Hotel Mirador Castelló SL",
            "invoice_number": "HM-0931",
            "invoice_date": "2026-05-22",
            "taxable_base": Decimal("90.00"),
            "iva_rate": Decimal("10"),
            "iva_amount": Decimal("9.00"),
            "grand_total": Decimal("99.00"),
        },
    ),
    "english_reverse_charge": (
        _ENGLISH_REVERSE_CHARGE,
        "B92000090",
        {
            "supplier_tax_id": "DE123456789",
            "customer_tax_id": "B92000090",
            "invoice_number": "INV-2026-117",
            "invoice_date": "2026-03-03",
            "taxable_base": Decimal("1250.00"),
            "iva_rate": None,
            "iva_amount": Decimal("0.00"),
            "grand_total": Decimal("1250.00"),
        },
    ),
    "rectificativa": (
        _RECTIFICATIVA,
        "45678912S",
        {
            "taxable_base": Decimal("-400.00"),
            "iva_amount": Decimal("-84.00"),
            "grand_total": Decimal("-484.00"),
            "retencion_amount": Decimal("-60.00"),
        },
    ),
}


@pytest.mark.parametrize("layout", sorted(_LAYOUTS))
def test_each_layout_reads_completely_and_every_value_grounds(
    layout: str,
    operation: PinnedAuthorityOperation,
) -> None:
    text, filer, expected = _LAYOUTS[layout]

    reading = _read(text, operation)
    draft = _grounded(text, operation, filer=filer)

    assert reading.complete, reading.missing_required_fields
    assert _values(draft, expected) == expected
    assert draft.discrepancies == ()
    envelopes = {envelope.field: envelope for envelope in draft.provenance}
    for name in reading.read_fields:
        assert envelopes[name].grounding in {FieldGroundingOutcome.ANCHORED, FieldGroundingOutcome.RECONCILED}, (
            name,
            envelopes[name].note,
        )


def test_a_rule_read_value_is_stamped_as_rule_read(operation: PinnedAuthorityOperation) -> None:
    draft = _read(_SINGLE_RATE, operation).draft

    origins = {envelope.origin for envelope in draft.provenance}

    assert origins == {FieldOrigin.TEXT_RULES}
    assert {envelope.grounding for envelope in draft.provenance} == {FieldGroundingOutcome.UNANCHORED}


def test_the_multi_rate_sums_are_derived_from_the_printed_tiers(operation: PinnedAuthorityOperation) -> None:
    draft = _read(_TWO_RATE_TABLE, operation).draft
    envelopes = {envelope.field: envelope for envelope in draft.provenance}

    assert [(tier.iva_rate, tier.taxable_base, tier.iva_amount) for tier in draft.iva_breakdown] == [
        (Decimal("21"), Decimal("1000.00"), Decimal("210.00")),
        (Decimal("10"), Decimal("250.00"), Decimal("25.00")),
    ]
    assert envelopes["taxable_base"].origin is FieldOrigin.DERIVED
    assert envelopes["taxable_base"].derived_from == ("iva_breakdown",)


def test_a_simplified_invoice_reads_its_issuer_identifier_but_not_a_letterhead_name(
    operation: PinnedAuthorityOperation,
) -> None:
    reading = _read(_SIMPLIFIED, operation)

    assert reading.draft.supplier_tax_id == "B92000082"
    assert reading.draft.customer_tax_id is None
    assert reading.draft.supplier_name is None
    assert reading.missing_required_fields == {"supplier_name"}
    assert reading.draft.grand_total == Decimal("72.60")


def test_an_unattributable_two_column_party_block_reads_no_identity(operation: PinnedAuthorityOperation) -> None:
    text = (
        "FACTURA\n"
        "EMISOR DESTINATARIO / CLIENTE\n"
        "Suministros Iberia SA Lucia Fernandez Ortega\n"
        "NIF: A22633036 Espana\n"
        "NIF: 45678912S\n"
        "Base imponible: 100,00 EUR\n"
        "IVA (21%): 21,00 EUR\n"
        "TOTAL FACTURA: 121,00 EUR"
    )

    draft = _read(text, operation).draft

    assert draft.supplier_tax_id is None
    assert draft.customer_tax_id is None
    assert draft.grand_total == Decimal("121.00")


def test_a_qualified_identifier_label_names_its_party(operation: PinnedAuthorityOperation) -> None:
    text = "INVOICE\nEMISOR DESTINATARIO\nVAT ID: IE6388047V Espana\nCustomer VAT ID: 45678912S\nTotal due: 10.00 EUR"

    reading = _read(text, operation)
    envelopes = {envelope.field: envelope for envelope in reading.draft.provenance}

    assert reading.draft.customer_tax_id == "45678912S"
    assert reading.draft.supplier_tax_id is None
    assert envelopes["customer_tax_id"].role_evidence == "Customer VAT ID"


# --- declining ---------------------------------------------------------------


def test_a_total_that_does_not_close_is_left_empty_with_a_finding(operation: PinnedAuthorityOperation) -> None:
    text = _SINGLE_RATE.replace("Total factura: 1452.00", "Total factura: 1425.00")

    reading = _read(text, operation)

    assert reading.draft.grand_total is None
    assert reading.draft.taxable_base is None
    assert reading.draft.iva_amount is None
    assert [finding.kind for finding in reading.draft.discrepancies] == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]
    assert reading.draft.discrepancies[0].observed == Decimal("1425.00")
    assert not reading.complete


def test_a_cuota_that_is_not_the_rate_of_the_base_is_left_empty(operation: PinnedAuthorityOperation) -> None:
    text = _RECARGO.replace("IVA 21 %: 105,00", "IVA 21 %: 150,00").replace("631,00", "676,00")

    reading = _read(text, operation)

    assert reading.draft.iva_amount is None
    assert reading.draft.iva_rate is None
    assert DraftDiscrepancyKind.RATE_INCONSISTENT in {finding.kind for finding in reading.draft.discrepancies}


def test_a_retention_the_amount_payable_contradicts_is_left_empty(operation: PinnedAuthorityOperation) -> None:
    text = _RETENTION.replace("Total a pagar 1.590,00", "Total a pagar 1.600,00")

    reading = _read(text, operation)

    assert reading.draft.retencion_amount is None
    assert reading.draft.grand_total == Decimal("1815.00")
    assert [(finding.kind, finding.field) for finding in reading.draft.discrepancies] == [
        (DraftDiscrepancyKind.ARITHMETIC_CLOSURE, "retencion_amount"),
    ]


def test_an_identifier_failing_its_control_character_is_not_read(operation: PinnedAuthorityOperation) -> None:
    text = _SINGLE_RATE.replace("NIF: B92000090", "NIF: B92000091")

    reading = _read(text, operation)

    assert reading.draft.supplier_tax_id is None
    assert "supplier_tax_id" in reading.missing_required_fields
    assert [(finding.kind, finding.field) for finding in reading.draft.discrepancies] == [
        (DraftDiscrepancyKind.IDENTITY_UNVERIFIED, "supplier_tax_id"),
    ]


def test_an_undecidable_thousands_separator_is_recorded_as_ambiguous(operation: PinnedAuthorityOperation) -> None:
    text = "Proveedor: Ejemplo SL\nBase imponible: 1.234 EUR\nTotal factura: 1.234 EUR"

    draft = _read(text, operation).draft
    envelopes = {envelope.field: envelope for envelope in draft.provenance}

    assert draft.taxable_base is None
    assert envelopes["taxable_base"].grounding is FieldGroundingOutcome.AMBIGUOUS
    assert {candidate.value for candidate in envelopes["taxable_base"].candidates} == {"1234", "1.234"}


def test_two_labels_printing_different_totals_choose_neither(operation: PinnedAuthorityOperation) -> None:
    text = _SINGLE_RATE + "\nImporte total: 1500.00 EUR"

    draft = _read(text, operation).draft
    envelopes = {envelope.field: envelope for envelope in draft.provenance}

    assert draft.grand_total is None
    assert envelopes["grand_total"].grounding is FieldGroundingOutcome.AMBIGUOUS


def test_a_figure_inside_a_legal_citation_is_not_an_amount(operation: PinnedAuthorityOperation) -> None:
    draft = _read(_ENGLISH_REVERSE_CHARGE, operation).draft

    assert draft.iva_amount == Decimal("0.00")


def test_an_unlabelled_document_reads_nothing(operation: PinnedAuthorityOperation) -> None:
    reading = _read("B1234567X\nB17283946\n766,30 21% 890,00 9.999,99", operation)

    assert reading.read_fields == frozenset()


# --- detector teeth ----------------------------------------------------------


def _tamper(text: str, printed: str) -> str:
    """Move the units digit of the last *printed* by one, well past the rounding allowance."""
    head, sep, tail = text.rpartition(printed)
    assert sep, f"{printed!r} is not in the layout"
    units = max(printed.rfind("."), printed.rfind(",")) - 1
    digit = "1" if printed[units] != "1" else "2"
    return head + printed[:units] + digit + printed[units + 1 :] + tail


_TAMPER_TARGETS = {
    "single_rate": "1452.00",
    "two_rate_table": "1.485,00",
    "recargo": "631,00",
    "retention": "1.815,00",
    "catalan": "99,00",
    "english_reverse_charge": "1250.00",
    "rectificativa": "-484,00",
}


@pytest.mark.parametrize("layout", sorted(_TAMPER_TARGETS))
def test_a_tampered_total_stops_the_reading_from_standing_alone(
    layout: str,
    operation: PinnedAuthorityOperation,
) -> None:
    clean = _LAYOUTS[layout][0]
    assert _read(clean, operation).complete

    reading = _read(_tamper(clean, _TAMPER_TARGETS[layout]), operation)

    assert not reading.complete
    assert reading.draft.grand_total is None
    assert reading.draft.discrepancies, "a tampered total must leave a finding behind"


# --- merge with the model ----------------------------------------------------


def test_the_model_fills_only_what_the_rules_could_not_read(operation: PinnedAuthorityOperation) -> None:
    reading = _read(_SIMPLIFIED, operation)
    model_draft = InvoiceDraft(
        supplier_name="Estación de Servicio Albufera SL",
        supplier_tax_id="B92000090",
        grand_total=Decimal("99.99"),
        provenance=(
            FieldProvenance(
                field="supplier_name",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.UNANCHORED,
                anchor="Estación de Servicio Albufera SL",
            ),
            FieldProvenance(
                field="grand_total",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.UNANCHORED,
                anchor="99,99",
            ),
        ),
        discrepancies=(
            DraftDiscrepancyFinding(kind=DraftDiscrepancyKind.IDENTITY_UNVERIFIED, field="supplier_tax_id"),
        ),
    )

    merged = merge_label_reading_with_model_draft(reading, model_draft)
    origins = {envelope.field: envelope.origin for envelope in merged.provenance}

    assert merged.supplier_name == "Estación de Servicio Albufera SL"
    assert origins["supplier_name"] is FieldOrigin.TEXT_LAYER
    assert merged.supplier_tax_id == "B92000082"
    assert merged.grand_total == Decimal("72.60")
    assert origins["grand_total"] is FieldOrigin.TEXT_RULES
    assert merged.discrepancies == ()


def test_a_rule_closure_finding_yields_to_the_model_figures_it_cleared(operation: PinnedAuthorityOperation) -> None:
    reading = _read(_SINGLE_RATE.replace("Total factura: 1452.00", "Total factura: 1425.00"), operation)

    kept = merge_label_reading_with_model_draft(reading, InvoiceDraft())
    superseded = merge_label_reading_with_model_draft(reading, InvoiceDraft(grand_total=Decimal("1425.00")))

    assert [finding.kind for finding in kept.discrepancies] == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]
    assert superseded.discrepancies == ()


# --- router ------------------------------------------------------------------


type _TextReader = Callable[
    [DocumentTranscription, Settings, LLMProvider | None, EvidenceConsentProof | None, object],
    InvoiceDraft,
]


def _router_ports(pages: tuple[str, ...], *, read_text: _TextReader) -> InvoiceDraftExtractionPorts:
    payload = b"%PDF-1.7 synthetic label-reader fixture"

    def evidence(_bucket: str, _evidence: str | None, _attachment: str | None, _settings: Settings) -> EvidenceInput:
        return EvidenceInput(
            mime_type="application/pdf",
            document_shape=DocumentShape.PDF_TEXT_LAYER,
            data=payload,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            attachment_id="c" * 64,
        )

    def structured_not_expected(data: bytes) -> StructuredInvoiceRecord:
        del data
        raise AssertionError("the structured reader is not part of a text-layer case")

    def vision_not_expected(
        _images: tuple[VisionImage, ...],
        _address: str,
        _settings: Settings,
        _provider: LLMProvider | None,
        _consent: EvidenceConsentProof | None,
    ) -> DocumentTranscription:
        raise AssertionError("the vision reader is not part of a text-layer case")

    return InvoiceDraftExtractionPorts(
        resolve_evidence_input=evidence,
        evidence_input_ports=EvidenceInputPorts(document_shape_probe=lambda data: DocumentShape.PDF_TEXT_LAYER),
        text_layer_ports=text_layer_ports_for_pages(pages),
        parse_structured_invoice=structured_not_expected,
        read_text=read_text,
        propose_supply_nature=lambda _transcription, _settings: None,
        rasterise_pdf=lambda _data: (),
        transcribe_vision=vision_not_expected,
        consent_binding_error=lambda _facts: RuntimeError("consent binding was not expected"),
    )


def _extract(ports: InvoiceDraftExtractionPorts, operation: PinnedAuthorityOperation) -> InvoiceDraft:
    return extract_invoice_draft_from_evidence(
        bucket_id="bucket",
        attachment_id="c" * 64,
        ports=ports,
        operation=operation,
        legends=resolve_regime_legends(
            operation=operation, effective_date=default_invoice_extraction_period().end_date
        ),
    )


def test_a_complete_rule_reading_never_calls_the_model(operation: PinnedAuthorityOperation) -> None:
    calls: list[DocumentTranscription] = []

    def read_text(transcription: DocumentTranscription, *_rest: object) -> InvoiceDraft:
        calls.append(transcription)
        raise AssertionError("the model must not be called when the rules read every required field")

    draft = _extract(_router_ports((_SINGLE_RATE,), read_text=read_text), operation)

    assert calls == []
    assert draft.grand_total == Decimal("1452.00")
    assert draft.discrepancies == ()


def test_an_absent_model_leaves_the_partial_rule_reading_standing(operation: PinnedAuthorityOperation) -> None:
    def unavailable(_transcription: DocumentTranscription, *_rest: object) -> InvoiceDraft:
        raise InvoiceDraftReaderUnavailableError(ConnectionError("runtime stopped"))

    draft = _extract(_router_ports((_SIMPLIFIED,), read_text=unavailable), operation)

    assert draft.supplier_name is None
    assert draft.supplier_tax_id == "B92000082"
    assert draft.grand_total == Decimal("72.60")


def test_an_absent_model_still_refuses_when_the_rules_read_nothing(operation: PinnedAuthorityOperation) -> None:
    from ..evidence_errors import PurchaseInvoiceEvidenceReaderError

    def unavailable(_transcription: DocumentTranscription, *_rest: object) -> InvoiceDraft:
        raise InvoiceDraftReaderUnavailableError(ConnectionError("runtime stopped"))

    with pytest.raises(PurchaseInvoiceEvidenceReaderError):
        _extract(_router_ports(("B1234567X B17283946 766,30",), read_text=unavailable), operation)


def test_an_incomplete_rule_reading_asks_the_model_for_the_rest(operation: PinnedAuthorityOperation) -> None:
    calls: list[DocumentTranscription] = []

    def read_text(transcription: DocumentTranscription, *_rest: object) -> InvoiceDraft:
        calls.append(transcription)
        return InvoiceDraft(
            supplier_name="Estación de Servicio Albufera SL",
            provenance=(
                FieldProvenance(
                    field="supplier_name",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    anchor="Estación de Servicio Albufera SL",
                ),
            ),
        )

    draft = _extract(_router_ports((_SIMPLIFIED,), read_text=read_text), operation)
    envelopes = {envelope.field: envelope for envelope in draft.provenance}

    assert len(calls) == 1
    assert draft.supplier_name == "Estación de Servicio Albufera SL"
    assert envelopes["supplier_name"].grounding is FieldGroundingOutcome.ANCHORED
    assert envelopes["grand_total"].origin is FieldOrigin.TEXT_RULES


# --- ahead-of-extraction predicate -------------------------------------------


def test_the_ahead_of_extraction_predicate_matches_the_router(operation: PinnedAuthorityOperation) -> None:
    complete = text_layer_reads_completely_by_labels(
        b"%PDF complete",
        text_layer_ports=text_layer_ports_for_pages((_SINGLE_RATE,)),
        operation=operation,
    )
    partial = text_layer_reads_completely_by_labels(
        b"%PDF partial",
        text_layer_ports=text_layer_ports_for_pages((_SIMPLIFIED,)),
        operation=operation,
    )
    scanned = text_layer_reads_completely_by_labels(
        b"%PDF scan",
        text_layer_ports=refusing_text_layer_ports(),
        operation=operation,
    )
    blank = text_layer_reads_completely_by_labels(
        b"%PDF blank",
        text_layer_ports=text_layer_ports_for_pages(("", "  ")),
        operation=operation,
    )

    assert (complete, partial, scanned, blank) == (True, False, False, False)


def test_a_derived_sum_first_does_not_break_identity_resolution(operation: PinnedAuthorityOperation) -> None:
    text = "Base imponible % IVA Cuota IVA\n1.000,00 21% 210,00\n250,00 10% 25,00\nTotal factura: 1.485,00 EUR"

    reading = _read(text, operation)
    draft = _grounded(text, operation)
    envelopes = {envelope.field: envelope for envelope in draft.provenance}

    assert reading.draft.provenance[0].origin is FieldOrigin.DERIVED
    assert draft.supplier_tax_id is None
    assert envelopes["supplier_tax_id"].origin is FieldOrigin.TEXT_RULES


def test_an_unrated_base_beside_rate_lines_is_the_total_they_must_sum_to(operation: PinnedAuthorityOperation) -> None:
    text = (
        "Base21%:435,10 IVA21%:91,37\n"
        "Base10%:265,40 IVA10%:26,54\n"
        "Base4%:76,80 IVA4%:3,07\n"
        "Base imponible: 708,60EUR\n"
        "IVA(total): 106,56EUR"
    )

    reading = _read(text, operation)

    assert reading.draft.taxable_base is None
    assert reading.draft.iva_breakdown == ()
    assert [(finding.kind, finding.field) for finding in reading.draft.discrepancies] == [
        (DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT, "taxable_base"),
    ]


def test_a_heading_word_is_never_read_as_a_party_name(operation: PinnedAuthorityOperation) -> None:
    text = "EMISOR\nInmueblesCastellana200SL DESTINATARIO/CLIENTE\nNIF: B92000017"

    assert _read(text, operation).draft.supplier_name is None
