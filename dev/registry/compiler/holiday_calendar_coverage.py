"""Development-only proof that every deadline year has a complete holiday calendar.

A filing close that falls on an inhábil day moves to the next día hábil, and a
domiciliación cutoff counts business days on the filer's territory calendar.
Both read the governed holiday calendar of the year they land in. A year whose
calendar is not authored leaves every close in it unverified, so the same
declaration would be judged differently depending on the filing year. That is
a registry-completeness defect, and this gate refuses it before publication.

The years are derived, never listed: every supported filing year of the
registry's support envelope contributes the years its governing deadline
windows open, close or cut off payment in. Each such year up to the latest one
in which any of those windows opens needs the calendar. A window that stays open
past that year (a multi-year devolución plazo) closes in a year whose calendar
the State has not published yet; those years are reported, not refused, because
no official source can exist for them until it is published.

A year is covered when its own publication event is authored, exactly as the
runtime calendar reads it, and that publication verifies every territory of the
dated deadline-calendar territory catalogue, with at least one national día
inhábil and no regional day outside the verified territories.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final

from cadrumo.domain.calculations.registry.calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import EventFactPayload
from cadrumo.domain.calculations.registry.facts.resolution import EventFactQuery, ResolvedEventFact
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.deadlines.festivos import (
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cadrumo.domain.calculations.registry.schema import ModeloDefinition
    from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
    from cadrumo.domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition

_NATIONAL: Final = "national"
_CCAA: Final = "ccaa"


@dataclass(frozen=True, slots=True)
class HolidayCalendarYearDemand:
    """The calendar years the supported filing years' deadline windows reach.

    Attributes:
        required: Years a governing window opens, closes or cuts payment off in,
            up to the latest year any of them opens in. Each needs a complete
            authored calendar.
        awaiting_publication: Later years only a still-open window closes in;
            their calendar cannot be published yet.
    """

    required: frozenset[int]
    awaiting_publication: frozenset[int]


def holiday_calendar_year_demand(
    modelos: Iterable[ModeloDefinition],
    catalogues: RegistryCatalogues,
) -> HolidayCalendarYearDemand:
    """Derive the calendar years every supported filing year's governing deadline windows reach."""
    support = catalogues.require_supported_filing_years()
    windows = tuple(_governing_windows(tuple(modelos), catalogues, frozenset(support.years)))
    if not windows:
        return HolidayCalendarYearDemand(required=frozenset(), awaiting_publication=frozenset())
    latest_opening = max(window.opens_on.year for window in windows)
    reached: set[int] = set()
    for window in windows:
        reached.update(range(window.opens_on.year, window.closes_on.year + 1))
        if window.payment_cutoff_on is not None:
            reached.add(window.payment_cutoff_on.year)
    required = frozenset(year for year in reached if year <= latest_opening)
    return HolidayCalendarYearDemand(required=required, awaiting_publication=frozenset(reached - required))


def _governing_windows(
    modelos: tuple[ModeloDefinition, ...],
    catalogues: RegistryCatalogues,
    filing_years: frozenset[int],
) -> Iterable[DeadlineWindowDefinition]:
    """Yield the windows of supported filing years that their selected revision owns."""
    support = catalogues.require_supported_filing_years()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for window in revision.deadline_windows:
                if window.filing_year not in filing_years:
                    continue
                selected = select_revision(
                    modelo,
                    filing_year=window.period.filing_year,
                    period=window.period.registry_token,
                    support=support,
                )
                if selected.id == revision.id:
                    yield window


@dataclass(frozen=True, slots=True)
class _HolidayEvent:
    """One authored día inhábil, reduced to what coverage needs."""

    year: int
    jurisdiction: object
    ccaa_code: object


def holiday_calendar_coverage_failures(
    demand: HolidayCalendarYearDemand,
    catalogues: RegistryCatalogues,
) -> tuple[str, ...]:
    """Return one finding for each required year whose calendar is absent or incomplete."""
    authority = CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    holidays = catalogues.facts.facts.get(HOLIDAY_EVENT_FACT_ID)
    events = tuple(
        _HolidayEvent(
            year=variant.payload.event_date.year,
            jurisdiction=selectors.get("jurisdiction"),
            ccaa_code=selectors.get("ccaa_code"),
        )
        for variant in (holidays.variants if holidays is not None else ())
        if isinstance(variant.payload, EventFactPayload)
        for selectors in ({selector.name: selector.value for selector in variant.selectors},)
    )
    failures: list[str] = []
    for year in sorted(demand.required):
        failures.extend(_year_failures(year, authority=authority, events=events))
    return tuple(failures)


def _year_failures(
    year: int,
    *,
    authority: CandidateFactAuthority,
    events: tuple[_HolidayEvent, ...],
) -> list[str]:
    subject = f"holiday calendar {year}"
    coordinate = date(year, 1, 1)
    publication = _authored_publication(year, coordinate, authority=authority)
    if publication is None:
        return [f"{subject}: no publication of fact {HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID!r} is authored for it"]
    outputs = {output.name: output.value for output in publication.payload.outputs}
    verified_value = outputs.get("verified_territories")
    if not isinstance(verified_value, str):
        return [f"{subject}: publication {publication.variant_id!r} declares no verified territories"]
    verified = [token.strip() for token in verified_value.split(",") if token.strip()]
    catalogue = resolve_calendar_ccaa_catalogue(effective_date=coordinate, authority=authority)
    failures = _territory_failures(
        subject, publication.variant_id, verified, {str(token) for token in catalogue.choices}
    )
    failures.extend(_event_failures(subject, [event for event in events if event.year == year], verified))
    return failures


def _territory_failures(subject: str, variant_id: str, verified: list[str], territories: set[str]) -> list[str]:
    """Compare the territories a publication verifies with the territory catalogue."""
    failures = [
        f"{subject}: territory {code} of the deadline-calendar territory catalogue is not verified by "
        f"publication {variant_id!r}"
        for code in sorted(territories - set(verified))
    ]
    failures.extend(
        f"{subject}: publication {variant_id!r} verifies {code}, which the territory catalogue does not declare"
        for code in sorted(set(verified) - territories)
    )
    if len(set(verified)) != len(verified):
        failures.append(f"{subject}: publication {variant_id!r} repeats a verified territory")
    return failures


def _event_failures(subject: str, in_year: list[_HolidayEvent], verified: list[str]) -> list[str]:
    """Check the year's authored día inhábil events against its verified territories."""
    failures: list[str] = []
    if not any(event.jurisdiction == _NATIONAL for event in in_year):
        failures.append(f"{subject}: no national día inhábil of fact {HOLIDAY_EVENT_FACT_ID!r} is authored for it")
    unverified_regions = sorted(
        {str(event.ccaa_code) for event in in_year if event.jurisdiction == _CCAA and event.ccaa_code not in verified}
    )
    failures.extend(
        f"{subject}: a regional día inhábil names {code}, which its publication does not verify"
        for code in unverified_regions
    )
    return failures


def _authored_publication(
    year: int,
    coordinate: date,
    *,
    authority: CandidateFactAuthority,
) -> ResolvedEventFact | None:
    """Resolve the year's publication the way the runtime calendar does, or ``None`` when none is its own."""
    try:
        resolved = authority.resolve_governed_fact(
            EventFactQuery(
                fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=coordinate,
            )
        )
    except RegistryValidationError:
        return None
    if not isinstance(resolved, ResolvedEventFact):
        return None
    # The runtime calendar accepts only a publication authored for this very
    # year: one carried over from a neighbouring year proves nothing about it.
    if (
        resolved.projection_direction is not TemporalProjectionDirection.AUTHORED
        and resolved.payload.event_date.year != year
    ):
        return None
    return resolved


def verify_holiday_calendar_coverage(
    modelos: Iterable[ModeloDefinition],
    catalogues: RegistryCatalogues,
) -> HolidayCalendarYearDemand:
    """Refuse a registry whose deadline years lack a complete holiday calendar, returning the derived years."""
    demand = holiday_calendar_year_demand(modelos, catalogues)
    failures = holiday_calendar_coverage_failures(demand, catalogues)
    if failures:
        raise RegistryValidationError(
            "holiday calendar coverage failed:\n" + "\n".join(f" - {failure}" for failure in failures)
        )
    return demand
