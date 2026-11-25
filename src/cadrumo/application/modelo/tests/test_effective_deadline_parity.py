"""The calculate posture, the declaration editor and the filing calendar judge a deadline alike.

Deadline windows store the nominal statutory close date. When that day is not
a business day the deadline runs to the next business day: Ley 39/2015 art.
30.5 ("Cuando el último día del plazo sea inhábil, se entenderá prorrogado al
primer día hábil siguiente"), applied to tax procedure by Ley 58/2003 art. 7.2.
On time therefore means on or before the effective date, and every surface
that says on time or late must say it against that date.

Each case reads the real published authority and holiday calendar through the
three application projections the frontends render -- the calculate command's
work-unit posture, the editor's form deadline and the overview calendar row --
and requires the same nominal date, effective date, holiday coverage and day
count from all three:

* Modelo 136 1T 2025 closes nominally on Sunday 20 April 2025.
* Modelo 185 period 09 of 2026 closes nominally on Saturday 10 October 2026;
  Monday the 12th is the Fiesta Nacional, so the filer has until Tuesday.
* Modelo 303 4T 2026 closes on Monday 1 February 2027 and 2027 is a published
  calendar year, so the date stands and is reported as nationally verified.
* A Modelo 303 window of 2028, whose holiday calendar is not published, keeps
  its nominal date and is reported as unverified.

An electronic filing counts days on the State's calendar of días inhábiles
(Ley 39/2015 art. 31.3), so a regional inhábil never moves a close. The
2025 calendar (BOE-A-2024-26935) lists Jueves Santo, 17 April, as inhábil in
Madrid and other communities but not nationally; Viernes Santo, 18 April, as
inhábil nationally; and Lunes de Pascua, 21 April, as inhábil only in Cataluña.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.legal_text import legal_effective_to
from ....domain.calculations.registry.tests.published_authority import published_selected_revision_id
from ....domain.deadlines.effective_close import effective_filing_deadline, resolve_effective_filing_deadline
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.plazo import resolve_filing_window
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...overview.calendar import build_overview_calendar
from ...overview.calendar_models import OverviewCalendarRange
from ...overview.tests.calendar_test_support import profile
from ..work_form_service import modelo_form_deadline
from ..work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "d" * 64


class _Case(NamedTuple):
    modelo: str
    filing_year: int
    period_code: str
    nominal: date
    effective: date
    coverage: DeadlineHolidayCoverage


# Each case sits in the exercise whose published calendar of días inhábiles it
# is about, so the exercise is read from that publication's in-force window.
_CALENDAR_OF_SUNDAY_CLOSE = legal_effective_to("resolucion-sefp-2024-12-16-dias-inhabiles-2025:anexo").year
_CALENDAR_OF_FIESTA_NACIONAL_MONDAY = legal_effective_to("resolucion-sefp-2025-11-18-dias-inhabiles-2026:anexo").year
_CALENDAR_OF_NEXT_EXERCISE = legal_effective_to("resolucion-dgt-2026-10-08-fiestas-laborales-2027:anexo").year

_WEEKEND = _Case(
    "136",
    _CALENDAR_OF_SUNDAY_CLOSE,
    "1T",
    date(_CALENDAR_OF_SUNDAY_CLOSE, 4, 20),
    date(_CALENDAR_OF_SUNDAY_CLOSE, 4, 21),
    DeadlineHolidayCoverage.NATIONAL_ONLY,
)
_NATIONAL_HOLIDAY = _Case(
    "185",
    _CALENDAR_OF_FIESTA_NACIONAL_MONDAY,
    "09",
    date(_CALENDAR_OF_FIESTA_NACIONAL_MONDAY, 10, 10),
    date(_CALENDAR_OF_FIESTA_NACIONAL_MONDAY, 10, 13),
    DeadlineHolidayCoverage.NATIONAL_ONLY,
)
_PUBLISHED_NEXT_EXERCISE = _Case(
    "303",
    _CALENDAR_OF_NEXT_EXERCISE - 1,
    "4T",
    date(_CALENDAR_OF_NEXT_EXERCISE, 2, 1),
    date(_CALENDAR_OF_NEXT_EXERCISE, 2, 1),
    DeadlineHolidayCoverage.NATIONAL_ONLY,
)
_CASES = (_WEEKEND, _NATIONAL_HOLIDAY, _PUBLISHED_NEXT_EXERCISE)
_UNCOVERED_YEAR = _CALENDAR_OF_NEXT_EXERCISE + 1


class _Posture(NamedTuple):
    nominal: date
    effective: date
    coverage: DeadlineHolidayCoverage
    days_remaining: int | None
    days_overdue: int | None


def _work_unit(case: _Case) -> WorkUnit:
    period = Period.from_year_and_code(case.filing_year, case.period_code)
    revision_id = published_selected_revision_id(
        case.modelo, filing_year=case.filing_year, period=period.registry_token
    )
    created = datetime(case.filing_year, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=case.modelo,
            filing_year=case.filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(case.modelo),
        filing_year=case.filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{case.modelo}-{case.filing_year}-{case.period_code}",
        created_at=created,
        updated_at=created,
    )


def _calculate_posture(case: _Case, reference_on: date, operation: PinnedAuthorityOperation) -> _Posture:
    posture = modelo_work_deadline_posture(_work_unit(case), reference_on=reference_on, operation=operation)
    assert posture is not None
    return _Posture(
        posture.nominal_closes_on,
        posture.closes_on,
        posture.holiday_coverage,
        posture.days_remaining,
        posture.days_overdue,
    )


def _editor_posture(case: _Case, reference_on: date, operation: PinnedAuthorityOperation) -> _Posture:
    deadline = modelo_form_deadline(
        operation,
        ModeloCode(case.modelo),
        Period.from_year_and_code(case.filing_year, case.period_code),
        reference_on=reference_on,
    )
    assert deadline is not None
    return _Posture(
        deadline.nominal_closes_on,
        deadline.closes_on,
        deadline.holiday_coverage,
        deadline.days_remaining,
        deadline.days_overdue,
    )


def _calendar_posture(case: _Case, reference_on: date, operation: PinnedAuthorityOperation) -> _Posture:
    taxpayer = profile()
    calendar = build_overview_calendar(
        taxpayer,
        OverviewCalendarRange(from_date=date(case.filing_year, 1, 1), to_date=case.effective + timedelta(days=31)),
        operation=operation,
        today=reference_on,
        engine=DeadlineEngine(authority=operation),
        work_units=(_work_unit(case),),
    )
    period = Period.from_year_and_code(case.filing_year, case.period_code)
    rows = [entry for entry in calendar.entries if entry.modelo == case.modelo and entry.period == period]
    assert len(rows) == 1, f"the calendar lists Modelo {case.modelo} {period} once"
    row = rows[0]
    remaining = (row.adjusted_closes_on - reference_on).days if reference_on <= row.adjusted_closes_on else None
    return _Posture(row.closes_on, row.adjusted_closes_on, row.holiday_coverage, remaining, row.days_overdue)


@pytest.mark.parametrize("case", _CASES, ids=["weekend", "national-holiday", "published-next-exercise"])
def test_every_surface_reads_the_same_nominal_and_effective_deadline(
    case: _Case, operation: PinnedAuthorityOperation
) -> None:
    window = resolve_filing_window(
        case.modelo,
        case.filing_year,
        Period.from_year_and_code(case.filing_year, case.period_code),
        authority=operation,
    )
    assert window is not None
    assert window.closes_on == case.nominal, "the registry window still declares the nominal date"

    for reference_on, expected_remaining, expected_overdue in (
        (case.effective, 0, None),
        (case.effective + timedelta(days=1), None, 1),
    ):
        expected = _Posture(case.nominal, case.effective, case.coverage, expected_remaining, expected_overdue)
        surfaces = {
            "calculate": _calculate_posture(case, reference_on, operation),
            "editor": _editor_posture(case, reference_on, operation),
            "calendar": _calendar_posture(case, reference_on, operation),
        }
        for surface, posture in surfaces.items():
            assert posture == expected, f"{surface} on {reference_on}: {posture} != {expected}"


def test_a_deadline_moved_off_a_non_business_day_is_still_on_time_on_the_moved_day(
    operation: PinnedAuthorityOperation,
) -> None:
    """Filing on the Monday after a Sunday deadline is on time, not one day late.

    Before the shared projection the calculate posture counted from the
    nominal Sunday and called this filing overdue while the editor and the
    calendar called it on time.
    """
    posture = modelo_work_deadline_posture(_work_unit(_WEEKEND), reference_on=_WEEKEND.effective, operation=operation)

    assert posture is not None
    assert posture.days_overdue is None
    assert posture.days_remaining == 0
    assert posture.conditional_recargo_preview is None
    assert posture.nominal_closes_on < posture.closes_on


def test_an_uncovered_year_is_reported_as_unverified_not_silently_nominal(
    operation: PinnedAuthorityOperation,
) -> None:
    deadline = resolve_effective_filing_deadline(
        "303", _UNCOVERED_YEAR, Period.from_year_and_code(_UNCOVERED_YEAR, "1T"), operation=operation
    )

    assert deadline is not None
    assert deadline.closes_on == deadline.nominal_closes_on == date(_UNCOVERED_YEAR, 4, 20)
    assert deadline.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert deadline.shift_reason == "calendar_unavailable"


def test_a_regional_inhabil_keeps_the_close_while_a_national_one_moves_it(
    operation: PinnedAuthorityOperation,
) -> None:
    year = legal_effective_to("resolucion-sefp-2024-12-16-dias-inhabiles-2025:anexo").year
    jueves_santo = date(year, 4, 17)
    viernes_santo = date(year, 4, 18)
    lunes_de_pascua = date(year, 4, 21)

    regional = effective_filing_deadline(jueves_santo, modelo="303", operation=operation)
    national = effective_filing_deadline(viernes_santo, modelo="303", operation=operation)

    assert regional.closes_on == jueves_santo
    assert regional.shift_reason == "business_day"
    assert regional.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
    assert national.closes_on == lunes_de_pascua
    assert national.holiday_refs == ("Viernes Santo",)
    assert national.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
