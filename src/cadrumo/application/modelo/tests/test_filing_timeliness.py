"""A presentation date is judged against the effective close of the plazo voluntario.

A declaration's legal kind says nothing about when it was presented: an
``original`` Modelo 130 filed in 2026 for 1T of 2024 is late, and lateness
carries the Ley 58/2003 art. 27 recargo consequence. The timeliness axis is
that missing fact, and it is judged against the same effective close date the
calculate posture, the declaration editor and the filing calendar read, so no
surface can call a filing late that another calls in time.

Each case reads the real published authority and holiday calendar:

* Modelo 136 1T 2025 closes nominally on Sunday 20 April 2025, so the filer has
  until Monday 21 April (Ley 39/2015 art. 30.5 through Ley 58/2003 art. 7.2).
  A presentation on that Monday is still en plazo; the Tuesday is extemporánea.
* Modelo 303 4T 2026 closes on Monday 1 February 2027, a business day, so the
  boundary is the declared date itself.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.effective_close import (
    EffectiveFilingDeadline,
    decide_filing_timeliness,
    resolve_effective_filing_deadline,
    resolve_filing_timeliness,
)
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.modelos.filing_record import FilingDeclarationKind

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_SHIFTED_CLOSE = ("136", 2025, "1T", date(2025, 4, 21))
_BUSINESS_DAY_CLOSE = ("303", 2026, "4T", date(2027, 2, 1))


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period_code", "effective_close"),
    [_SHIFTED_CLOSE, _BUSINESS_DAY_CLOSE],
    ids=["close-shifted-off-a-sunday", "close-on-a-business-day"],
)
def test_the_effective_close_date_is_the_boundary_between_en_plazo_and_extemporanea(
    modelo: str,
    filing_year: int,
    period_code: str,
    effective_close: date,
    operation: PinnedAuthorityOperation,
) -> None:
    """The last day of the window is in time; the next day is late."""
    period = Period.from_year_and_code(filing_year, period_code)
    deadline = resolve_effective_filing_deadline(modelo, filing_year, period, operation=operation)

    assert deadline is not None
    assert deadline.closes_on == effective_close, "the shared projection still owns the effective close date"

    for presented_on, expected in (
        (effective_close - timedelta(days=1), FilingTimeliness.EN_PLAZO),
        (effective_close, FilingTimeliness.EN_PLAZO),
        (effective_close + timedelta(days=1), FilingTimeliness.EXTEMPORANEA),
    ):
        resolved = resolve_filing_timeliness(
            modelo,
            filing_year,
            period,
            presented_on=presented_on,
            operation=operation,
        )
        assert resolved is expected, f"presented on {presented_on}: {resolved} != {expected}"
        assert deadline.timeliness_on(presented_on) is expected


def test_a_filing_on_the_moved_day_is_en_plazo_rather_than_one_day_late(
    operation: PinnedAuthorityOperation,
) -> None:
    """Judging against the nominal Sunday would report a timely Monday as extemporánea."""
    modelo, filing_year, period_code, effective_close = _SHIFTED_CLOSE
    period = Period.from_year_and_code(filing_year, period_code)
    deadline = resolve_effective_filing_deadline(modelo, filing_year, period, operation=operation)

    assert deadline is not None
    assert deadline.nominal_closes_on < deadline.closes_on
    assert deadline.timeliness_on(deadline.nominal_closes_on + timedelta(days=1)) is FilingTimeliness.EN_PLAZO
    assert deadline.timeliness_on(effective_close) is FilingTimeliness.EN_PLAZO


def test_the_presentation_date_is_the_spanish_civil_date_of_the_filing_instant(
    operation: PinnedAuthorityOperation,
) -> None:
    """A filing made late on the Spanish evening is judged on the Spanish day.

    Europe/Madrid leads UTC by two hours in April, so a filing stamped at
    22:30 UTC on the last day of the window happened on the following Spanish
    civil day and is extemporánea. Reading the UTC date would call it in time
    (Ley 39/2015 art. 31, peninsular official time at the sede electrónica).
    """
    modelo, filing_year, period_code, effective_close = _SHIFTED_CLOSE
    period = Period.from_year_and_code(filing_year, period_code)
    just_before_madrid_midnight = datetime(
        effective_close.year, effective_close.month, effective_close.day, 22, 30, tzinfo=UTC
    )

    assert just_before_madrid_midnight.date() == effective_close, "the UTC date still reads as the closing day"
    assert (
        decide_filing_timeliness(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            filed_at=just_before_madrid_midnight,
            operation=operation,
        )
        is FilingTimeliness.EXTEMPORANEA
    )
    assert (
        decide_filing_timeliness(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            filed_at=just_before_madrid_midnight - timedelta(hours=12),
            operation=operation,
        )
        is FilingTimeliness.EN_PLAZO
    )


@pytest.mark.parametrize(
    "declaration_kind",
    [FilingDeclarationKind.ORIGINAL, FilingDeclarationKind.COMPLEMENTARIA, FilingDeclarationKind.SUSTITUTIVA],
    ids=["original", "complementaria", "sustitutiva"],
)
def test_a_plazo_timed_declaration_is_judged_against_the_periods_own_window(
    declaration_kind: FilingDeclarationKind,
    operation: PinnedAuthorityOperation,
) -> None:
    """Ley 58/2003 art. 122.1: presented after the plazo, these are extemporáneas."""
    modelo, filing_year, period_code, effective_close = _SHIFTED_CLOSE
    period = Period.from_year_and_code(filing_year, period_code)

    for day, expected in (
        (effective_close, FilingTimeliness.EN_PLAZO),
        (effective_close + timedelta(days=1), FilingTimeliness.EXTEMPORANEA),
    ):
        decided = decide_filing_timeliness(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            filed_at=datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
            operation=operation,
            declaration_kind=declaration_kind,
        )
        assert decided is expected, f"{declaration_kind} on {day}: {decided} != {expected}"


def test_a_rectificativa_keeps_an_unknown_posture(operation: PinnedAuthorityOperation) -> None:
    """No bundled official text times the rectification procedure against the plazo.

    Art. 120.3 and the art. 120.4 added by Ley 13/2023 make it the vehicle of
    the rectification procedure, and art. 122.1's extemporaneidad rule names
    complementarias and sustitutivas only, so the posture is not inferred.
    """
    modelo, filing_year, period_code, effective_close = _SHIFTED_CLOSE
    period = Period.from_year_and_code(filing_year, period_code)
    well_past_the_close = effective_close + timedelta(days=400)

    assert (
        decide_filing_timeliness(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            filed_at=datetime(
                well_past_the_close.year, well_past_the_close.month, well_past_the_close.day, 12, 0, tzinfo=UTC
            ),
            operation=operation,
            declaration_kind=FilingDeclarationKind.RECTIFICATIVA,
        )
        is FilingTimeliness.UNKNOWN
    )


def test_an_axis_the_registry_declares_no_window_for_is_unknown_not_timely(
    operation: PinnedAuthorityOperation,
) -> None:
    """An absent filing window says nothing about punctuality.

    Modelo 100 is annual, so no window matches a quarterly period token. The
    resolver must not read that absence as a filing made in time.
    """
    period = Period.from_year_and_code(2024, "1T")

    assert resolve_effective_filing_deadline("100", 2024, period, operation=operation) is None
    assert (
        resolve_filing_timeliness("100", 2024, period, presented_on=date(2026, 6, 30), operation=operation)
        is FilingTimeliness.UNKNOWN
    )


def test_an_unknown_close_is_unknown_timeliness_past_its_lower_bound() -> None:
    """A projected window whose close is unpublished cannot call a filing late.

    Its nominal date stays a lower bound: up to it the filer is in time, and
    nothing past it is judged, because an unknown close is not a closed window.
    """
    nominal = date(2031, 1, 30)
    deadline = EffectiveFilingDeadline(
        nominal_closes_on=nominal,
        closes_on=nominal,
        holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
        shift_reason="calendar_unavailable",
        close_known=False,
    )

    assert deadline.timeliness_on(nominal - timedelta(days=1)) is FilingTimeliness.EN_PLAZO
    assert deadline.timeliness_on(nominal) is FilingTimeliness.EN_PLAZO
    assert deadline.timeliness_on(nominal + timedelta(days=1)) is FilingTimeliness.UNKNOWN
