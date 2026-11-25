"""Where a requested overview calendar range sits against the registry's filing-year envelope.

The envelope is the pinned authority's single support declaration. A calendar
year can present the obligations of its own filing year and, because a filing
window opens in the year after the period it covers, of the year before. A
calendar year serves nothing only when the envelope admits neither of those
filing years; such a year is unsupported, which is not the same as a year in
which nothing is due.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel

from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.schema_references import TemporalSupportEnvelope
from .calendar_models import OverviewCalendarRange


class OverviewCalendarSupportState(StrEnum):
    """How much of a requested calendar range the filing-year envelope serves.

    Attributes:
        SUPPORTED: Every calendar year is served, and no served filing year
            lies above the horizon.
        PROJECTED: Every calendar year is served, and some served filing year
            lies above the horizon, answered from the newest authored edition
            at calculation grade at most.
        PARTIAL: Some calendar years are served and others are outside the
            envelope; the unserved years carry no obligations, not an empty
            calendar.
        BELOW_FLOOR: The whole range lies below the envelope's floor.
        ABOVE_CEILING: The whole range lies above the envelope's declared hard
            ceiling.
    """

    SUPPORTED = "supported"
    PROJECTED = "projected"
    PARTIAL = "partial"
    BELOW_FLOOR = "below_floor"
    ABOVE_CEILING = "above_ceiling"


UNSUPPORTED_CALENDAR_STATES: Final[frozenset[OverviewCalendarSupportState]] = frozenset(
    {OverviewCalendarSupportState.BELOW_FLOOR, OverviewCalendarSupportState.ABOVE_CEILING}
)
"""States in which the range serves no filing year at all."""


def _calendar_year_is_served(calendar_year: int, envelope: TemporalSupportEnvelope) -> bool:
    """Whether the envelope admits a filing year whose windows fall in ``calendar_year``."""
    return envelope.admits_coordinate(calendar_year) or envelope.admits_coordinate(calendar_year - 1)


def calendar_support_state(
    calendar_range: OverviewCalendarRange, envelope: TemporalSupportEnvelope
) -> OverviewCalendarSupportState:
    """Classify ``calendar_range`` against the envelope's hard gates and authored horizon."""
    calendar_years = range(calendar_range.from_date.year, calendar_range.to_date.year + 1)
    served = [_calendar_year_is_served(year, envelope) for year in calendar_years]
    if not any(served):
        if calendar_range.to_date.year < envelope.floor:
            return OverviewCalendarSupportState.BELOW_FLOOR
        return OverviewCalendarSupportState.ABOVE_CEILING
    if not all(served):
        return OverviewCalendarSupportState.PARTIAL
    if any(year > envelope.horizon and envelope.admits_coordinate(year) for year in calendar_range.covered_years()):
        return OverviewCalendarSupportState.PROJECTED
    return OverviewCalendarSupportState.SUPPORTED


class OverviewCalendarSupport(BaseModel):
    """The envelope a calendar read was served under, and the requested range's place in it.

    ``floor``, ``horizon`` and ``hard_ceiling`` are the pinned authority's
    bounds as its catalogue resolves them; ``hard_ceiling`` is ``None`` when the
    envelope stays open above the horizon.
    """

    model_config = STRICT_FROZEN_CONFIG

    floor: FilingYear
    horizon: FilingYear
    hard_ceiling: FilingYear | None
    state: OverviewCalendarSupportState

    @classmethod
    def for_range(cls, calendar_range: OverviewCalendarRange, envelope: TemporalSupportEnvelope) -> Self:
        """Capture the envelope's bounds and classify ``calendar_range`` against them."""
        return cls(
            floor=envelope.floor,
            horizon=envelope.horizon,
            hard_ceiling=envelope.hard_ceiling,
            state=calendar_support_state(calendar_range, envelope),
        )

    def envelope(self) -> TemporalSupportEnvelope:
        """Rebuild the served envelope from its captured bounds."""
        return TemporalSupportEnvelope(floor=self.floor, horizon=self.horizon, hard_ceiling=self.hard_ceiling)

    @property
    def unsupported(self) -> bool:
        """Whether the range serves no filing year at all."""
        return self.state in UNSUPPORTED_CALENDAR_STATES


__all__ = [
    "UNSUPPORTED_CALENDAR_STATES",
    "OverviewCalendarSupport",
    "OverviewCalendarSupportState",
    "calendar_support_state",
]
