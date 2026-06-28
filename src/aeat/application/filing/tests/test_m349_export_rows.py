"""Modelo 349 fixed-width row rendering from resolved invoice rows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core import BindingSourceKind, Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    InvoiceObservation,
    resolve_export_layout,
    resolve_invoice_binding_row_values,
)
from ....domain.filing import ModeloBindingValue, ModeloDraft, ModeloValueKind
from ....domain.submission import ModeloDraftStatus
from .. import render_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M349_PUBLIC_OPERATOR_BINDINGS = frozenset(
    {
        "iva-349-operador-row-codigo-pais",
        "iva-349-operador-row-nif",
        "iva-349-operador-row-apellidos",
        "iva-349-operador-row-clave",
        "iva-349-operador-row-base",
    },
)


def test_render_layout_emits_m349_payable_acquisition_as_public_operador_record() -> None:
    """Received acquisitions must render as Tipo 2 operador rows, not as mirror-only data."""
    snapshot = resources().modelos.authority.snapshot("349", filing_year=2026, period="1T")
    layout = resolve_export_layout(snapshot).layout
    rows = resolve_invoice_binding_row_values(
        snapshot.revision,
        (
            InvoiceObservation(
                invoice_id="inv-de-sale",
                party_tax_id="DE111111111",
                country_code="DE",
                transaction_date=date(2026, 3, 1),
                base_amount=Decimal("1000.00"),
                intracommunity_clave="E",
                party_legal_name="SALE GMBH",
            ),
            InvoiceObservation(
                invoice_id="inv-de-acq",
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                party_tax_id="DE222222222",
                country_code="DE",
                transaction_date=date(2026, 3, 2),
                base_amount=Decimal("750.00"),
                intracommunity_clave="A",
                party_legal_name="SUPPLIER GMBH",
            ),
        ),
    )
    binding_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    now_utc = datetime(2026, 4, 1, tzinfo=UTC)
    binding_values = tuple(
        ModeloBindingValue(
            binding_id=binding_id,
            value=value,
            kind=ModeloValueKind.LITERAL,
            source=(
                BindingSourceKind.PAYABLE_INVOICE
                if row_index == 2
                else BindingSourceKind(binding_by_id[binding_id].source)
            ),
            legal_refs=binding_by_id[binding_id].legal_refs,
            source_refs=binding_by_id[binding_id].source_refs,
            row_index=row_index,
        )
        for (binding_id, row_index), value in sorted(rows.items())
        if binding_id in _M349_PUBLIC_OPERATOR_BINDINGS
    )
    draft = ModeloDraft(
        draft_id="m349-invoice-row-export",
        modelo="349",
        period=Period.from_year_and_code(2026, "1T"),
        profile_tax_id="B12345678",
        status=ModeloDraftStatus.APROBADO,
        values=(),
        binding_values=binding_values,
        created_at=now_utc,
        updated_at=now_utc,
        schema_version="test",
    )

    payload = render_layout(layout, draft=draft, headers={"declaration_type": "I"})

    assert len(payload) == 1500
    sale_record = payload[500:1000].decode("latin-1")
    acquisition_record = payload[1000:1500].decode("latin-1")
    assert sale_record[0] == "2"
    assert sale_record[75:77] == "DE"
    assert sale_record[77:92].strip() == "111111111"
    assert sale_record[92:132].strip() == "SALE GMBH"
    assert sale_record[132] == "E"
    assert sale_record[133:146] == "0000000100000"
    assert acquisition_record[0] == "2"
    assert acquisition_record[75:77] == "DE"
    assert acquisition_record[77:92].strip() == "222222222"
    assert acquisition_record[92:132].strip() == "SUPPLIER GMBH"
    assert acquisition_record[132] == "A"
    assert acquisition_record[133:146] == "0000000075000"
