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

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ..recargo_equivalencia import (
    IVA_RECARGO_FACT_ID,
    recargo_rate_record_for_applied_rate,
    resolve_recargo_rate_for_applied_rate,
)

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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        ordinary = recargo_rate_record_for_applied_rate(
            Decimal("0.10"), _COLLISION_DATE, operation=_authority_operation_for_test
        )
        transitional = recargo_rate_record_for_applied_rate(
            Decimal("0.05"), _COLLISION_DATE, operation=_authority_operation_for_test
        )

        assert ordinary is not None and transitional is not None
        assert ordinary.recargo_rate == Decimal("0.014")
        assert transitional.recargo_rate == Decimal("0.0062")
        assert ordinary.recargo_rate != transitional.recargo_rate


def test_recargo_lookup_retains_the_matched_authority_provenance() -> None:
    """The public rate projection has the exact applied-rate fact evidence."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        resolved = resolve_recargo_rate_for_applied_rate(
            Decimal("0.05"), _COLLISION_DATE, operation=_authority_operation_for_test
        )
        record = recargo_rate_record_for_applied_rate(
            Decimal("0.05"), _COLLISION_DATE, operation=_authority_operation_for_test
        )

        assert record is not None
        assert record.iva_rate == Decimal("0.05")
        assert record.recargo_rate == Decimal("0.0062")
        assert (record.effective_from, record.effective_until) == (resolved.valid_from, resolved.valid_to)
        assert record.legal_refs == resolved.legal_refs
        assert resolved.fact_id == "iva-recargo-by-applied-rate"
        assert resolved.date_axis.value == "devengo_date"
        assert resolved.effective_date == _COLLISION_DATE
        assert {selector.name: selector.value for selector in resolved.matched_selectors} == {
            "applied_rate": Decimal("0.05"),
        }
        assert resolved.legal_refs
        assert len(resolved.authority_digest) == 64


def test_the_quarter_four_step_moves_both_transitional_pairings() -> None:
    """RDL 4/2024 raised the food rates on 1 October 2024, recargos with them."""
    with _indexed_authority_for_test().operation() as operation:
        for applied_rate, expected in (("0.075", "0.01"), ("0.02", "0.0026")):
            record = recargo_rate_record_for_applied_rate(Decimal(applied_rate), _STEP_DATE, operation=operation)
            assert record is not None
            assert record.recargo_rate == Decimal(expected)
        assert recargo_rate_record_for_applied_rate(Decimal("0.05"), _STEP_DATE, operation=operation) is None


def test_a_zero_rated_pairing_is_a_rate_of_zero_not_an_absent_one() -> None:
    """Art. 72's zero recargo remains a grounded record, rather than absence."""
    with _indexed_authority_for_test().operation() as operation:
        record = recargo_rate_record_for_applied_rate(Decimal("0.00"), _COLLISION_DATE, operation=operation)
        assert record is not None
        assert record.recargo_rate == Decimal("0")
        assert record.legal_refs


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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        assert (
            recargo_rate_record_for_applied_rate(applied_rate, on_date, operation=_authority_operation_for_test) is None
        ), why


def test_published_pairings_are_grounded_and_supported_windows_resolve() -> None:
    """Historical facts retain grounding; supported windows use the runtime resolver."""
    with _indexed_authority_for_test().operation() as operation:
        fact = operation.governed_fact(IVA_RECARGO_FACT_ID)
        assert fact.variants, "the published pairing catalogue must not be empty"
        support = operation.supported_filing_years()
        resolved_count = 0
        for variant in fact.variants:
            assert variant.legal_refs, "every historical pairing must retain its grounding"
            assert variant.valid_from is not None
            probe_date = max(variant.valid_from, date(support.floor, 1, 1))
            if not support.admits_coordinate(probe_date.year) or (
                variant.valid_to is not None and variant.valid_to < probe_date
            ):
                continue
            selector = next(selector for selector in variant.selectors if selector.name == "applied_rate")
            applied_rate = Decimal(str(selector.value))
            record = recargo_rate_record_for_applied_rate(applied_rate, probe_date, operation=operation)
            assert record is not None
            assert record.legal_refs, f"recargo pairing for IVA rate {applied_rate} carries no legal_refs"
            assert record.legal_refs == variant.legal_refs
            resolved_count += 1
        assert resolved_count > 0, "the published catalogue must exercise at least one supported pairing"
