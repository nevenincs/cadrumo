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


def _tax_id(stated: str | None) -> str | None:
    """The identifier without the ISO prefix Facturae states it with."""
    return stated.removeprefix("ES") if stated is not None else None


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
            assert _tax_id(parsed.supplier_tax_id) == persona.identity(row.counterparty), where
            assert _tax_id(parsed.customer_tax_id) == persona.identity(persona.taxpayer), where
            assert parsed.invoice_number == row.invoice_number, where
            assert parsed.invoice_date == row.operation_date(envelope).isoformat(), where
            assert parsed.currency == row.currency, where
            assert parsed.taxable_base == row.taxable_base, where
            assert parsed.iva_amount == row.iva_amount, where
            assert parsed.iva_breakdown == [(row.iva_rate * 100, row.taxable_base, row.iva_amount)], where
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
