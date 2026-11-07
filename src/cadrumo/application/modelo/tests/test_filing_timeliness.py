"""A presentation date is judged against the effective close of the plazo voluntario.

A declaration's legal kind says nothing about when it was presented: an
``original`` declaration presented after its window closed is late, and that
lateness carries a Ley 58/2003 consequence whose regime depends on the
declaration -- the art. 27 recargo where it results in an amount payable, the
art. 198 regime where no economic harm arises. The timeliness axis is that
missing fact, and it is judged against the same effective close date the
calculate posture, the declaration editor and the filing calendar read, so no
surface can call a filing late that another calls in time.

The targets are scanned from the real published authority and holiday calendar
-- one window whose close moves to the next business day (Ley 39/2015 art. 30.5
through Ley 58/2003 art. 7.2), one whose close is already a business day --
rather than named here, because the supported years and each modelo's editions
are each declared once in the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ....core.period import Period
from ....core.time.clock import MADRID_TZ
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.irpf_income_categories import require_irpf_income_category
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.contribuyente.entity_type import require_entity_type
from ....domain.deadlines.effective_close import (
    EffectiveFilingDeadline,
    decide_filing_timeliness,
    resolve_effective_filing_deadline,
    resolve_filing_timeliness,
)
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.deadlines.tests.effective_close_scan import ScannedObligation, obligation_with_a_shifted_close
from ....domain.modelos.filing_record import FilingDeclarationKind

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

#: Period tokens walked to find one the scanned modelo authors no window for.
_PERIOD_TOKENS = ("1T", "2T", "3T", "4T", "0A")


@dataclass(frozen=True, slots=True)
class _Target:
    """One scanned filing axis and the close its filer actually has."""

    modelo: str
    filing_year: int
    period: Period
    nominal_closes_on: date
    effective_closes_on: date


def _scan_profile() -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": IVARegime("GENERAL"),
            "has_employees": True,
            "pays_rent_with_retencion": True,
        },
    )


def _target(scanned: ScannedObligation) -> _Target:
    return _Target(
        modelo=str(scanned.obligation.modelo),
        filing_year=scanned.obligation.period.filing_year,
        period=scanned.obligation.period,
        nominal_closes_on=scanned.nominal_closes_on,
        effective_closes_on=scanned.effective_closes_on,
    )


@pytest.fixture(name="shifted_target")
def _shifted_target(operation: PinnedAuthorityOperation) -> _Target:
    """A window whose close moves to the next business day."""
    return _target(obligation_with_a_shifted_close(_scan_profile(), operation=operation))


@pytest.fixture(name="unshifted_target")
def _unshifted_target(operation: PinnedAuthorityOperation) -> _Target:
    """A window whose published close is already the day the filer has."""
    engine = DeadlineEngine(authority=operation)
    envelope = published_supported_filing_years()
    assert envelope is not None
    for filing_year in envelope.years:
        schedule = engine.compute(_scan_profile(), filing_year, today=date(filing_year, 1, 1))
        for row in schedule.obligations:
            if (
                row.adjusted_closes_on == row.closes_on
                and row.holiday_coverage is not DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
            ):
                return _target(ScannedObligation(filing_year=filing_year, obligation=row))
    raise AssertionError("no supported filing year authors a window that closes on a business day")


@pytest.mark.parametrize(
    "fixture_name",
    ["shifted_target", "unshifted_target"],
    ids=["close-moved-to-the-next-business-day", "close-already-a-business-day"],
)
def test_the_effective_close_date_is_the_boundary_between_en_plazo_and_extemporanea(
    fixture_name: str,
    request: pytest.FixtureRequest,
    operation: PinnedAuthorityOperation,
) -> None:
    """The last day of the window is in time; the next day is late."""
    target = request.getfixturevalue(fixture_name)
    assert isinstance(target, _Target)
    deadline = resolve_effective_filing_deadline(target.modelo, target.filing_year, target.period, operation=operation)

    assert deadline is not None
    assert deadline.closes_on == target.effective_closes_on, "the shared projection owns the effective close date"

    for presented_on, expected in (
        (target.effective_closes_on - timedelta(days=1), FilingTimeliness.EN_PLAZO),
        (target.effective_closes_on, FilingTimeliness.EN_PLAZO),
        (target.effective_closes_on + timedelta(days=1), FilingTimeliness.EXTEMPORANEA),
    ):
        resolved = resolve_filing_timeliness(
            target.modelo,
            target.filing_year,
            target.period,
            presented_on=presented_on,
            operation=operation,
        )
        assert resolved is expected, f"presented on {presented_on}: {resolved} != {expected}"
        assert deadline.timeliness_on(presented_on) is expected


def test_a_filing_on_the_moved_day_is_en_plazo_rather_than_one_day_late(
    shifted_target: _Target,
    operation: PinnedAuthorityOperation,
) -> None:
    """Judging against the nominal non-business day calls a timely filing late."""
    deadline = resolve_effective_filing_deadline(
        shifted_target.modelo,
        shifted_target.filing_year,
        shifted_target.period,
        operation=operation,
    )

    assert deadline is not None
    assert deadline.nominal_closes_on < deadline.closes_on
    assert deadline.timeliness_on(deadline.nominal_closes_on + timedelta(days=1)) is FilingTimeliness.EN_PLAZO
    assert deadline.timeliness_on(shifted_target.effective_closes_on) is FilingTimeliness.EN_PLAZO


def test_the_presentation_date_is_the_spanish_civil_date_of_the_filing_instant(
    shifted_target: _Target,
    operation: PinnedAuthorityOperation,
) -> None:
    """A filing made late on the Spanish evening is judged on the Spanish day.

    Europe/Madrid leads UTC, so a filing stamped at 23:30 UTC on the last day of
    the window happened on the following Spanish civil day and is extemporánea.
    Reading the UTC date would call it in time (Ley 39/2015 art. 31, peninsular
    official time at the sede electrónica).
    """
    close = shifted_target.effective_closes_on
    just_before_madrid_midnight = datetime(close.year, close.month, close.day, 23, 30, tzinfo=UTC)

    assert just_before_madrid_midnight.date() == close, "the UTC date still reads as the closing day"
    assert just_before_madrid_midnight.astimezone(MADRID_TZ).date() > close
    assert (
        decide_filing_timeliness(
            modelo=shifted_target.modelo,
            filing_year=shifted_target.filing_year,
            period=shifted_target.period,
            filed_at=just_before_madrid_midnight,
            operation=operation,
        )
        is FilingTimeliness.EXTEMPORANEA
    )
    assert (
        decide_filing_timeliness(
            modelo=shifted_target.modelo,
            filing_year=shifted_target.filing_year,
            period=shifted_target.period,
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
    shifted_target: _Target,
    operation: PinnedAuthorityOperation,
) -> None:
    """Ley 58/2003 art. 122.1: presented after the plazo, these are extemporáneas."""
    for day, expected in (
        (shifted_target.effective_closes_on, FilingTimeliness.EN_PLAZO),
        (shifted_target.effective_closes_on + timedelta(days=1), FilingTimeliness.EXTEMPORANEA),
    ):
        decided = decide_filing_timeliness(
            modelo=shifted_target.modelo,
            filing_year=shifted_target.filing_year,
            period=shifted_target.period,
            filed_at=datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
            operation=operation,
            declaration_kind=declaration_kind,
        )
        assert decided is expected, f"{declaration_kind} on {day}: {decided} != {expected}"


def test_a_rectificativa_keeps_an_unknown_posture(
    shifted_target: _Target,
    operation: PinnedAuthorityOperation,
) -> None:
    """No bundled official text times the rectification procedure against the plazo.

    Art. 120.3 and the art. 120.4 added by Ley 13/2023 make it the vehicle of
    the rectification procedure, and art. 122.1's extemporaneidad rule names
    complementarias and sustitutivas only, so the posture is not inferred.
    """
    well_past_the_close = shifted_target.effective_closes_on + timedelta(days=400)

    assert (
        decide_filing_timeliness(
            modelo=shifted_target.modelo,
            filing_year=shifted_target.filing_year,
            period=shifted_target.period,
            filed_at=datetime(
                well_past_the_close.year,
                well_past_the_close.month,
                well_past_the_close.day,
                12,
                0,
                tzinfo=UTC,
            ),
            operation=operation,
            declaration_kind=FilingDeclarationKind.RECTIFICATIVA,
        )
        is FilingTimeliness.UNKNOWN
    )


def test_an_axis_the_registry_declares_no_window_for_is_unknown_not_timely(
    shifted_target: _Target,
    operation: PinnedAuthorityOperation,
) -> None:
    """An absent filing window says nothing about punctuality.

    The axis is the scanned target's own modelo and year with a period token
    the registry authors no window for, found by walking the quarterly and
    annual tokens. The resolver must not read that absence as a timely filing.
    """
    unauthored = next(
        period
        for period in (Period.from_year_and_code(shifted_target.filing_year, code) for code in _PERIOD_TOKENS)
        if resolve_effective_filing_deadline(
            shifted_target.modelo,
            shifted_target.filing_year,
            period,
            operation=operation,
        )
        is None
    )

    assert (
        resolve_filing_timeliness(
            shifted_target.modelo,
            shifted_target.filing_year,
            unauthored,
            presented_on=shifted_target.effective_closes_on,
            operation=operation,
        )
        is FilingTimeliness.UNKNOWN
    )


def test_an_unknown_close_is_unknown_timeliness_past_its_lower_bound(shifted_target: _Target) -> None:
    """A projected window whose close is unpublished cannot call a filing late.

    Its nominal date stays a lower bound: up to it the filer is in time, and
    nothing past it is judged, because an unknown close is not a closed window.
    The value is built in memory from a scanned close, so it addresses no
    registry edition of its own.
    """
    nominal = shifted_target.nominal_closes_on
    deadline = EffectiveFilingDeadline(
        nominal_closes_on=nominal,
        closes_on=nominal,
        holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
        shift_reason="calendar_unavailable",
    )

    assert deadline.timeliness_on(nominal - timedelta(days=1)) is FilingTimeliness.EN_PLAZO
    assert deadline.timeliness_on(nominal) is FilingTimeliness.EN_PLAZO
    assert deadline.timeliness_on(nominal + timedelta(days=1)) is FilingTimeliness.UNKNOWN
