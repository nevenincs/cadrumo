"""Find a filing target whose effective close differs from its published close.

A test about the business-day shift needs a window that actually shifts, and a
test about an unverifiable shift needs a year whose holiday calendar is not
bundled. Naming either by year or by edition freezes a registry fact into the
test: the supported years come from the year policy alone, and the editions
come from each modelo's own revisions, so a literal here is a second
declaration of both.

These helpers scan instead. They walk the supported filing years from the
published envelope, compute the real schedule for a supplied profile, and
return the first obligation whose published and effective closes differ -- or
whose shift calendar could not be resolved. The first year whose calendar the
authority does not publish is found the same way. A scan that finds nothing raises,
so a test never silently passes against an envelope that no longer contains the
case it is about.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import count
from typing import TYPE_CHECKING

from ...calculations.registry.tests.published_authority import published_supported_filing_years
from ..engine import DeadlineEngine
from ..errors import DeadlineValidationError
from ..festivos import DeadlineHolidayCoverage, holiday_calendar_from_authority

if TYPE_CHECKING:
    from ...calculations.registry.authority import PinnedAuthorityOperation
    from ..models import ModeloDeadline, TaxpayerProfile


@dataclass(frozen=True, slots=True)
class ScannedObligation:
    """One scanned obligation and the filing year its schedule was computed for."""

    filing_year: int
    obligation: ModeloDeadline

    @property
    def nominal_closes_on(self) -> date:
        """The close the registry publishes for this window."""
        return self.obligation.closes_on

    @property
    def effective_closes_on(self) -> date:
        """The close the filer actually has, after the business-day shift."""
        return self.obligation.adjusted_closes_on


def _supported_years() -> tuple[int, ...]:
    envelope = published_supported_filing_years()
    assert envelope is not None, "the published authority declares no supported filing years"
    return tuple(envelope.years)


def first_unpublished_calendar_year(operation: PinnedAuthorityOperation) -> int:
    """Return the first year from the support floor whose holiday calendar the authority does not publish.

    Publications are authored one year at a time, so the walk ends at the year
    after the newest one.
    """
    for year in count(min(_supported_years())):
        try:
            holiday_calendar_from_authority(year, operation=operation)
        except DeadlineValidationError:
            return year
    raise AssertionError("unreachable: the year walk is unbounded")


def _scanned(
    profile: TaxpayerProfile,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ScannedObligation, ...]:
    engine = DeadlineEngine(authority=operation)
    rows: list[ScannedObligation] = []
    for filing_year in _supported_years():
        schedule = engine.compute(profile, filing_year, today=date(filing_year, 1, 1))
        rows.extend(ScannedObligation(filing_year=filing_year, obligation=row) for row in schedule.obligations)
    return tuple(rows)


def obligation_with_a_shifted_close(
    profile: TaxpayerProfile,
    *,
    operation: PinnedAuthorityOperation,
) -> ScannedObligation:
    """Return the first obligation whose close moved to the next business day.

    Raises:
        AssertionError: No supported year authors such a window for this
            profile, so the case this scan exists for is not in the envelope.
    """
    for scanned in _scanned(profile, operation=operation):
        row = scanned.obligation
        if row.adjusted_closes_on > row.closes_on:
            return scanned
    raise AssertionError("no supported filing year authors a window whose close moves to the next business day")


def obligations_with_an_unresolvable_shift(
    profile: TaxpayerProfile,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ScannedObligation, ...]:
    """Return every dated obligation of the supported years whose shift calendar could not be resolved."""
    return tuple(
        scanned
        for scanned in _scanned(profile, operation=operation)
        if scanned.obligation.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    )


__all__ = [
    "ScannedObligation",
    "first_unpublished_calendar_year",
    "obligation_with_a_shifted_close",
    "obligations_with_an_unresolvable_shift",
]
