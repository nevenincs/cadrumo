"""What the published rate schedule answers, and what a projected rate may prove.

Expected figures come from the bundled sources, not from a run: Ley 41/1994 art. 78
(16 % and 7 % from 1995), the AEAT 2020 IVA manual's art. 90 and 91 footnotes (18 %
and 8 % until 31 August 2012), and RDL 20/2012 art. 23 (21 % and 10 % from the next day).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...invoices.enums import IvaRate, iva_rate_percentage, iva_rate_slot_is_published, resolve_iva_rate_slot
from ...invoices.figures import FigureFindingCode, compute_line_figures, dated_rate_slots
from ...transactions.retencion_facts import load_retencion_actividades_rates
from ..errors import IvaRateNotFoundError
from ..lookup import (
    coexisting_tier_rates,
    lookup_published_rate,
    lookup_rate,
    rate_kinds_for_declared_rate,
    rate_table_covers,
    tier_rates_within,
)
from ..schema import EUMemberState, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ES = EUMemberState.from_registry("es")
_DE = EUMemberState.from_registry("de")
_GENERAL = IvaRateKind("general")
_REDUCED = IvaRateKind("reduced")
_SUPER_REDUCED = IvaRateKind("super_reduced")
_ZERO = IvaRateKind("zero")

_LAST_DAY_OF_18 = date(2012, 8, 31)
_FIRST_DAY_OF_21 = date(2012, 9, 1)
_FIRST_DAY_OF_16 = date(1995, 1, 1)
_LAST_DAY_16_IS_CERTAIN = date(2009, 12, 23)


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned, validating_governed_facts(pinned):
        yield pinned


@pytest.mark.parametrize(
    ("kind", "on_date", "pct"),
    [
        (_GENERAL, _FIRST_DAY_OF_16, "16"),
        (_REDUCED, _FIRST_DAY_OF_16, "7"),
        (_SUPER_REDUCED, _FIRST_DAY_OF_16, "4"),
        (_GENERAL, _LAST_DAY_16_IS_CERTAIN, "16"),
        (_REDUCED, _LAST_DAY_16_IS_CERTAIN, "7"),
        (_GENERAL, _LAST_DAY_OF_18, "18"),
        (_REDUCED, _LAST_DAY_OF_18, "8"),
        (_GENERAL, _FIRST_DAY_OF_21, "21"),
        (_REDUCED, _FIRST_DAY_OF_21, "10"),
    ],
)
def test_a_sourced_rate_is_published_for_its_date(
    operation: PinnedAuthorityOperation,
    kind: IvaRateKind,
    on_date: date,
    pct: str,
) -> None:
    record = lookup_rate(_ES, kind, on_date, operation=operation)

    assert record.pct == Decimal(pct)
    assert record.published_on_date
    assert lookup_published_rate(_ES, kind, on_date, operation=operation).pct == Decimal(pct)


def test_the_unsourced_stretch_reads_the_nearest_edition_on_each_side(operation: PinnedAuthorityOperation) -> None:
    gap_days = (_LAST_DAY_OF_18 - _LAST_DAY_16_IS_CERTAIN).days
    midpoint = _LAST_DAY_16_IS_CERTAIN + timedelta(days=gap_days // 2)

    before = lookup_rate(_ES, _GENERAL, midpoint - timedelta(days=1), operation=operation)
    after = lookup_rate(_ES, _GENERAL, midpoint + timedelta(days=1), operation=operation)

    assert (before.pct, before.published_on_date, before.projected_from_date) == (
        Decimal("16"),
        False,
        _LAST_DAY_16_IS_CERTAIN,
    )
    assert (after.pct, after.published_on_date, after.projected_from_date) == (
        Decimal("18"),
        False,
        _LAST_DAY_OF_18,
    )


def test_a_date_before_every_edition_reads_the_first(operation: PinnedAuthorityOperation) -> None:
    record = lookup_rate(_ES, _GENERAL, _FIRST_DAY_OF_16 - timedelta(days=1), operation=operation)

    assert (record.pct, record.published_on_date, record.projected_from_date) == (
        Decimal("16"),
        False,
        _FIRST_DAY_OF_16,
    )


def test_a_foreign_tier_before_its_first_edition_reads_it(operation: PinnedAuthorityOperation) -> None:
    first = lookup_rate(_DE, _GENERAL, date(date.today().year, 12, 31), operation=operation)
    record = lookup_rate(_DE, _GENERAL, first.effective_from - timedelta(days=1), operation=operation)

    assert record.pct == first.pct
    assert not record.published_on_date
    assert record.projected_from_date == first.effective_from


def test_the_spanish_zero_tier_answers_zero_outside_its_temporary_windows(operation: PinnedAuthorityOperation) -> None:
    on_date = date(date.today().year, 1, 15)

    assert lookup_rate(_ES, _ZERO, on_date, operation=operation).pct == Decimal("0")
    assert IvaRate.from_registry("RATE_0") == resolve_iva_rate_slot(Decimal("0"), on_date)


def test_a_tier_the_state_has_never_had_stays_refused(operation: PinnedAuthorityOperation) -> None:
    """A rate the state's table never held is another question than a date's edition."""
    with pytest.raises(IvaRateNotFoundError):
        lookup_rate(_DE, _SUPER_REDUCED, date(date.today().year, 1, 15), operation=operation)


def test_published_lookup_refuses_a_projected_rate_as_a_coverage_gap(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(IvaRateNotFoundError) as refused:
        lookup_published_rate(_ES, _GENERAL, _FIRST_DAY_OF_16 - timedelta(days=1), operation=operation)

    assert refused.value.context is not None
    assert refused.value.context["rate_registry_covers_date"] is False


@pytest.mark.parametrize(
    ("slot", "on_date"),
    [
        ("RATE_5", date(2024, 10, 1)),
        ("RATE_2", date(2025, 1, 1)),
        ("RATE_7.5", date(2025, 1, 1)),
    ],
)
def test_a_temporary_measure_ends_where_its_law_ends_it(
    operation: PinnedAuthorityOperation,
    slot: str,
    on_date: date,
) -> None:
    """RDL 4/2024 art. 1: 5 % to 30 September 2024, 2 % and 7.5 % to 31 December 2024."""
    assert iva_rate_percentage(IvaRate.from_registry(slot), on_date - timedelta(days=1)) is not None
    with pytest.raises(IvaRateNotFoundError):
        iva_rate_percentage(IvaRate.from_registry(slot), on_date)
    assert coexisting_tier_rates(_ES, _REDUCED, date(date.today().year, 1, 15), operation=operation) == ()


def test_a_declared_rate_is_never_confirmed_by_a_projected_one(operation: PinnedAuthorityOperation) -> None:
    """16 % is the nearest edition's rate; the date's own published table does not hold it."""
    on_date = _LAST_DAY_16_IS_CERTAIN + timedelta(days=30)

    assert lookup_rate(_ES, _GENERAL, on_date, operation=operation).pct == Decimal("16")
    assert rate_kinds_for_declared_rate(_ES, Decimal("0.16"), on_date, operation=operation) == ()
    assert not rate_table_covers(_ES, on_date, _GENERAL, operation=operation)
    with pytest.raises(IvaRateNotFoundError):
        resolve_iva_rate_slot(Decimal("16"), on_date)


def test_a_declared_rate_on_a_published_date_is_judged_against_the_law(operation: PinnedAuthorityOperation) -> None:
    assert _GENERAL in rate_kinds_for_declared_rate(_ES, Decimal("0.18"), _LAST_DAY_OF_18, operation=operation)
    assert rate_kinds_for_declared_rate(_ES, Decimal("0.21"), _LAST_DAY_OF_18, operation=operation) == ()
    assert resolve_iva_rate_slot(Decimal("18"), _LAST_DAY_OF_18) == IvaRate.from_registry("RATE_21")
    with pytest.raises(IvaRateNotFoundError):
        resolve_iva_rate_slot(Decimal("21"), _LAST_DAY_OF_18)


def test_tier_rates_within_names_only_published_rates(operation: PinnedAuthorityOperation) -> None:
    rates = tier_rates_within(
        _ES,
        _GENERAL,
        _LAST_DAY_16_IS_CERTAIN + timedelta(days=30),
        _LAST_DAY_OF_18 + timedelta(days=30),
        operation=operation,
    )

    assert rates == (Decimal("18"), Decimal("21"))


def test_a_line_on_a_projected_rate_prices_and_is_not_judged_wrong(operation: PinnedAuthorityOperation) -> None:
    """Base 100 at the nearest edition's 16 % gives 16.00; a stated 18.00 is unverifiable, not wrong."""
    on_date = _LAST_DAY_16_IS_CERTAIN + timedelta(days=30)
    general = IvaRate.from_registry("RATE_21")
    slot = next(item for item in dated_rate_slots(on_date) if item.slot == general)

    assert slot.fraction == Decimal("0.16")
    assert slot.projected_on == on_date
    assert not iva_rate_slot_is_published(general, on_date)

    agreeing = compute_line_figures(
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        stated_subtotal=Decimal("100"),
        stated_iva_amount=Decimal("16.00"),
        slot=slot,
    )
    assert agreeing.iva_amount.computed == Decimal("16.00")
    assert agreeing.findings == ()

    differing = compute_line_figures(
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        stated_subtotal=Decimal("100"),
        stated_iva_amount=Decimal("18.00"),
        slot=slot,
    )
    assert [finding.code for finding in differing.findings] == [FigureFindingCode.LINE_RATE_COVERAGE_GAP]


def test_a_line_on_a_published_rate_is_still_judged(operation: PinnedAuthorityOperation) -> None:
    """Base 100 on the last day of 18 % gives 18.00, so a stated 21.00 is wrong in law."""
    general = IvaRate.from_registry("RATE_21")
    slot = next(item for item in dated_rate_slots(_LAST_DAY_OF_18) if item.slot == general)

    assert slot.projected_on is None
    figures = compute_line_figures(
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        stated_subtotal=Decimal("100"),
        stated_iva_amount=Decimal("21.00"),
        slot=slot,
    )
    assert [finding.code for finding in figures.findings] == [FigureFindingCode.LINE_IVA_MISMATCH]


def test_a_retention_rate_answers_below_the_floor_and_before_its_first_edition(
    operation: PinnedAuthorityOperation,
) -> None:
    """RIRPF art. 95: 15 % as authored from April 2007, and carried back from that edition."""
    floor = operation.supported_filing_years().date_envelope().floor

    assert load_retencion_actividades_rates(
        effective_date=date(2010, 6, 15),
        authority=operation,
    ).general_rate == Decimal("0.15")
    assert floor.year > 2010
    assert load_retencion_actividades_rates(
        effective_date=date(2007, 3, 31),
        authority=operation,
    ).general_rate == Decimal("0.15")
