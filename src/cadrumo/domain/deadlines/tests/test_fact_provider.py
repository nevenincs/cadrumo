"""Focused governed-fact coverage for legally grounded calendars."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.resources.bundled_data import bundled_path
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.facts.resolution import resolve_governed_fact
from ...calculations.registry.facts.schema import EventFactPayload, GovernedFactCatalogue
from ..festivos import (
    HOLIDAY_EVENT_FACT_ID,
    CalendarCCAA,
    HolidayJurisdiction,
    compile_holiday_calendar_facts,
    holiday_event_fact_query,
    load_holiday_calendar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue() -> GovernedFactCatalogue:
    facts = compile_holiday_calendar_facts(bundled_path("registry", "aeat"))
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def test_provider_enrolls_only_boe_identified_calendar_years() -> None:
    fact = _catalogue().facts[HOLIDAY_EVENT_FACT_ID]

    assert {variant.valid_from.year for variant in fact.variants} == {2024, 2025}
    assert 2026 not in {variant.valid_from.year for variant in fact.variants}


def test_exact_ccaa_holiday_query_preserves_legacy_value_and_provenance() -> None:
    on = date(2025, 5, 2)
    legacy = next(holiday for holiday in load_holiday_calendar(2025).ccaa if holiday.holiday_date == on)
    resolved = resolve_governed_fact(
        _catalogue(),
        holiday_event_fact_query(on, jurisdiction=HolidayJurisdiction.CCAA, ccaa_code=CalendarCCAA.MADRID),
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
        holiday_event_fact_query(date(2025, 5, 2), jurisdiction=HolidayJurisdiction.CCAA)
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            _catalogue(),
            holiday_event_fact_query(date(2025, 5, 3), jurisdiction=HolidayJurisdiction.NATIONAL),
            authority_digest="d" * 64,
        )
