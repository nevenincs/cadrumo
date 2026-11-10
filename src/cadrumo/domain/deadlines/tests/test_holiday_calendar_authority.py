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

2027 comes from the Dirección General de Trabajo relación de fiestas laborales
(BOE-A-2026-21254), whose anexo marks each date by territory. The dates used:

* 2027-01-01 (Friday), 2027-03-26 (Viernes Santo, Friday), 2027-05-01 and
  2027-12-25 (Saturdays): festive in all nineteen territories, so inhábil nationally.
* 2027-03-25, Jueves Santo: festive in seventeen territories, not in Cataluña or the
  Comunitat Valenciana.
* 2027-03-29, Lunes de Pascua: festive in Illes Balears, Cataluña, Navarra, País
  Vasco, La Rioja and the Comunitat Valenciana; note 2 replaces it in Arán, so it is
  not a day off throughout Cataluña.
* 2027-08-16: Lunes siguiente a la Asunción in Andalucía, Aragón, Asturias,
  Canarias, Castilla y León and Madrid.
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
_BOE_A_2023_23637_EXERCISE = legal_effective_to("resolucion-sefp-2023-11-16-dias-inhabiles-2024:anexo").year
_BOE_A_2024_26935_EXERCISE = legal_effective_to("resolucion-sefp-2024-12-16-dias-inhabiles-2025:anexo").year
_BOE_A_2025_23702_EXERCISE = legal_effective_to("resolucion-sefp-2025-11-18-dias-inhabiles-2026:anexo").year
_BOE_A_2026_21254_EXERCISE = legal_effective_to("resolucion-dgt-2026-10-08-fiestas-laborales-2027:anexo").year

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


def _territory(operation: PinnedAuthorityOperation, code: str, year: int = _BOE_A_2024_26935_EXERCISE) -> CalendarCCAA:
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


@pytest.mark.parametrize(
    "year",
    [_BOE_A_2023_23637_EXERCISE, _BOE_A_2024_26935_EXERCISE, _BOE_A_2025_23702_EXERCISE, _BOE_A_2026_21254_EXERCISE],
)
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
        calendar = load_holiday_calendar(_BOE_A_2024_26935_EXERCISE, operation=operation)
        catalonia = _regional_dates(calendar, _territory(operation, "ES-CT"))

    year = _BOE_A_2024_26935_EXERCISE
    assert date(year, 12, 26) not in catalonia
    # The rest of the Catalan list is still present, so the absence is specific.
    assert {date(year, 4, 21), date(year, 6, 24), date(year, 9, 11)} <= catalonia


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


def _national_dates(calendar: HolidayCalendar) -> set[date]:
    return {holiday.holiday_date for holiday in calendar.national}


def test_the_fiestas_laborales_national_days_are_those_festive_in_every_territory() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(_BOE_A_2026_21254_EXERCISE, operation=operation)

    assert calendar.boe_url == "https://www.boe.es/buscar/doc.php?id=BOE-A-2026-21254"
    assert _national_dates(calendar) == {
        date(_BOE_A_2026_21254_EXERCISE, 1, 1),
        date(_BOE_A_2026_21254_EXERCISE, 1, 6),
        date(_BOE_A_2026_21254_EXERCISE, 3, 26),
        date(_BOE_A_2026_21254_EXERCISE, 5, 1),
        date(_BOE_A_2026_21254_EXERCISE, 10, 12),
        date(_BOE_A_2026_21254_EXERCISE, 11, 1),
        date(_BOE_A_2026_21254_EXERCISE, 12, 6),
        date(_BOE_A_2026_21254_EXERCISE, 12, 8),
        date(_BOE_A_2026_21254_EXERCISE, 12, 25),
    }


@pytest.mark.parametrize(
    ("close", "expected"),
    [
        # Friday 1 January: Saturday 2 and Sunday 3 are weekend, Monday 4 is ordinary.
        (date(_BOE_A_2026_21254_EXERCISE, 1, 1), date(_BOE_A_2026_21254_EXERCISE, 1, 4)),
        # Wednesday 6 January, Epifanía, moves to Thursday.
        (date(_BOE_A_2026_21254_EXERCISE, 1, 6), date(_BOE_A_2026_21254_EXERCISE, 1, 7)),
        # Saturday 30 January moves to Monday 1 February.
        (date(_BOE_A_2026_21254_EXERCISE, 1, 30), date(_BOE_A_2026_21254_EXERCISE, 2, 1)),
        # Viernes Santo moves to Monday 29 March, a regional-only day that never moves a close.
        (date(_BOE_A_2026_21254_EXERCISE, 3, 26), date(_BOE_A_2026_21254_EXERCISE, 3, 29)),
        # Jueves Santo is regional, so the close stays.
        (date(_BOE_A_2026_21254_EXERCISE, 3, 25), date(_BOE_A_2026_21254_EXERCISE, 3, 25)),
        # Monday 1 November moves to Tuesday 2 November.
        (date(_BOE_A_2026_21254_EXERCISE, 11, 1), date(_BOE_A_2026_21254_EXERCISE, 11, 2)),
        # Saturday 25 December moves to Monday 27 December.
        (date(_BOE_A_2026_21254_EXERCISE, 12, 25), date(_BOE_A_2026_21254_EXERCISE, 12, 27)),
    ],
)
def test_a_fiestas_laborales_filing_close_moves_only_for_weekends_and_national_days(
    close: date, expected: date
) -> None:
    with bundled_indexed_authority().operation() as operation:
        shift = shift_deadline(close, modelo="303", operation=operation)

    assert shift.adjusted_close_date == expected
    assert shift.coverage is DeadlineHolidayCoverage.NATIONAL_ONLY


def test_fiestas_laborales_regional_days_follow_the_annex_columns() -> None:
    with bundled_indexed_authority().operation() as operation:
        calendar = load_holiday_calendar(_BOE_A_2026_21254_EXERCISE, operation=operation)
        madrid = _regional_dates(calendar, _territory(operation, "ES-MD", _BOE_A_2026_21254_EXERCISE))
        catalonia = _regional_dates(calendar, _territory(operation, "ES-CT", _BOE_A_2026_21254_EXERCISE))
        valencia = _regional_dates(calendar, _territory(operation, "ES-VC", _BOE_A_2026_21254_EXERCISE))
        basque = _regional_dates(calendar, _territory(operation, "ES-PV", _BOE_A_2026_21254_EXERCISE))

    assert madrid == {
        date(_BOE_A_2026_21254_EXERCISE, 3, 19),
        date(_BOE_A_2026_21254_EXERCISE, 3, 25),
        date(_BOE_A_2026_21254_EXERCISE, 8, 16),
    }
    # Arán replaces Easter Monday, and the Catalan Saturday 11 September is a weekend day.
    assert catalonia == {date(_BOE_A_2026_21254_EXERCISE, 6, 24)}
    assert valencia == {date(_BOE_A_2026_21254_EXERCISE, 3, 19), date(_BOE_A_2026_21254_EXERCISE, 3, 29)}
    assert basque == {
        date(_BOE_A_2026_21254_EXERCISE, 3, 25),
        date(_BOE_A_2026_21254_EXERCISE, 3, 29),
        date(_BOE_A_2026_21254_EXERCISE, 10, 7),
    }
