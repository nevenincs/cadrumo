"""A persona's generated invoices read back, through the product's Facturae reader, as the rows they evidence."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from ...adapters.inbound.einvoice.parsers import parse_einvoice_document
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.persona_invoices import generated_documents, render_facturae
from ...tests.personas import Persona, PersonaCatalogueError, YearEnvelope, persona_ids, read_persona
from .persona_materialisation import year_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _with_generated_documents(envelope: YearEnvelope) -> list[Persona]:
    personas = [read_persona(persona_id, envelope=envelope) for persona_id in persona_ids()]
    return [persona for persona in personas if any(document.generator for document in persona.documents)]


def _stated_tax_id(persona: Persona, role: str) -> str:
    """The identifier as Facturae states it: an EU VAT number as it stands, a Spanish one behind ``ES``."""
    identity = persona.identities.role(role)
    return identity.value if identity.kind == "vat_eu" else f"ES{identity.value}"


def test_every_generated_invoice_reads_back_as_its_row(operation: PinnedAuthorityOperation) -> None:
    envelope = year_envelope(operation)
    personas = _with_generated_documents(envelope)
    assert {persona.id for persona in personas} >= {"autonomo-fontanero", "autonomo-alta-reciente"}
    for persona in personas:
        rows = {row.ref: row for row in persona.ledger}
        documents = {document.id: document for document in persona.documents}
        for generated in generated_documents(persona, envelope):
            (ref,) = documents[generated.document_id].attach_to
            row = rows[ref]
            assert row.counterparty is not None
            assert row.taxable_base is not None and row.iva_rate is not None and row.iva_amount is not None
            parsed = parse_einvoice_document(generated.text.encode("utf-8"))
            where = f"{persona.id} {generated.document_id}"
            assert parsed.supplier_tax_id == _stated_tax_id(persona, row.counterparty), where
            assert parsed.customer_tax_id == _stated_tax_id(persona, persona.taxpayer), where
            assert parsed.invoice_number == row.invoice_number, where
            assert parsed.invoice_date == row.operation_date(envelope).isoformat(), where
            assert parsed.currency == row.currency, where
            assert parsed.taxable_base == row.taxable_base, where
            # Under reverse charge the supplier repercutes nothing; the row's cuota is the recipient's own.
            rate, cuota = (Decimal(0), Decimal("0.00")) if row.reverse_charge else (row.iva_rate, row.iva_amount)
            assert parsed.iva_amount == cuota, where
            assert parsed.iva_breakdown == [(rate * 100, row.taxable_base, cuota)], where
            assert parsed.recargo_amount == row.recargo_amount, where
            # Facturae always states TotalTaxesWithheld, so a row withholding nothing reads as a stated zero.
            assert parsed.retencion_amount == (row.retencion_amount or Decimal("0.00")), where
            expected_rate = None if row.retencion_rate is None else row.retencion_rate * 100
            assert parsed.retencion_rate == expected_rate, where


def test_the_rent_invoice_states_the_retencion_the_row_withholds(operation: PinnedAuthorityOperation) -> None:
    envelope = year_envelope(operation)
    persona = read_persona("autonomo-fontanero", envelope=envelope)
    document = next(document for document in persona.documents if document.attach_to == ("FON-ALQ-01",))
    parsed = parse_einvoice_document(render_facturae(persona, document, envelope).text.encode("utf-8"))

    # 600.00 base, 21 % IVA 126.00, 19 % IRPF 114.00: the tenant pays 612.00.
    assert (parsed.taxable_base, parsed.iva_amount) == (Decimal("600.00"), Decimal("126.00"))
    assert (parsed.retencion_rate, parsed.retencion_amount) == (Decimal("19.00"), Decimal("114.00"))


def test_a_recargo_invoice_states_the_surcharge_beside_the_cuota(operation: PinnedAuthorityOperation) -> None:
    envelope = year_envelope(operation)
    persona = read_persona("minorista-recargo", envelope=envelope)
    document = next(document for document in persona.documents if document.attach_to == ("MIN-COM-1",))
    rendered = render_facturae(persona, document, envelope).text
    parsed = parse_einvoice_document(rendered.encode("utf-8"))

    # 6800.00 base, 21 % IVA 1428.00, 5.2 % recargo 353.60: the retailer pays 8581.60.
    assert (parsed.taxable_base, parsed.iva_amount, parsed.recargo_amount) == (
        Decimal("6800.00"),
        Decimal("1428.00"),
        Decimal("353.60"),
    )
    assert "<EquivalenceSurcharge>5.20</EquivalenceSurcharge>" in rendered
    assert "<InvoiceTotal>8581.60</InvoiceTotal>" in rendered


def test_a_reverse_charge_invoice_repercutes_no_cuota(operation: PinnedAuthorityOperation) -> None:
    envelope = year_envelope(operation)
    persona = read_persona("intracomunitario-desarrollador", envelope=envelope)
    document = next(document for document in persona.documents if document.attach_to == ("DEV-NUBE-02",))
    rendered = render_facturae(persona, document, envelope).text
    parsed = parse_einvoice_document(rendered.encode("utf-8"))

    # 80.00 base from an Irish supplier: the invoice states no cuota; the 16.80 is self-assessed.
    assert parsed.supplier_tax_id == "IE0000001A"
    assert (parsed.taxable_base, parsed.iva_amount) == (Decimal("80.00"), Decimal("0.00"))
    assert "<ResidenceTypeCode>U</ResidenceTypeCode>" in rendered
    assert "Inversión del sujeto pasivo" in rendered


def test_a_row_whose_figures_miss_the_movement_is_refused(operation: PinnedAuthorityOperation) -> None:
    envelope = year_envelope(operation)
    persona = read_persona("autonomo-fontanero", envelope=envelope)
    document = next(document for document in persona.documents if document.attach_to == ("FON-ALQ-01",))
    ledger = tuple(
        dataclasses.replace(row, amount=Decimal("-613.00")) if row.ref == "FON-ALQ-01" else row
        for row in persona.ledger
    )

    with pytest.raises(PersonaCatalogueError, match="differs from the movement"):
        render_facturae(dataclasses.replace(persona, ledger=ledger), document, envelope)


def test_a_specimen_document_is_not_generated(operation: PinnedAuthorityOperation) -> None:
    envelope = year_envelope(operation)
    persona = read_persona("autonomo-fontanero", envelope=envelope)
    document = dataclasses.replace(persona.documents[0], generator=None)

    with pytest.raises(PersonaCatalogueError, match="not a generated Facturae"):
        render_facturae(persona, document, envelope)
