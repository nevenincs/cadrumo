"""The recargo lookup keys on the rate a line carried, not on its tier.

LIVA art. 161 pairs each recargo with an IVA tier, and for thirty years the tier
determined the rate because each tier had exactly one. The 2023-2024 foodstuffs
measures ended that: between 2023-01-01 and 2024-09-30 the reducido tier carried
its ordinary 10 % (recargo 1,4 %) and the transitional 5 % (recargo 0,62 %) at
the same time. A tier-keyed lookup cannot say which applies to a given line.

Real-behaviour: the committed registry table through the real loader. Nothing is
stubbed, and the expected figures come from the bundled corpus -- RDL 20/2022
art. 72 and RDL 4/2024 art. 1 state each IVA rate beside its recargo -- not from
the table under test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._recargo_equivalencia import (
    RecargoRateRecord,
    load_recargo_rate_table,
    load_recargo_rates,
    recargo_rate_for_applied_rate,
)
from ..errors import IvaValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Inside the window where the ordinary and transitional reduced rates coexist.
_COLLISION_DATE = date(2024, 8, 15)
#: Inside the Q4 2024 step, after the transitional rates increased.
_STEP_DATE = date(2024, 11, 15)


def test_the_two_reduced_rates_resolve_distinctly_on_one_date() -> None:
    """The collision case, and the entire reason this lookup is rate-keyed.

    Both rates sit on the reducido tier on this date. A tier-keyed lookup
    returns one answer for both; this must return two.
    """
    ordinary = recargo_rate_for_applied_rate(Decimal("0.10"), _COLLISION_DATE)
    transitional = recargo_rate_for_applied_rate(Decimal("0.05"), _COLLISION_DATE)

    assert ordinary == Decimal("0.014")
    assert transitional == Decimal("0.0062")
    assert ordinary != transitional


def test_the_quarter_four_step_moves_both_transitional_pairings() -> None:
    """RDL 4/2024 raised the food rates on 1 October 2024, recargos with them."""
    assert recargo_rate_for_applied_rate(Decimal("0.075"), _STEP_DATE) == Decimal("0.01")
    assert recargo_rate_for_applied_rate(Decimal("0.02"), _STEP_DATE) == Decimal("0.0026")
    # And the earlier pairings are gone by then, rather than lingering.
    assert recargo_rate_for_applied_rate(Decimal("0.05"), _STEP_DATE) is None


def test_a_zero_rated_pairing_is_a_rate_of_zero_not_an_absent_one() -> None:
    """Art. 72 gives its 0 % foods a recargo "del 0 por ciento" -- a rate.

    Distinct from an unmodelled combination, which yields ``None``. The
    difference matters because a zero-rated supply is inside the recargo regime
    carrying the obligation at zero, where an unmodelled one says only that this
    table cannot answer.
    """
    inside = recargo_rate_for_applied_rate(Decimal("0.00"), _COLLISION_DATE)

    assert inside == Decimal("0")
    assert inside is not None


@pytest.mark.parametrize(
    ("applied_rate", "on_date", "why"),
    [
        (Decimal("0.05"), date(2026, 6, 1), "transitional rate, long after its window closed"),
        (Decimal("0.03"), _COLLISION_DATE, "a rate Spain never charged"),
        (Decimal("0.21"), date(1990, 1, 1), "before the regime existed"),
    ],
)
def test_an_unmodelled_combination_returns_nothing_rather_than_a_near_match(
    applied_rate: Decimal,
    on_date: date,
    why: str,
) -> None:
    """No nearest-match fallback: an unmodelled pairing must refuse to guess."""
    assert recargo_rate_for_applied_rate(applied_rate, on_date) is None, why


def test_the_ordinary_rates_match_the_operator_reviewed_parameters() -> None:
    """The operational table must not drift from the reviewed legal record.

    The art. 161 rates exist twice by design: as operator-reviewed legal
    parameters, which are the grounding record, and in this table, which is the
    lookup. Two stores of one number drift unless something checks, so this is
    that check rather than a restatement.
    """
    reviewed = load_recargo_rates()
    pairs = {
        Decimal("0.21"): reviewed.general_rate,
        Decimal("0.10"): reviewed.reducido_rate,
        Decimal("0.04"): reviewed.super_reducido_rate,
    }

    for iva_rate, reviewed_recargo in pairs.items():
        assert recargo_rate_for_applied_rate(iva_rate, _COLLISION_DATE) == reviewed_recargo


def test_overlapping_windows_for_one_rate_are_refused() -> None:
    """An ambiguous key must refuse, not answer with whichever record is first.

    Silently answering from an ambiguous key is precisely what made the
    tier-keyed shape unsafe, so the replacement refuses instead of ordering.
    """
    from .._recargo_equivalencia import _reject_overlapping_windows

    overlapping = (
        RecargoRateRecord(
            iva_rate=Decimal("0.10"),
            recargo_rate=Decimal("0.014"),
            effective_from=date(2023, 1, 1),
            effective_until=date(2024, 12, 31),
            legal_refs=("ley-37-1992:art-161",),
        ),
        RecargoRateRecord(
            iva_rate=Decimal("0.10"),
            recargo_rate=Decimal("0.02"),
            effective_from=date(2024, 1, 1),
            effective_until=None,
            legal_refs=("ley-37-1992:art-161",),
        ),
    )

    with pytest.raises(IvaValidationError, match="overlapping windows"):
        _reject_overlapping_windows(overlapping)


def test_the_committed_table_carries_grounding_on_every_record() -> None:
    """Every pairing states the provision that establishes it.

    A recargo rate is a regulatory value, so a record without a binding
    reference cannot ship whatever its number says.
    """
    for record in load_recargo_rate_table():
        assert record.legal_refs, f"recargo pairing for IVA rate {record.iva_rate} carries no legal_refs"
