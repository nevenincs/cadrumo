"""Development-only parser and fact compiler for authored holiday calendars."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.core.toml import read_toml
from cadrumo.domain.calculations.registry.facts.schema import (
    EventFactPayload,
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    NamedFactValue,
)
from .loader_cache import toml_file_fingerprint
from .loader_fingerprints import RegistryPathFingerprints
from cadrumo.domain.calculations.registry.schema_base import DateAxis, SourceCitation
from cadrumo.domain.deadlines.errors import DeadlineValidationError
from cadrumo.domain.deadlines.festivos import (
    HOLIDAY_CALENDAR_PROVIDER_DIRECTORY,
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
    CalendarCCAA,
    Holiday,
    HolidayCalendar,
    HolidayJurisdiction,
)

_NonEmptyShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_TOML_ROW_CONFIG: ConfigDict = ConfigDict(frozen=True, extra="forbid", validate_default=True)
_HOLIDAY_SHIFT_LEGAL_REF = "ley-39-2015:art-30.5"


class _NationalHolidayRow(BaseModel):
    model_config = _TOML_ROW_CONFIG
    date: date
    name: _NonEmptyShortString


class _CcaaHolidayRow(BaseModel):
    model_config = _TOML_ROW_CONFIG
    date: date
    ccaa_code: CalendarCCAA
    name: _NonEmptyShortString


class _HolidayCalendarToml(BaseModel):
    model_config = _TOML_ROW_CONFIG
    year: Annotated[int, Field(ge=2000, le=2100)]
    boe_ref: _NonEmptyShortString
    boe_url: str | None = None
    national: list[_NationalHolidayRow] = Field(default_factory=list)
    ccaa: list[_CcaaHolidayRow] = Field(default_factory=list)


@lru_cache(maxsize=64)
def load_holiday_calendar(path: Path, year: int) -> HolidayCalendar:
    """Parse one exact authored calendar path for development publication."""
    if not path.exists():
        raise DeadlineValidationError(f"holiday calendar for year {year} not registered (expected file: {path.name})")
    raw = read_toml(path, error_factory=DeadlineValidationError)
    declared_year = raw.get("year")
    if declared_year != year:
        raise DeadlineValidationError(
            f"holiday calendar year mismatch: filename declares {year} but TOML declares {declared_year!r}"
        )
    try:
        parsed = _HolidayCalendarToml.model_validate(raw)
        return HolidayCalendar(
            year=year,
            boe_ref=parsed.boe_ref,
            boe_url=parsed.boe_url,
            national=tuple(
                Holiday(holiday_date=row.date, jurisdiction=HolidayJurisdiction.NATIONAL, name=row.name)
                for row in parsed.national
            ),
            ccaa=tuple(
                Holiday(
                    holiday_date=row.date, jurisdiction=HolidayJurisdiction.CCAA, ccaa_code=row.ccaa_code, name=row.name
                )
                for row in parsed.ccaa
            ),
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise DeadlineValidationError(f"{path}: invalid holiday calendar row: {exc}") from exc


def compile_holiday_calendar_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    calendar_root = registry_root.resolve() / HOLIDAY_CALENDAR_PROVIDER_DIRECTORY
    holidays: list[GovernedFactVariant] = []
    publications: list[GovernedFactVariant] = []
    for path in sorted(calendar_root.glob("festivos-*.toml"), key=lambda item: item.name):
        token = path.stem.removeprefix("festivos-")
        if not token.isdigit():
            continue
        calendar = load_holiday_calendar(path.resolve(), int(token))
        if calendar.boe_url is None:
            continue
        publications.append(_publication_variant(calendar))
        holidays.extend(_holiday_variant(calendar, holiday) for holiday in (*calendar.national, *calendar.ccaa))
    if not publications:
        return ()
    facts = [
        GovernedFact(
            fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
            family=GovernedFactFamily.EVENT,
            variants=tuple(publications),
        )
    ]
    if holidays:
        facts.append(
            GovernedFact(fact_id=HOLIDAY_EVENT_FACT_ID, family=GovernedFactFamily.EVENT, variants=tuple(holidays))
        )
    return tuple(facts)


def collect_holiday_calendar_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    root = registry_root.resolve() / HOLIDAY_CALENDAR_PROVIDER_DIRECTORY
    return tuple(toml_file_fingerprint(path.resolve()) for path in sorted(root.glob("*.toml")))


def reset_holiday_calendar_fact_provider() -> None:
    load_holiday_calendar.cache_clear()


def _publication_variant(calendar: HolidayCalendar) -> GovernedFactVariant:
    source_ref = f"aeat-calendario-contribuyente-{calendar.year}"
    return GovernedFactVariant(
        variant_id=f"holiday-calendar-publication:{calendar.year}",
        date_axis=DateAxis.SUBMISSION_DATE,
        valid_from=date(calendar.year, 1, 1),
        valid_to=date(calendar.year, 12, 31),
        payload=EventFactPayload(
            event_date=date(calendar.year, 1, 1),
            event_code="holiday_calendar_published",
            outputs=(
                NamedFactValue(name="boe_ref", value=calendar.boe_ref),
                NamedFactValue(name="boe_url", value=calendar.boe_url or ""),
            ),
        ),
        legal_refs=(_HOLIDAY_SHIFT_LEGAL_REF,),
        source_refs=(source_ref,),
        source_citations=(SourceCitation(source_ref=source_ref, required_text=("Calendario del contribuyente",)),),
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        ownership=FactOwnership.GENERATED,
    )


def _holiday_variant(calendar: HolidayCalendar, holiday: Holiday) -> GovernedFactVariant:
    selectors = [FactSelector(name="jurisdiction", value=holiday.jurisdiction.value)]
    if holiday.ccaa_code is not None:
        selectors.append(FactSelector(name="ccaa_code", value=holiday.ccaa_code.value))
    source_ref = f"aeat-calendario-contribuyente-{calendar.year}"
    return GovernedFactVariant(
        variant_id=f"{holiday.holiday_date.isoformat()}:{holiday.jurisdiction.value}:{holiday.ccaa_code.value.lower() if holiday.ccaa_code is not None else 'es'}",
        selectors=tuple(selectors),
        date_axis=DateAxis.SUBMISSION_DATE,
        valid_from=holiday.holiday_date,
        valid_to=holiday.holiday_date,
        payload=EventFactPayload(
            event_date=holiday.holiday_date,
            event_code="public_holiday",
            outputs=(
                NamedFactValue(name="name", value=holiday.name),
                NamedFactValue(name="boe_ref", value=calendar.boe_ref),
                NamedFactValue(name="boe_url", value=calendar.boe_url or ""),
            ),
        ),
        legal_refs=(_HOLIDAY_SHIFT_LEGAL_REF,),
        source_refs=(source_ref,),
        source_citations=(SourceCitation(source_ref=source_ref, required_text=("Calendario del contribuyente",)),),
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        ownership=FactOwnership.GENERATED,
    )
