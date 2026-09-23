"""Published holiday calendars against the BOE días inhábiles resolutions.

Expected values come from the ANEXO of the Secretaría de Estado de Función
Pública resolution fixing the días inhábiles of the Administración General del
Estado for each year: BOE-A-2023-23637 (2024), BOE-A-2024-26935 (2025) and
BOE-A-2025-23702 (2026). The fixed dates used here:

* 2025-04-17, Jueves Santo: inhábil in the Comunidad de Madrid and fifteen other
  territories, but not in Cataluña or the Comunitat Valenciana.
* 2025-04-18, Viernes Santo: inhábil in todo el territorio nacional.
* 2025-04-21, Lunes de Pascua: inhábil in Cataluña, not in Madrid.
* 2025-11-10: not listed for Madrid; it is a municipal holiday of the city.
* 2025-12-26, San Esteban: listed for Cataluña, but replaced by 17 June in Arán,
  so it is not a day off throughout the territory.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.calendar_ccaa_catalogue import require_calendar_ccaa

from ..festivos import (
    CalendarCCAA,
    DeadlineHolidayCoverage,
    HolidayCalendar,
    load_holiday_calendar,
    shift_deadline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CALENDAR_TERRITORIES = (
    "ES-AN",
    "ES-AR",
    "ES-AS",
    "ES-IB",
    "ES-CN",
    "ES-CB",
    "ES-CM",
    "ES-CL",
    "ES-CT",
    "ES-EX",
    "ES-GA",
    "ES-RI",
    "ES-MD",
    "ES-MC",
    "ES-NC",
    "ES-PV",
    "ES-VC",
    "ES-CE",
    "ES-ML",
)


def _territory(operation: PinnedAuthorityOperation, code: str, year: int = 2025) -> CalendarCCAA:
    return require_calendar_ccaa(code, effective_date=date(year, 7, 1), authority=operation)


def _regional_dates(calendar: HolidayCalendar, territory: CalendarCCAA) -> set[date]:
    return {holiday.holiday_date for holiday in calendar.ccaa if holiday.ccaa_code == territory}


def test_the_2026_calendar_resolves_from_its_own_publication() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2026, operation=operation)

    assert calendar.year == 2026
    assert calendar.boe_url is not None
    assert "BOE-A-2025-23702" in calendar.boe_url
    # Viernes Santo 2026 is inhábil in todo el territorio nacional.
    assert date(2026, 4, 3) in {holiday.holiday_date for holiday in calendar.national}


@pytest.mark.parametrize("year", [2024, 2025, 2026])
def test_every_calendar_territory_is_verified(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(year, operation=operation)
        expected = {_territory(operation, code, year) for code in _CALENDAR_TERRITORIES}

    assert set(calendar.verified_territories) == expected
    assert len(calendar.verified_territories) == len(_CALENDAR_TERRITORIES)


def test_madrid_2025_holds_jueves_santo_and_not_the_municipal_almudena() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        madrid = _regional_dates(calendar, _territory(operation, "ES-MD"))
        valencia = _regional_dates(calendar, _territory(operation, "ES-VC"))
        catalonia = _regional_dates(calendar, _territory(operation, "ES-CT"))

    assert date(2025, 4, 17) in madrid
    assert date(2025, 11, 10) not in madrid
    assert date(2025, 4, 17) not in valencia
    assert date(2025, 4, 17) not in catalonia


def test_san_esteban_is_not_a_catalan_regional_day_because_aran_replaces_it() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        catalonia = _regional_dates(calendar, _territory(operation, "ES-CT"))

    assert date(2025, 12, 26) not in catalonia
    # The rest of the Catalan list is still present, so the absence is specific.
    assert {date(2025, 4, 21), date(2025, 6, 24), date(2025, 9, 11)} <= catalonia


def test_jueves_santo_moves_a_madrid_deadline_past_easter_but_not_a_catalan_one() -> None:
    close_date = date(2025, 4, 17)
    with bundled_indexed_authority().operation() as operation:
        madrid = shift_deadline(
            close_date,
            modelo="303",
            ccaa_code=_territory(operation, "ES-MD"),
            operation=operation,
        )
        catalonia = shift_deadline(
            close_date,
            modelo="303",
            ccaa_code=_territory(operation, "ES-CT"),
            operation=operation,
        )

    # 18 April is Viernes Santo and 19-20 April are the weekend.
    assert madrid.shifted is True
    assert madrid.adjusted_close_date == date(2025, 4, 21)
    assert madrid.coverage is DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY

    assert catalonia.shifted is False
    assert catalonia.adjusted_close_date == close_date
    assert catalonia.coverage is DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY


def test_the_2025_publication_cites_the_dias_inhabiles_resolution() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)

    assert calendar.boe_url == "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-26935"
