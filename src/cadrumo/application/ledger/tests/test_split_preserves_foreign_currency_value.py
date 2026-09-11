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

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....application.aggregation.currency_predicates import is_non_eur_without_conversion
from ....core.money.rounding import round_to_cents
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction
from ...modelo.tests.test_modelo_303_deductible_evidence_gate import iva_transaction
from ..actions_split_merge import _split_child_eur_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RATE = Decimal("0.1")
# Chosen because independent per-child rounding does NOT re-sum to the parent
# here: 403.33/403.33/403.34 at 0.1 each round to 40.33, totalling 120.99
# against a parent value of 121.00. Without the residual rule a cent vanishes.
_CHILD_AMOUNTS = (Decimal("403.33"), Decimal("403.33"), Decimal("403.34"))


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
