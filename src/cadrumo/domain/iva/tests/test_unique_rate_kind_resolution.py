"""Exact-one rate-kind projection over the installed published IVA authority."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.tests.published_authority import published_legal_reference
from ..lookup import (
    rate_kinds_for_declared_rate,
    select_unique_rate_kind,
    unique_rate_kind_for_declared_rate,
)
from ..rates import load_iva_rate_table
from ..schema import EUMemberState, IvaRateKind, spanish_eu_member_state

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

# The temporary rates are bounded by RD-ley 4/2024 art. 1; its window is read from the
# published provision.
_RDL_4_2024 = published_legal_reference("real-decreto-ley-4-2024:art-1")
assert _RDL_4_2024.effective_to is not None
_WINDOW_OPENS = _RDL_4_2024.effective_from
_WINDOW_CLOSES = _RDL_4_2024.effective_to
_WINDOW_YEAR = _WINDOW_OPENS.year
_AFTER_WINDOW = _WINDOW_CLOSES + timedelta(days=1)

_ES = EUMemberState.from_registry("es")
_GENERAL = IvaRateKind("general")
_REDUCED = IvaRateKind("reduced")
_SUPER_REDUCED = IvaRateKind("super_reduced")
_ZERO = IvaRateKind("zero")


@pytest.mark.parametrize(
    ("declared_rate", "on_date", "expected"),
    [
        (Decimal("0.05"), _WINDOW_OPENS, _REDUCED),
        (Decimal("0.02"), date(_WINDOW_YEAR, 10, 1), _SUPER_REDUCED),
        (Decimal("0.075"), _WINDOW_CLOSES, _REDUCED),
        (Decimal("0"), _AFTER_WINDOW, _ZERO),
        (Decimal("0.02"), _AFTER_WINDOW, None),
    ],
)
def test_unique_projection_uses_published_rate_windows(
    operation: PinnedAuthorityOperation,
    declared_rate: Decimal,
    on_date: date,
    expected: IvaRateKind | None,
) -> None:
    member_state = spanish_eu_member_state(effective_date=on_date, authority=operation)

    assert unique_rate_kind_for_declared_rate(member_state, declared_rate, on_date, operation=operation) == expected


def test_published_spanish_rate_boundaries_have_no_distinct_tier_ambiguity(
    operation: PinnedAuthorityOperation,
) -> None:
    """Scan every date boundary derived from installed Spanish rate rows.

    This is evidence about the current publication, not an assertion that an
    ambiguity cannot be authored later. Repeated numeric records inside one
    tier remain one match; only multiple distinct returned kinds are ambiguous.
    """
    records = load_iva_rate_table(operation=operation)[_ES]
    support = operation.supported_filing_years().date_envelope()
    latest_supported = support.hard_ceiling or support.horizon
    boundaries: set[date] = set()
    for record in records:
        boundaries.add(record.effective_from)
        if record.effective_until is not None:
            boundaries.add(record.effective_until)
            if record.effective_until < date.max:
                boundaries.add(record.effective_until + timedelta(days=1))

    admitted_boundaries = sorted(on_date for on_date in boundaries if support.floor <= on_date <= latest_supported)
    assert admitted_boundaries
    for on_date in admitted_boundaries:
        active_rates = tuple(
            record
            for record in records
            if record.effective_from <= on_date
            and (record.effective_until is None or on_date <= record.effective_until)
        )
        declared_rates = {record.pct / Decimal("100") for record in active_rates} | {Decimal("0")}
        member_state = spanish_eu_member_state(effective_date=on_date, authority=operation)
        for declared_rate in declared_rates:
            matches = rate_kinds_for_declared_rate(member_state, declared_rate, on_date, operation=operation)
            assert len(matches) <= 1, (
                f"published Spanish rate {declared_rate} resolves to distinct tiers "
                f"{tuple(kind.value for kind in matches)} on {on_date}"
            )
            expected = matches[0] if matches else None
            assert (
                unique_rate_kind_for_declared_rate(member_state, declared_rate, on_date, operation=operation)
                == expected
            )


@pytest.mark.parametrize(
    ("matches", "expected"),
    [
        ((), None),
        ((_GENERAL,), _GENERAL),
        ((_GENERAL, _REDUCED), None),
    ],
)
def test_private_cardinality_rule_selects_only_one_distinct_tier(
    matches: tuple[IvaRateKind, ...],
    expected: IvaRateKind | None,
) -> None:
    """Exercise the pure cardinality guard without inventing authority rows."""
    assert select_unique_rate_kind(matches) == expected
