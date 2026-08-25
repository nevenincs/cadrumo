"""Period-versioned IVA rate lookup tests.

Confirms that :func:`cadrumo.domain.iva.lookup_rate` resolves the correct
:class:`cadrumo.domain.iva.IvaRateRecord` record across the 2024 / 2025 ES window
boundary, and that the committed registry has no overlapping effective
windows.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest

from .. import EUMemberState, IvaRateKind, load_iva_rate_table, lookup_rate, rate_kinds_for_declared_rate
from ..errors import IvaRateNotFoundError, IvaRateOverlapError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_es_general_2024_rate() -> None:
    """A 2024 date resolves the 21 % general rate.

    ``effective_from`` is 2012-09-01, not 2024-01-01. The earlier value was a
    bulk-refresh boundary sitting in a field defined as "First date the rate
    applies", so the table asserted the general rate began in 2024 -- and this
    test asserted it back. RDL 20/2012 art. 23.Dos fixed 21 % from 1 September
    2012 and nothing has changed it since.
    """
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2024, 6, 15))
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2012, 9, 1)
    assert rate.effective_until == date(2024, 12, 31)


def test_es_general_2025_rate() -> None:
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2025, 6, 15))
    assert rate.pct == Decimal("21")
    assert rate.effective_from == date(2025, 1, 1)
    assert rate.effective_until is None


def test_es_general_2024_last_day() -> None:
    """December 31 2024 still resolves to the 2024 record."""
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2024, 12, 31))
    assert rate.effective_until == date(2024, 12, 31)


def test_es_general_2025_first_day() -> None:
    """January 1 2025 resolves to the 2025 record (no overlap)."""
    rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2025, 1, 1))
    assert rate.effective_from == date(2025, 1, 1)


def test_es_super_reduced_2024_and_2025_both_resolve() -> None:
    """The 4 % super-reducido is registered for both years."""
    rate_2024 = lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, date(2024, 6, 15))
    rate_2025 = lookup_rate(EUMemberState.ES, IvaRateKind.SUPER_REDUCED, date(2025, 6, 15))
    assert rate_2024.pct == Decimal("4")
    assert rate_2025.pct == Decimal("4")


def test_es_reduced_2024_and_2025_both_resolve() -> None:
    """The 10 % reducido is registered for both years."""
    rate_2024 = lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, date(2024, 6, 15))
    rate_2025 = lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, date(2025, 6, 15))
    assert rate_2024.pct == Decimal("10")
    assert rate_2025.pct == Decimal("10")


def test_es_lookup_before_the_general_rate_existed_raises() -> None:
    """A date before 1 September 2012 has no registered general rate, and must refuse.

    This replaces an assertion that 2023 raises. That was true of the table and
    false of the law: the boundary it pinned was a refresh artefact, so the test
    encoded the defect as the contract and would have kept the correction out.

    The boundary is still real and still worth a gate -- it has simply moved to
    where the statute puts it. Before RDL 20/2012 took effect the general rate
    was 18 %, which this table does not carry, so 2012-08-31 must refuse while
    2012-09-01 resolves. Both directions are asserted, because a refusal test
    with no matching acceptance cannot tell a boundary from a blanket gap.
    """
    with pytest.raises(IvaRateNotFoundError, match=r"ES|GENERAL|2012|rate"):
        lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2012, 8, 31))

    assert lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2012, 9, 1)).pct == Decimal("21")


def test_es_pre_2024_years_inside_prescripcion_now_resolve() -> None:
    """2022 and 2023 price correctly, which is the point of the correction.

    Both years sit inside the four-year prescripción window, and the registry
    declares pre-2024 revisions on more than thirty modelos, so a taxpayer
    amending either year needs the rate. Before the correction every tier
    refused for both.
    """
    for year in (2022, 2023):
        assert lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(year, 6, 1)).pct == Decimal("21")
        assert lookup_rate(EUMemberState.ES, IvaRateKind.REDUCED, date(year, 6, 1)).pct == Decimal("10")


def test_committed_registry_has_no_overlapping_windows() -> None:
    """No two TIER-DEFINING rates claim the same tier at the same moment.

    Scoped to records that define what a tier means, mirroring the loader's own
    rule. A ``supersedes_tier_default`` rate exists precisely to overlap: a
    statute applied it to part of a tier's supplies while the rest stayed on the
    ordinary rate, so both are simultaneously correct and neither replaces the
    other. Asserting over those would reject the shape the registry is meant to
    carry; asserting only over them would let two genuine tier definitions
    collide, which is the ambiguity ``lookup_rate`` depends on this invariant to
    prevent.
    """
    for member_state, rates in load_iva_rate_table().items():
        by_kind: dict[IvaRateKind, list[tuple[date, date]]] = {}
        for rate in rates:
            if rate.supersedes_tier_default:
                continue
            by_kind.setdefault(rate.kind, []).append((rate.effective_from, rate.effective_until or date.max))
        for kind, windows in by_kind.items():
            ordered = sorted(windows)
            for previous, current in pairwise(ordered):
                if previous[1] >= current[0]:
                    raise IvaRateOverlapError(f"{member_state.value}/{kind.value}: {previous} overlaps {current}")


def test_a_declared_zero_resolves_to_the_zero_tier_on_every_date() -> None:
    """0 % is always a legitimate Spanish declared rate, whatever the table records.

    Spain zero-rates on FOUR grounds, three of them permanent: exports to a
    third country (LIVA art. 21), intra-community supplies (art. 25), entregas
    of donativos to Ley 49/2002 entities (art. 91.Cuatro), and the temporary
    RD-ley 4/2024 basic-foods window. ``rates.toml`` records only the last --
    and says so itself, because a flat ``kind = "zero"`` record cannot be
    bounded to a class of supply.

    Reading that partial table as exhaustive made ``rate_kinds_for_declared_rate``
    answer nothing for 0 % outside July-September 2024, so every export and
    intra-EU supply became unclassifiable at any other date -- live for 2025 and
    2026, not a historical-fixture problem. Seventeen tests failed on it.

    Whether a PARTICULAR supply was entitled to zero-rating is a question about
    the supply, and it lives on the category axis, which can tell
    ``DOMESTIC_ZERO`` from ``EXPORT_THIRD_COUNTRY_ZERO_RATED``. The rate axis
    structurally cannot express it, so it must not pretend to answer it.
    """
    for on_date in (date(2024, 3, 15), date(2024, 8, 15), date(2024, 11, 15), date(2025, 6, 1), date(2026, 6, 1)):
        assert rate_kinds_for_declared_rate(EUMemberState.ES, Decimal("0"), on_date) == (IvaRateKind.ZERO,), (
            f"0 % must resolve to the zero tier on {on_date.isoformat()}: the table's silence about a zero "
            "record is incomplete coverage, not a statement that zero-rating was unlawful that day"
        )


def test_the_zero_exemption_does_not_leak_into_the_dated_temporary_rates() -> None:
    """Control: the RD-ley 4/2024 rates stay window-bound, so the narrowing is not reverted.

    The zero answer is unconditional; nothing else is. Without this the fix
    above could have been implemented by making every rate date-blind, which
    would re-admit a 2 % foodstuffs line in 2025 -- a rate the statute had
    withdrawn, and precisely what the tax review closed.

    Each rate is checked both INSIDE its own window and OUTSIDE it, so the
    assertion fails if the window collapses in either direction.
    """
    inside_summer = date(2024, 8, 15)
    inside_autumn = date(2024, 11, 15)
    after = date(2025, 6, 1)

    assert rate_kinds_for_declared_rate(EUMemberState.ES, Decimal("0.05"), inside_summer) == (IvaRateKind.REDUCED,)
    assert rate_kinds_for_declared_rate(EUMemberState.ES, Decimal("0.02"), inside_autumn) == (
        IvaRateKind.SUPER_REDUCED,
    )
    assert rate_kinds_for_declared_rate(EUMemberState.ES, Decimal("0.075"), inside_autumn) == (IvaRateKind.REDUCED,)

    for withdrawn in (Decimal("0.02"), Decimal("0.05"), Decimal("0.075")):
        assert rate_kinds_for_declared_rate(EUMemberState.ES, withdrawn, after) == (), (
            f"{withdrawn} must not resolve in 2025 -- the temporary windows closed, and a date-blind fix "
            "would silently re-admit a rate the statute withdrew"
        )
