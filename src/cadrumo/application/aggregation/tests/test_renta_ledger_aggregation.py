"""Focused unit tests for _renta_ledger._casilla_aggregation.

`_casilla_aggregation` aggregates `RentaDeductibleExpenseObservation`
records into a `CasillaAggregation` payload, grouping by
``(target_casilla_id, category)`` and producing:

- Per-casilla totals dict: ``casilla → sum(deductible_amount)``.
- Per-(casilla, category) provenance rows with sorted transaction
  ids and a subtotal.

Previously exercised only indirectly through the public
``aggregate_renta_ledger_expenses`` orchestrator's tests. A
regression in the grouping key or the sort order would silently
change the audit trail across every operator's Renta filing.

Tests here pin the grouping-contract output shape; subtotal
arithmetic checks are aggregator-contract assertions (the
aggregator must correctly sum the inputs it was given), not
calculation tautologies.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.resources.registry import resources
from ....domain.categories.spending_category import SpendingCategory
from ....domain.renta.ledger_expenses import (
    RentaDeductibilityContext,
    RentaDeductibleExpenseFact,
    RentaDeductibleExpenseObservation,
    RentaExpenseDirection,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
)
from .._renta_ledger import _casilla_aggregation
from .renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _tx_id(label: str) -> str:
    """Map a readable fixture label to a conforming 64-hex transaction id.

    ``TransactionId`` is a content-addressed digest, so a short label is not a
    legal value. Deriving it here keeps every assertion written against the
    readable label instead of a magic digest, and keeps distinct labels
    distinct.
    """
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _observation(
    transaction_id: str,
    *,
    category: SpendingCategory,
    gross_amount: Decimal,
) -> RentaDeductibleExpenseObservation:
    """Build a single Renta-deductible observation via the project factory."""
    fact = RentaDeductibleExpenseFact(
        transaction_id=_tx_id(transaction_id),
        catalogue_id="ledger",
        operation_date=date(2025, 4, 5),
        gross_amount=gross_amount,
        direction=RentaExpenseDirection.OUTGOING_EXPENSE,
        category=category,
    )
    profile = resources().category_profiles.get(2025)[category]
    result = evaluate_renta_deductibility(
        fact,
        profile,
        RentaDeductibilityContext(profile_year=2025),
    )
    return build_renta_deductible_expense_observation(fact, result, tax_year=2025)


_PERIOD_2025 = _period(2025, "0A")


_M100_AUTONOMOS_SS_CASILLA: CasillaId = validated_casilla_id("0186")
_M100_ASESORIA_CASILLA: CasillaId = validated_casilla_id("0199")


# ---------------------------------------------------------------------------
# Output structural contract
# ---------------------------------------------------------------------------


def test_casilla_aggregation_empty_observations_yields_empty_totals_and_provenance() -> None:
    result = _casilla_aggregation(_PERIOD_2025, (), modelo="100")

    assert result.modelo == "100"
    assert result.period == _PERIOD_2025
    assert result.casilla_values == {}
    assert result.provenance == ()


def test_casilla_aggregation_modelo_propagates_to_output() -> None:
    """The modelo passed to the aggregator is reflected in the output."""
    obs = _observation("tx-1", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs], modelo="100")

    assert result.modelo == "100"


def test_casilla_aggregation_preserves_period_argument() -> None:
    obs = _observation("tx-1", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))

    other_period = _period(2024, "0A")
    result = _casilla_aggregation(other_period, [obs], modelo="100")

    assert result.period == other_period


# ---------------------------------------------------------------------------
# Grouping behaviour
# ---------------------------------------------------------------------------


def test_casilla_aggregation_single_observation_produces_one_total_and_one_provenance_row() -> None:
    obs = _observation("tx-1", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs], modelo="100")

    assert set(result.casilla_values.keys()) == {_M100_AUTONOMOS_SS_CASILLA}
    assert len(result.provenance) == 1
    assert result.provenance[0].casilla_id == _M100_AUTONOMOS_SS_CASILLA
    assert result.provenance[0].category_id == SpendingCategory.CUOTAS_AUTONOMOS_SS.value
    assert result.provenance[0].transaction_ids == (_tx_id("tx-1"),)


def test_casilla_aggregation_groups_observations_same_casilla_same_category_into_one_row() -> None:
    """Two observations from the same (casilla, category) collapse into
    a single provenance row that lists both transaction_ids."""
    obs_a = _observation("tx-a", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))
    obs_b = _observation("tx-b", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("200.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs_a, obs_b], modelo="100")

    assert len(result.provenance) == 1
    assert result.provenance[0].casilla_id == _M100_AUTONOMOS_SS_CASILLA
    assert result.provenance[0].transaction_ids == tuple(sorted((_tx_id("tx-a"), _tx_id("tx-b"))))
    assert set(result.casilla_values.keys()) == {_M100_AUTONOMOS_SS_CASILLA}


def test_casilla_aggregation_groups_same_casilla_different_categories_into_separate_rows() -> None:
    """ASESORIA_CONTABLE and ASESORIA_FISCAL both target casilla 0199.
    The total under 0199 sums BOTH categories, but provenance has TWO
    rows so the audit trail preserves per-category attribution."""
    obs_contable = _observation(
        "tx-contable",
        category=SpendingCategory.ASESORIA_CONTABLE,
        gross_amount=Decimal("121.00"),
    )
    obs_fiscal = _observation("tx-fiscal", category=SpendingCategory.ASESORIA_FISCAL, gross_amount=Decimal("79.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs_contable, obs_fiscal], modelo="100")

    # Both observations contribute to the same casilla key.
    assert set(result.casilla_values.keys()) == {_M100_ASESORIA_CASILLA}
    # But provenance preserves the per-category split.
    provenance_categories = {row.category_id for row in result.provenance if row.casilla_id == _M100_ASESORIA_CASILLA}
    assert provenance_categories == {
        SpendingCategory.ASESORIA_CONTABLE.value,
        SpendingCategory.ASESORIA_FISCAL.value,
    }


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


def test_casilla_aggregation_provenance_rows_are_sorted_by_casilla_then_category() -> None:
    """Provenance rows iterate in lexicographic (casilla, category)
    order so audit-diff output is stable regardless of input ordering."""
    obs_186 = _observation("tx-186", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))
    obs_192 = _observation("tx-192", category=SpendingCategory.ARRENDAMIENTO_LOCAL, gross_amount=Decimal("500.00"))
    obs_199 = _observation("tx-199", category=SpendingCategory.ASESORIA_CONTABLE, gross_amount=Decimal("121.00"))

    # Feed observations in random-ish order.
    result = _casilla_aggregation(_PERIOD_2025, [obs_192, obs_199, obs_186], modelo="100")

    keys = [(row.casilla_id, row.category_id) for row in result.provenance]
    assert keys == sorted(keys)


def test_casilla_aggregation_transaction_ids_within_one_row_are_sorted() -> None:
    """transaction_ids on each provenance row are lexicographically
    sorted; the aggregator never preserves input ordering for the
    transaction sequence."""
    obs_z = _observation("tx-z", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("100.00"))
    obs_a = _observation("tx-a", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("200.00"))
    obs_m = _observation("tx-m", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs_z, obs_a, obs_m], modelo="100")

    fed_order = (_tx_id("tx-z"), _tx_id("tx-a"), _tx_id("tx-m"))
    # The claim below is only a claim about sorting if the order the
    # observations were fed in is not already the sorted one.
    assert fed_order != tuple(sorted(fed_order)), "pick labels whose derived ids are fed out of order"
    assert len(result.provenance) == 1
    assert result.provenance[0].transaction_ids == tuple(sorted(fed_order))


# ---------------------------------------------------------------------------
# Aggregator-contract arithmetic (input-given totals, NOT external authority)
# ---------------------------------------------------------------------------


def test_casilla_aggregation_subtotal_equals_sum_of_member_observations() -> None:
    """The aggregator-contract assertion: subtotal on each provenance
    row equals the sum of deductible_amount of its member observations.
    This is an aggregator-contract check (the helper must correctly
    sum the inputs it was given), not a calculation tautology — the
    test does NOT hand-compute the deductible_amount of each
    observation; it asserts the aggregator's internal sum matches
    Python's built-in sum() over the same inputs."""
    obs_a = _observation("tx-a", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))
    obs_b = _observation("tx-b", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("200.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs_a, obs_b], modelo="100")

    expected_subtotal = obs_a.deductible_amount + obs_b.deductible_amount
    assert result.provenance[0].subtotal == expected_subtotal


def test_casilla_aggregation_casilla_total_equals_sum_of_observations_for_that_casilla() -> None:
    """Same aggregator-contract assertion at the casilla-level: the
    helper must correctly sum every observation that targets the same
    casilla, regardless of category. Asserts the aggregator's
    casilla_values entry matches Python's sum() over the same inputs."""
    obs_contable = _observation(
        "tx-contable",
        category=SpendingCategory.ASESORIA_CONTABLE,
        gross_amount=Decimal("121.00"),
    )
    obs_fiscal = _observation("tx-fiscal", category=SpendingCategory.ASESORIA_FISCAL, gross_amount=Decimal("79.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs_contable, obs_fiscal], modelo="100")

    expected_total = obs_contable.deductible_amount + obs_fiscal.deductible_amount
    assert result.casilla_values[_M100_ASESORIA_CASILLA] == expected_total


# ---------------------------------------------------------------------------
# Typed provenance: SpendingCategory survives the ledger→renta handoff
# ---------------------------------------------------------------------------


def test_casilla_aggregation_category_id_is_typed_spending_category_instance() -> None:
    """category_id on CasillaProvenance rows is a SpendingCategory enum member.

    The ledger→renta handoff must preserve the typed ``SpendingCategory``
    enum through ``_casilla_aggregation`` so downstream consumers can
    compare against the enum directly without calling
    ``normalize_spending_category``. This test asserts the type survives
    end-to-end: from ``RentaDeductibleExpenseObservation.category``
    (typed ``SpendingCategory``) through ``_casilla_aggregation`` to
    ``CasillaProvenance.category_id`` (also typed ``SpendingCategory``
    via the ``_SpendingCategoryField`` coercion).

    If ``category_id`` were stored as a bare ``str``, the
    ``isinstance`` assertion below would fail, surfacing the
    provenance-loss regression introduced by any future edit that
    reverts ``category_id`` to ``str | None``.
    """

    obs = _observation("tx-typed", category=SpendingCategory.CUOTAS_AUTONOMOS_SS, gross_amount=Decimal("300.00"))

    result = _casilla_aggregation(_PERIOD_2025, [obs], modelo="100")

    assert len(result.provenance) == 1
    row = result.provenance[0]
    # The typed enum must survive the handoff — not a bare string.
    assert isinstance(row.category_id, SpendingCategory), (
        f"CasillaProvenance.category_id must be a SpendingCategory instance "
        f"but got {type(row.category_id).__name__!r}; the typed provenance "
        "was lost at the ledger→renta handoff"
    )
    assert row.category_id is SpendingCategory.CUOTAS_AUTONOMOS_SS
