"""The real, committed modelo 347 contraparte row bindings (S294 piece 3).

Proves a real declaration mixing BOTH invoice directions -- adquisiciones
(clave A, payable_invoice) and entregas (clave B, collectible_invoice) --
resolves to one shared row sequence through the ACTUAL committed
2025-y-siguientes bindings (``modelo-347-contraparte-row-{nif,nombre,clave,
importe}``), not a synthetic stand-in. Grounded in the diseño de registro's
own structure (recorded in the tui-architecture modelo 347 contraparte
binding inventory reference): the Tipo-2 declarado record is ONE physical
stream for every clave, so a purchase and a sale for different
counterparties must not collide at the same row index.

Claves C-G are still deferred (each needs a fact this binding family does
not classify from ``source_kind`` alone yet); an observation for one of
those operations simply carries ``operation_clave = None`` and contributes
no row, proven below.
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


def _observation(
    *,
    party: str,
    country: str,
    name: str,
    total: str,
    clave: str | None,
    source_kind: BindingSourceKind = BindingSourceKind.COLLECTIBLE_INVOICE,
) -> InvoiceObservation:
    return InvoiceObservation(
        source_kind=source_kind,
        invoice_id=f"inv-{party}-{total}",
        party_tax_id=party,
        country_code=country,
        party_legal_name=name,
        transaction_date=date(2026, 4, 1),
        base_amount=Decimal(total),
        invoice_total_amount=Decimal(total),
        operation_clave=clave,
    )


def test_a_purchase_and_a_sale_share_one_row_sequence_not_two_colliding_ones() -> None:
    """The bite proof: a purchase (clave A) and a sale (clave B) for different counterparties.

    Before the shared-sequence fix, a payable-sourced clave A binding and a
    collectible-sourced clave B binding would each independently start
    their own row index at 1, so this scenario would have produced two
    row-1 entries -- one correct and one silently overwriting or
    misattributing the other's fields when rendered into the same Tipo-2
    record slot.
    """
    revision = _modelo_347_revision()
    observations = (
        _observation(
            party="A22222223",
            country="ES",
            name="Proveedor SA",
            total="9000.00",
            clave="A",
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
        ),
        _observation(
            party="B11111112",
            country="ES",
            name="Cliente Uno SL",
            total="4000.00",
            clave="B",
            source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        ),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    # Sorted by (country_code, party_tax_id, clave): (ES, A22222223, A), (ES, B11111112, B)
    assert resolved["modelo-347-contraparte-row-nif", 1] == "A22222223"
    assert resolved["modelo-347-contraparte-row-nombre", 1] == "Proveedor SA"
    assert resolved["modelo-347-contraparte-row-clave", 1] == "A"
    assert resolved["modelo-347-contraparte-row-importe", 1] == Decimal("9000.00")
    assert resolved["modelo-347-contraparte-row-nif", 2] == "B11111112"
    assert resolved["modelo-347-contraparte-row-nombre", 2] == "Cliente Uno SL"
    assert resolved["modelo-347-contraparte-row-clave", 2] == "B"
    assert resolved["modelo-347-contraparte-row-importe", 2] == Decimal("4000.00")


def test_a_real_multi_counterparty_declaration_emits_one_row_per_counterparty() -> None:
    """Two counterparties, each above the declaration floor, each their own row."""
    revision = _modelo_347_revision()
    observations = (
        _observation(party="B11111112", country="ES", name="Cliente Uno SL", total="4000.00", clave="B"),
        _observation(party="B11111112", country="ES", name="Cliente Uno SL", total="1000.00", clave="B"),
        _observation(party="A22222223", country="ES", name="Cliente Dos SA", total="9000.00", clave="B"),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    # Sorted by (country_code, party_tax_id, clave): (ES, A22222223, B), (ES, B11111112, B)
    assert resolved["modelo-347-contraparte-row-nif", 1] == "A22222223"
    assert resolved["modelo-347-contraparte-row-nombre", 1] == "Cliente Dos SA"
    assert resolved["modelo-347-contraparte-row-clave", 1] == "B"
    assert resolved["modelo-347-contraparte-row-importe", 1] == Decimal("9000.00")
    assert resolved["modelo-347-contraparte-row-nif", 2] == "B11111112"
    assert resolved["modelo-347-contraparte-row-nombre", 2] == "Cliente Uno SL"
    assert resolved["modelo-347-contraparte-row-clave", 2] == "B"
    assert resolved["modelo-347-contraparte-row-importe", 2] == Decimal("5000.00")


def test_a_single_counterparty_still_resolves_to_exactly_one_row() -> None:
    """A count-only assertion would also pass a broken resolver emitting N identical rows."""
    revision = _modelo_347_revision()
    observations = (
        _observation(party="B11111112", country="ES", name="Cliente Uno SL", total="4000.00", clave="B"),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    row_indexes = {row_index for (_binding_id, row_index) in resolved}
    assert row_indexes == {1}
    assert resolved["modelo-347-contraparte-row-nif", 1] == "B11111112"


def test_an_unclassified_clave_contributes_no_row() -> None:
    """An operation whose clave (C-G) is not yet classified is skipped, not mis-declared."""
    revision = _modelo_347_revision()
    observations = (
        _observation(party="C33333334", country="ES", name="Colegio Profesional", total="500.00", clave=None),
        _observation(party="B11111112", country="ES", name="Cliente Uno SL", total="4000.00", clave="B"),
    )

    resolved = resolve_invoice_binding_row_values(revision, observations)

    row_indexes = {row_index for (_binding_id, row_index) in resolved}
    assert row_indexes == {1}
    assert resolved["modelo-347-contraparte-row-nif", 1] == "B11111112"
