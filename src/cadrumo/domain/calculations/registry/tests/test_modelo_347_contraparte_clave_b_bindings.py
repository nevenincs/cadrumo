"""The real, committed modelo 347 clave B contraparte row bindings (S294 piece 3, first slice).

Proves a real multi-counterparty declaration resolves to one row per
counterparty through the ACTUAL committed 2025-y-siguientes bindings
(``modelo-347-contraparte-row-{nif,nombre,clave,importe}-b``), not a
synthetic stand-in. Scoped to clave B (entregas, collectible invoices)
only -- clave A needs a resolver-level source union this Step defers (see
``0002-contraparte-clave-b.toml``'s own header note and the tui-architecture
modelo 347 contraparte binding inventory reference).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from ..invoice_bindings import InvoiceObservation, resolve_invoice_binding_row_values
from ..schema import ModeloRevision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo_347_revision() -> ModeloRevision:
    modelo, _catalogues = _committed_modelo("347")
    return modelo.revisions["2025-y-siguientes"]


def _entrega_observation(*, party: str, country: str, name: str, total: str) -> InvoiceObservation:
    return InvoiceObservation(
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        invoice_id=f"inv-{party}-{total}",
        party_tax_id=party,
        country_code=country,
        party_legal_name=name,
        transaction_date=date(2026, 4, 1),
        base_amount=Decimal(total),
        invoice_total_amount=Decimal(total),
        operation_clave="B",
    )


def test_a_real_multi_counterparty_declaration_emits_one_row_per_counterparty() -> None:
    """Two counterparties, each above the declaration floor, each their own row."""
    revision = _modelo_347_revision()
    observations = (
        _entrega_observation(party="B11111112", country="ES", name="Cliente Uno SL", total="4000.00"),
        _entrega_observation(party="B11111112", country="ES", name="Cliente Uno SL", total="1000.00"),
        _entrega_observation(party="A22222223", country="ES", name="Cliente Dos SA", total="9000.00"),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    # Sorted by (country_code, party_tax_id, clave): (ES, A22222223, B), (ES, B11111112, B)
    assert resolved["modelo-347-contraparte-row-nif-b", 1] == "A22222223"
    assert resolved["modelo-347-contraparte-row-nombre-b", 1] == "Cliente Dos SA"
    assert resolved["modelo-347-contraparte-row-clave-b", 1] == "B"
    assert resolved["modelo-347-contraparte-row-importe-b", 1] == Decimal("9000.00")
    assert resolved["modelo-347-contraparte-row-nif-b", 2] == "B11111112"
    assert resolved["modelo-347-contraparte-row-nombre-b", 2] == "Cliente Uno SL"
    assert resolved["modelo-347-contraparte-row-clave-b", 2] == "B"
    assert resolved["modelo-347-contraparte-row-importe-b", 2] == Decimal("5000.00")


def test_a_single_counterparty_still_resolves_to_exactly_one_row() -> None:
    """A count-only assertion would also pass a broken resolver emitting N identical rows."""
    revision = _modelo_347_revision()
    observations = (_entrega_observation(party="B11111112", country="ES", name="Cliente Uno SL", total="4000.00"),)

    resolved = resolve_invoice_binding_row_values(revision, observations)

    row_indexes = {row_index for (_binding_id, row_index) in resolved}
    assert row_indexes == {1}
    assert resolved["modelo-347-contraparte-row-nif-b", 1] == "B11111112"
