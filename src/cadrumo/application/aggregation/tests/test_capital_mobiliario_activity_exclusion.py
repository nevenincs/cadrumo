"""A row linked to a savings position counts once, in the savings boxes, and never as activity income or expense.

The twin of each linked row carries the same business classification without the
link, so the activity pass is shown to read it: only the link moves the row.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.renta.ledger_expenses import RentaDeductibilityContext
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ..renta_gasto_ledger import classify_gasto_transaction
from ..renta_income_classification import classify_income_transaction
from ..renta_income_models import RentaIncomeLedgerAggregationIssue
from ..renta_ledger import RentaCategoryDeductionRules
from .capital_mobiliario_position_support import (
    DEPOSIT,
    DEPOSIT_PAYER,
    INTEREST,
    SHARES,
    YEAR,
    linked_row,
    payer_record,
    resolve_savings,
    savings_boxes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _business(row: Transaction, *, linked: bool) -> Transaction:
    return row.model_copy(
        update={
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "capital_mobiliario",
            "posicion_ref": row.posicion_ref if linked else None,
            "concepto_capital_mobiliario": row.concepto_capital_mobiliario if linked else None,
        }
    )


def _activity_income(row: Transaction) -> object:
    return classify_income_transaction(
        row,
        invoices=InvoiceCatalogue(),
        receipts_by_invoice=None,
        bucket_id="savings-exclusion",
        cumulative_start=date(YEAR, 1, 1),
        cumulative_end=date(YEAR, 12, 31),
        target_casilla_id=validated_casilla_id("0171", surface="activity income target"),
        activity_category_matcher=lambda _transaction: True,
        employment_category_matcher=lambda _transaction: False,
    )


def _activity_expense(row: Transaction) -> object:
    return classify_gasto_transaction(
        row,
        bucket_id="savings-exclusion",
        cumulative_start=date(YEAR, 1, 1),
        cumulative_end=date(YEAR, 12, 31),
        target_casilla_id=validated_casilla_id("0186", surface="activity expense target"),
        accept_activity_marker=True,
        rules=RentaCategoryDeductionRules(
            profile_year=YEAR,
            profiles={},
            region_overrides={},
            context=RentaDeductibilityContext(profile_year=YEAR),
        ),
    )


def test_a_business_interest_row_linked_to_a_position_counts_once_in_the_interest_box() -> None:
    linked = _business(linked_row("i1", DEPOSIT, "intereses", "324.00"), linked=True)
    unlinked = _business(linked, linked=False)

    twin = _activity_income(unlinked)
    assert twin is not None
    assert not isinstance(twin, RentaIncomeLedgerAggregationIssue)
    assert _activity_income(linked) is None

    resolution = resolve_savings((linked,), records=(payer_record(DEPOSIT_PAYER, integro="400.00", retencion="76.00"),))
    assert savings_boxes(resolution)[INTEREST] == Decimal("400.00")


def test_a_linked_custody_expense_is_never_an_activity_expense() -> None:
    linked = _business(
        linked_row("g1", SHARES, "gasto_administracion_deposito", "30.00", direction=TransactionDirection.OUTGOING),
        linked=True,
    )

    assert _activity_expense(_business(linked, linked=False)) is not None
    assert _activity_expense(linked) is None
