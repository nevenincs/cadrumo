"""The tier c) rehabilitation window is counted in calendar years, not in days.

LIRPF art. 23.2.c, verbatim from the bundled consolidated corpus:

    c) En un 60 por ciento cuando, no cumpliendose los requisitos de las letras
    anteriores, la vivienda hubiera sido objeto de una actuacion de rehabilitacion
    [...] que hubiera finalizado EN LOS DOS ANOS ANTERIORES a la fecha de la
    celebracion del contrato de arrendamiento.

"Los dos anos anteriores" counts *de fecha a fecha*. The rule shipped as a 730-day
approximation, and two calendar years are 731 days whenever the span contains a 29 de
febrero -- so a rehabilitation finished exactly two calendar years before the contract
was one day outside the window and lost tier c) entirely, dropping the reduccion from
60 per cent to the 50 of letra d).

Direction: over-payment. The filer is refused a reduccion the article grants them, the
return is valid, and nothing warns. Every figure in the rule was correct; the unit was
not, which is why no review of the numbers would ever have found it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import Arrendamiento
from .._tier_resolver import (
    REHAB_LOOKBACK_YEARS,
    _qualifies_for_tier_60_rehab,
    _resolve_rehab_lookback_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _contract(*, celebrated: date, finished: date | None) -> Arrendamiento:
    """Only the two dates the tier c) predicate reads are meaningful here."""
    return Arrendamiento(
        finca_id=1,
        contract_celebration_date=celebrated,
        tenant_count=1,
        qualifying_co_tenant_count=0,
        initial_rent=Decimal("1000.00"),
        is_first_rental=False,
        rehabilitation_finished_date=finished,
        lau_17_6_compliant=True,
    )


def _qualifies(*, celebrated: date, finished: date | None) -> bool:
    return _qualifies_for_tier_60_rehab(
        _contract(celebrated=celebrated, finished=finished),
        rehab_lookback_years=REHAB_LOOKBACK_YEARS,
    )


@pytest.mark.parametrize(
    ("celebrated", "finished", "note"),
    [
        pytest.param(date(2024, 3, 1), date(2022, 3, 1), "span contains 29-Feb-2024", id="leap-span"),
        pytest.param(date(2023, 6, 1), date(2021, 6, 1), "no leap day in span", id="ordinary-span"),
        pytest.param(date(2028, 3, 1), date(2026, 3, 1), "span contains 29-Feb-2028", id="later-leap-span"),
    ],
)
def test_exactly_two_calendar_years_qualifies_whether_or_not_a_leap_day_intervenes(
    celebrated: date,
    finished: date,
    note: str,
) -> None:
    """THE DEFECT. These are the same statutory situation and must agree.

    Under the retired 730-day rule the leap spans were 731 days and were refused,
    so this parametrisation failed on exactly the leap ids and passed on the others.
    """
    assert _qualifies(celebrated=celebrated, finished=finished) is True, note


def test_the_day_before_the_window_opens_does_not_qualify() -> None:
    """The window is bounded; widening it would grant a reduccion the article does not."""
    assert _qualifies(celebrated=date(2024, 3, 1), finished=date(2022, 2, 28)) is False


def test_a_rehabilitation_finished_after_the_contract_does_not_qualify() -> None:
    """ "Anteriores" is directional: the window opens before the contract, not after."""
    assert _qualifies(celebrated=date(2024, 3, 1), finished=date(2024, 6, 1)) is False


def test_a_contract_celebrated_on_the_leap_day_clamps_its_boundary_outwards() -> None:
    """29 February has no counterpart two years earlier, so the boundary clamps to 28.

    Clamping widens a backwards window by a day rather than narrowing it, which is
    the only direction that cannot cost a filer a right they hold.
    """
    assert _qualifies(celebrated=date(2024, 2, 29), finished=date(2022, 2, 28)) is True


def test_no_rehabilitation_date_does_not_qualify() -> None:
    assert _qualifies(celebrated=date(2024, 3, 1), finished=None) is False


def test_the_registry_declares_the_window_in_years_for_every_shipped_revision() -> None:
    """Property, not tally: whatever revisions ship, each declares two calendar years.

    The retired parameter was declared in DAYS, which is what let a unit mismatch
    hide behind a correct-looking number.
    """
    declared = {year: _resolve_rehab_lookback_years(year) for year in (2020, 2021, 2022, 2023, 2024, 2025)}

    assert set(declared.values()) == {2}, declared
    assert REHAB_LOOKBACK_YEARS == 2


def test_no_registry_revision_still_declares_the_window_in_days() -> None:
    """ANTI-REGRESSION: a days-declared parameter is the shape that carried the defect."""
    from ....core.resources import bundled_path

    registry = bundled_path("registry")
    offenders = sorted(
        str(path.relative_to(registry))
        for path in registry.rglob("*.toml")
        if "rehab-lookback-days" in path.read_text(encoding="utf-8")
    )

    assert offenders == [], (
        "these revisions still declare the rehabilitation window in days: "
        f"{offenders}. The article counts it de fecha a fecha, and a day count is one "
        "day short across any leap span."
    )
