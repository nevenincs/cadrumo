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
from cadrumo.domain.calculations.registry.calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue
from cadrumo.domain.calculations.registry.tests.legal_text import legal_effective_to

from ..festivos import (
    CalendarCCAA,
    DeadlineHolidayCoverage,
    HolidayCalendar,
    load_holiday_calendar,
    shift_deadline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Each días inhábiles resolution fixes the calendar of the year its in-force window
# closes on; the dates asserted against it are transcribed from its ANEXO.
_BOE_A_2024_26935_EXERCISE = legal_effective_to("resolucion-sefp-2024-12-16-dias-inhabiles-2025:anexo").year
_BOE_A_2025_23702_EXERCISE = legal_effective_to("resolucion-sefp-2025-11-18-dias-inhabiles-2026:anexo").year

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
    return resolve_calendar_ccaa_catalogue(effective_date=date(year, 7, 1), authority=operation).require(code)


def _regional_dates(calendar: HolidayCalendar, territory: CalendarCCAA) -> set[date]:
    return {holiday.holiday_date for holiday in calendar.ccaa if holiday.ccaa_code == territory}


def test_a_calendar_resolves_from_its_own_publication() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(_BOE_A_2025_23702_EXERCISE, operation=operation)

    assert calendar.year == _BOE_A_2025_23702_EXERCISE
    assert calendar.boe_url is not None
    assert "BOE-A-2025-23702" in calendar.boe_url
    # Viernes Santo 2026 is inhábil in todo el territorio nacional.
    assert date(_BOE_A_2025_23702_EXERCISE, 4, 3) in {holiday.holiday_date for holiday in calendar.national}


@pytest.mark.parametrize("year", [2024, 2025, 2026])
def test_every_calendar_territory_is_verified(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(year, operation=operation)
        expected = {_territory(operation, code, year) for code in _CALENDAR_TERRITORIES}

    assert set(calendar.verified_territories) == expected
    assert len(calendar.verified_territories) == len(_CALENDAR_TERRITORIES)


def test_madrid_holds_jueves_santo_and_not_the_municipal_almudena() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(_BOE_A_2024_26935_EXERCISE, operation=operation)
        madrid = _regional_dates(calendar, _territory(operation, "ES-MD", _BOE_A_2024_26935_EXERCISE))
        valencia = _regional_dates(calendar, _territory(operation, "ES-VC", _BOE_A_2024_26935_EXERCISE))
        catalonia = _regional_dates(calendar, _territory(operation, "ES-CT", _BOE_A_2024_26935_EXERCISE))

    assert date(_BOE_A_2024_26935_EXERCISE, 4, 17) in madrid
    assert date(_BOE_A_2024_26935_EXERCISE, 11, 10) not in madrid
    assert date(_BOE_A_2024_26935_EXERCISE, 4, 17) not in valencia
    assert date(_BOE_A_2024_26935_EXERCISE, 4, 17) not in catalonia


def test_san_esteban_is_not_a_catalan_regional_day_because_aran_replaces_it() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(2025, operation=operation)
        catalonia = _regional_dates(calendar, _territory(operation, "ES-CT"))

    assert date(2025, 12, 26) not in catalonia
    # The rest of the Catalan list is still present, so the absence is specific.
    assert {date(2025, 4, 21), date(2025, 6, 24), date(2025, 9, 11)} <= catalonia


def test_a_regional_inhabil_never_moves_a_filing_close_while_a_national_one_does() -> None:
    year = _BOE_A_2024_26935_EXERCISE
    jueves_santo = date(year, 4, 17)
    viernes_santo = date(year, 4, 18)
    lunes_de_pascua = date(year, 4, 21)
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(year, operation=operation)
        madrid = _territory(operation, "ES-MD", year)
        catalonia = _territory(operation, "ES-CT", year)
        regional_close = shift_deadline(jueves_santo, modelo="303", operation=operation)
        national_close = shift_deadline(viernes_santo, modelo="303", operation=operation)

    assert {madrid, catalonia} <= set(calendar.verified_territories)
    assert jueves_santo in _regional_dates(calendar, madrid)
    assert lunes_de_pascua in _regional_dates(calendar, catalonia)
    assert {jueves_santo, lunes_de_pascua}.isdisjoint(holiday.holiday_date for holiday in calendar.national)
    assert viernes_santo in {holiday.holiday_date for holiday in calendar.national}

    assert regional_close.shifted is False
    assert regional_close.adjusted_close_date == jueves_santo
    assert regional_close.coverage is DeadlineHolidayCoverage.NATIONAL_ONLY

    assert national_close.shifted is True
    assert national_close.adjusted_close_date == lunes_de_pascua
    assert national_close.coverage is DeadlineHolidayCoverage.NATIONAL_ONLY


def test_the_calendar_publication_cites_the_dias_inhabiles_resolution() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(_BOE_A_2024_26935_EXERCISE, operation=operation)

    assert calendar.boe_url == "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-26935"
