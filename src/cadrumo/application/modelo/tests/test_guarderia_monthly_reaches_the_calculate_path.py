"""The month-level guardería map must REACH the 0613 terms, not merely persist.

The Art. 81.2 month rules landed on the canonical record, and the entry surface
that can write them landed after. Between the two there was a third thing, found
while building the second: the derived-facts injector carried its OWN loop
summing ``renta_family.descendiente.{n}.gastos_guarderia`` under an inline
``age < 3`` test, so it never read the canonical record at all.

That is a second aggregation path, and it had already diverged. A descendant
declaring only the monthly map contributed the annual field's absent zero, so a
taxpayer could enter their spend through the new surface, see it stored, and
receive nothing — strictly worse than the gap the surface closes, because before
it they at least knew the feature did not exist.

These tests drive the production resolver over real profile records through the
resident registry authority, and assert the binding VALUES the 0613 formula
consumes. No expected figure here is a tax outcome derived from the registry
formula: each is the arithmetic of the fixture's own declared months, which is
what "did this spend arrive" means.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache

import pytest

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.contribuyente import (
    DescendantInfo,
    descendant_facts_from_list,
    parse_guarderia_mensual,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..profile_binding import ProfileBindingResolutionError, resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000613"
_T0 = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
_YEAR = 2024

#: The two bindings the 0613 formula multiplies and minimises over.
_SPEND_BINDING = "renta-2024-profile-guarderia-gastos-reales"
_COUNT_BINDING = "renta-2024-profile-descendientes-guarderia"


@lru_cache
def _snapshot() -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=_YEAR, period="0A")


def _resolved(*descendientes: DescendantInfo) -> dict[str, Decimal]:
    """Resolve the profile-sourced bindings for a record carrying *descendientes*."""
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=tuple(
            UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendientes)
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    resolution = resolve_profile_sourced_bindings(_snapshot(), bucket_id=_BUCKET, profile_record=record)
    return dict(resolution.binding_values)


def _monthly(raw: str) -> tuple[object, ...]:
    return parse_guarderia_mensual(raw, field="probe")


def test_a_monthly_map_reaches_the_spend_binding() -> None:
    """The regression this file exists for.

    A child under three for the whole period, with spend declared ONLY as a
    monthly map. The injector's own loop read the annual field and found
    nothing, so this resolved to zero while the record held 720 euros.
    """
    child = DescendantInfo(
        birth_date=date(2022, 6, 1),
        gastos_guarderia_mensuales=_monthly("1-4:180"),  # type: ignore[arg-type]
    )

    resolved = _resolved(child)

    assert resolved[_SPEND_BINDING] == Decimal("720")


def test_the_annual_figure_still_reaches_the_spend_binding() -> None:
    """The path every existing profile uses is unchanged by the delegation."""
    child = DescendantInfo(birth_date=date(2022, 6, 1), gastos_guarderia_euros=900)

    resolved = _resolved(child)

    assert resolved[_SPEND_BINDING] == Decimal("900")


def test_every_declared_month_reaches_the_binding_in_the_turning_three_period() -> None:
    """The third birthday is not a boundary for the Art. 81.2 increment.

    "los gastos incurridos con posterioridad al cumplimiento de dicha edad"
    GRANTS the months after the birthday, which the under-three limb cannot
    reach; it does not withdraw the ones before. Capítulo 18's worked case
    settles it — a child turning three in September is granted January to June.

    The child here turns three in April, and all eight declared months reach the
    binding. Nothing derives the upper bound: the months a taxpayer can evidence
    are the months their childcare centre determined and reported.
    """
    child = DescendantInfo(
        birth_date=date(2021, 4, 15),
        gastos_guarderia_mensuales=_monthly("1-4:180;5-8:210"),  # type: ignore[arg-type]
    )

    resolved = _resolved(child)

    assert resolved[_SPEND_BINDING] == Decimal("1560")  # 4x180 + 4x210


def test_an_annual_only_figure_contributes_nothing_in_the_turning_three_period() -> None:
    """An annual total cannot be apportioned to a window whose upper edge is not derived.

    The reason is the closing month, not the birthday, which draws no line: the
    region determines when the second infant-education cycle may begin, and this
    application declines to compute that. Zero here is the honest answer rather
    than a withheld window — the figure on record cannot be split, so granting
    any part of it would be inventing the split. The operator is told separately,
    by the calculate-path advisory, that the fix is the monthly detail their
    centre already certified.
    """
    child = DescendantInfo(birth_date=date(2021, 4, 15), gastos_guarderia_euros=2400)

    resolved = _resolved(child)

    assert resolved[_SPEND_BINDING] == Decimal("0")


def test_the_turning_three_child_is_counted_in_the_cap_population() -> None:
    """Otherwise the cap term zeroes exactly the spend the extension admits.

    ``0613 = min(gastos_reales, count x 1000, cotizaciones)``. A turning-three
    child is not "menor de 3 al devengo", so the Art. 58.2 population excludes
    them — and a household whose only child is in that period would be capped at
    zero, handing straight back the under-grant the extension exists to close.
    """
    child = DescendantInfo(
        birth_date=date(2021, 4, 15),
        gastos_guarderia_mensuales=_monthly("5-8:210"),  # type: ignore[arg-type]
    )

    resolved = _resolved(child)

    assert resolved[_COUNT_BINDING] == Decimal("1")


def test_a_child_past_the_turning_three_period_contributes_nothing_and_is_not_counted() -> None:
    """The widening stops at the extension's edge; it is not an open door."""
    child = DescendantInfo(
        birth_date=date(2019, 4, 15),
        gastos_guarderia_mensuales=_monthly("1-12:210"),  # type: ignore[arg-type]
    )

    resolved = _resolved(child)

    assert resolved[_SPEND_BINDING] == Decimal("0")
    assert resolved[_COUNT_BINDING] == Decimal("0")


def test_a_non_cohabiting_child_contributes_nothing() -> None:
    """Cohabitation gates the whole Art. 58 limb, monthly map or not."""
    child = DescendantInfo(
        birth_date=date(2022, 6, 1),
        convive_con_contribuyente=False,
        gastos_guarderia_mensuales=_monthly("1-4:180"),  # type: ignore[arg-type]
    )

    resolved = _resolved(child)

    assert resolved[_SPEND_BINDING] == Decimal("0")
    assert resolved[_COUNT_BINDING] == Decimal("0")


def test_mixed_households_sum_each_child_under_its_own_rule() -> None:
    """One profile, three children, three different Art. 81.2 outcomes.

    Proves the terms are per-child and then summed, rather than one rule applied
    to whichever child the loop met first.
    """
    under_three_monthly = DescendantInfo(
        birth_date=date(2022, 6, 1),
        gastos_guarderia_mensuales=_monthly("1-4:180"),  # type: ignore[arg-type]
    )
    under_three_annual = DescendantInfo(birth_date=date(2023, 2, 10), gastos_guarderia_euros=600)
    turning_three = DescendantInfo(
        birth_date=date(2021, 4, 15),
        gastos_guarderia_mensuales=_monthly("1-4:180;5-8:210"),  # type: ignore[arg-type]
    )

    resolved = _resolved(under_three_monthly, under_three_annual, turning_three)

    assert resolved[_SPEND_BINDING] == Decimal("2880")  # 720 + 600 + 1560
    assert resolved[_COUNT_BINDING] == Decimal("3")


def test_an_unparseable_stored_birth_date_still_refuses_by_index() -> None:
    """The named refusal must survive the fold onto the canonical record.

    Before the delegation this loop carried its own diagnostic naming the row,
    written deliberately: an unparseable stored date is a data defect the
    operator can fix once told where it is, and skipping the row instead would
    silently under-count the cap population and drop that child's spend.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=(
            UserProfileFact(path="renta_family.descendiente.0.birth_date", value="not-a-date"),
            UserProfileFact(path="renta_family.descendientes_count", value="1"),
        ),
        created_at=_T0,
        updated_at=_T0,
    )

    with pytest.raises(ProfileBindingResolutionError, match=re.escape("renta_family.descendiente.0.birth_date")):
        resolve_profile_sourced_bindings(_snapshot(), bucket_id=_BUCKET, profile_record=record)
