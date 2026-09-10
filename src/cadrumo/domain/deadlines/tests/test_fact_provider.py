"""Focused governed-fact coverage for legally grounded calendars."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.resources.bundled_data import bundled_path
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.facts.resolution import EventFactQuery, resolve_governed_fact
from ...calculations.registry.facts.schema import EventFactPayload, FactSelector, GovernedFactCatalogue
from ...calculations.registry.schema_base import DateAxis
from ..festivos import (
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
    CalendarCCAA,
    HolidayJurisdiction,
    compile_holiday_calendar_facts,
    holiday_calendar_from_authority,
    load_holiday_calendar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _holiday_query(
    on: date, *, jurisdiction: HolidayJurisdiction, ccaa_code: CalendarCCAA | None = None
) -> EventFactQuery:
    if jurisdiction is HolidayJurisdiction.CCAA and ccaa_code is None:
        raise ValueError("a CCAA holiday query requires ccaa_code")
    selectors = [FactSelector(name="jurisdiction", value=jurisdiction.value)]
    if ccaa_code is not None:
        selectors.append(FactSelector(name="ccaa_code", value=ccaa_code.value))
    return EventFactQuery(
        fact_id=HOLIDAY_EVENT_FACT_ID, date_axis=DateAxis.SUBMISSION_DATE, effective_date=on, selectors=tuple(selectors)
    )


def _catalogue() -> GovernedFactCatalogue:
    facts = compile_holiday_calendar_facts(bundled_path("registry", "aeat"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def test_provider_enrolls_only_boe_identified_calendar_years() -> None:
    fact = _catalogue().facts[HOLIDAY_EVENT_FACT_ID]
    publication = _catalogue().facts[HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID]

    assert {variant.valid_from.year for variant in fact.variants} == {2024, 2025}
    assert 2026 not in {variant.valid_from.year for variant in fact.variants}
    assert {variant.valid_from.year for variant in publication.variants} == {2024, 2025}


def test_publication_event_proves_a_clear_date_is_in_a_published_calendar() -> None:
    resolved = resolve_governed_fact(
        _catalogue(),
        EventFactQuery(
            fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=date(2025, 3, 4),
        ),
        authority_digest="e" * 64,
    )
    assert isinstance(resolved.payload, EventFactPayload)
    assert resolved.payload.event_code == "holiday_calendar_published"
    assert (
        dict((output.name, output.value) for output in resolved.payload.outputs)["boe_ref"]
        == "boe-resolucion-festivos-2025"
    )


def test_authority_calendar_facade_preserves_values_and_fails_closed_when_unpublished() -> None:
    calendar = holiday_calendar_from_authority(2025, authority=bundled_authority())
    assert calendar == load_holiday_calendar(2025)
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        holiday_calendar_from_authority(2026, authority=bundled_authority())


def test_exact_ccaa_holiday_query_preserves_legacy_value_and_provenance() -> None:
    on = date(2025, 5, 2)
    legacy = next(holiday for holiday in load_holiday_calendar(2025).ccaa if holiday.holiday_date == on)
    resolved = resolve_governed_fact(
        _catalogue(),
        _holiday_query(on, jurisdiction=HolidayJurisdiction.CCAA, ccaa_code=CalendarCCAA.MADRID),
        authority_digest="c" * 64,
    )
    assert isinstance(resolved.payload, EventFactPayload)
    outputs = {output.name: output.value for output in resolved.payload.outputs}

    assert resolved.payload.event_date == legacy.holiday_date
    assert outputs["name"] == legacy.name
    assert resolved.legal_refs == ("ley-39-2015:art-30.5",)
    assert resolved.source_refs == ("aeat-calendario-contribuyente-2025",)
    assert resolved.source_citations[0].required_text == ("Calendario del contribuyente",)
    assert resolved.review_status.value == "pending_review"


def test_query_contract_refuses_incomplete_or_nonexistent_coordinates() -> None:
    with pytest.raises(ValueError, match="requires ccaa_code"):
        _holiday_query(date(2025, 5, 2), jurisdiction=HolidayJurisdiction.CCAA)
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            _catalogue(),
            _holiday_query(date(2025, 5, 3), jurisdiction=HolidayJurisdiction.NATIONAL),
            authority_digest="d" * 64,
        )
