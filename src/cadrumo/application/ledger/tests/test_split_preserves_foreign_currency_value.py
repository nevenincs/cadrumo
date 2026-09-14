"""Splitting a converted foreign row keeps its euro value, whole and undivided.

The split builder copied the parent's currency but not its conversion, so every
child of a converted foreign parent came out foreign-with-no-conversion. That
is not a rounding difference downstream: ``effective_eur_amount`` refuses such a
row outright, and the money roll-up excludes it, so splitting a foreign
transaction silently removed its value from every euro-denominated view of the
ledger. Edit and merge already preserved the conversion; split was the hole.

Two things have to hold at once. Each child takes the parent's rate VERBATIM,
because ``effective_eur_taxable_base`` multiplies each child's own base by that
child's rate -- a rate back-solved to fit a rounded EUR value would break
``gross == base + iva`` once re-expressed in euros. And the children must
re-sum to the parent's stored EUR total, which independent per-child rounding
does not guarantee, so the last child absorbs the residual.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.aggregation.currency_predicates import is_non_eur_without_conversion
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.money.rounding import round_to_cents
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_split_merge import _split_child_eur_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RATE = Decimal("0.1")
# Chosen because independent per-child rounding does NOT re-sum to the parent
# here: 403.33/403.33/403.34 at 0.1 each round to 40.33, totalling 120.99
# against a parent value of 121.00. Without the residual rule a cent vanishes.
_CHILD_AMOUNTS = (Decimal("403.33"), Decimal("403.33"), Decimal("403.34"))
_IVA_RATE = Decimal("0.21")
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)


def _raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        description=f"IVA transaction {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(2026, 2, 15),
                amount=taxable_base + iva_amount,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": "BUSINESS",
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "deduction_fact_kind": (
                IvaDeductionFactKind._from_registry("domestic_current")
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority._from_registry("invoice_evidence"),
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _domestic_parent() -> Transaction:
    return iva_transaction("split-fx", direction=TransactionDirection.OUTGOING, taxable_base=Decimal("1000.00"))


def _converted_parent(*, rate: Decimal = _RATE) -> Transaction:
    """A foreign parent whose EUR value was rounded once, over the whole gross."""
    parent = _domestic_parent()
    return parent.model_copy(
        update={
            "raw": parent.raw.model_copy(update={"currency": "USD"}),
            "fx_rate": rate,
            "value_in_eur": round_to_cents(parent.raw.amount * rate),
        },
    )


def test_the_children_of_a_converted_parent_resum_to_its_stored_euro_value() -> None:
    """The post-condition, on a split where naive rounding would lose a cent."""
    parent = _converted_parent()
    assert parent.value_in_eur == Decimal("121.00")

    values = _split_child_eur_values(parent=parent, child_amounts=_CHILD_AMOUNTS)

    assert values is not None
    assert sum(values, start=Decimal("0")) == parent.value_in_eur


def test_the_last_child_absorbs_the_residual_rather_than_the_ledger_losing_it() -> None:
    """Names where the cent goes, so a future change cannot quietly relocate it."""
    parent = _converted_parent()
    naive = [round_to_cents(amount * _RATE) for amount in _CHILD_AMOUNTS]
    assert sum(naive, start=Decimal("0")) == Decimal("120.99"), "the fixture must actually have a residual"

    values = _split_child_eur_values(parent=parent, child_amounts=_CHILD_AMOUNTS)

    assert values is not None
    assert list(values[:-1]) == naive[:-1]
    assert values[-1] == Decimal("40.34")
    assert values[-1] != naive[-1]


def test_every_child_is_valued_at_the_parents_rate_not_one_fitted_to_itself() -> None:
    """A back-solved per-child rate would break gross == base + iva in euros."""
    parent = _converted_parent()
    rate = parent.fx_rate
    assert rate is not None, "a converted parent must carry the rate its children inherit"

    values = _split_child_eur_values(parent=parent, child_amounts=_CHILD_AMOUNTS)

    assert values is not None
    for amount, value in zip(_CHILD_AMOUNTS[:-1], values[:-1], strict=True):
        assert value == round_to_cents(amount * rate)


def test_a_single_child_receives_the_whole_parent_value() -> None:
    """The degenerate split still conserves the total exactly."""
    parent = _converted_parent()

    values = _split_child_eur_values(parent=parent, child_amounts=(parent.raw.amount,))

    assert values == (parent.value_in_eur,)


def test_an_unconverted_parent_has_no_conversion_to_distribute() -> None:
    """A domestic row carries no rate, so its children carry none either."""
    assert _split_child_eur_values(parent=_domestic_parent(), child_amounts=_CHILD_AMOUNTS) is None


def test_a_child_built_from_a_converted_parent_is_not_an_unconverted_row() -> None:
    """The operator-visible consequence: the child stays inside the euro totals.

    Asserted through the same predicate the roll-up and the aggregation gates
    consult, rather than by re-reading the fields, so this fails if the child
    ever stops satisfying what those callers actually ask.
    """
    parent = _converted_parent()
    values = _split_child_eur_values(parent=parent, child_amounts=_CHILD_AMOUNTS)
    assert values is not None

    child = iva_transaction("split-fx-child", direction=TransactionDirection.OUTGOING, taxable_base=Decimal("300.00"))
    converted_child = child.model_copy(
        update={
            "raw": child.raw.model_copy(update={"currency": parent.raw.currency}),
            "fx_rate": parent.fx_rate,
            "value_in_eur": values[0],
            "modified_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
    )

    assert not is_non_eur_without_conversion(converted_child)
