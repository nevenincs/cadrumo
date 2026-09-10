"""Behavioral publication coverage for authored category and holiday inputs."""

from __future__ import annotations

from datetime import date
from shutil import copy2
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    EventFactQuery,
    MappingFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import (
    FactSelector,
    GovernedFactCatalogue,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.categories.registry import CATEGORY_PROFILE_FACT_ID
from cadrumo.domain.categories.errors import CategoryValidationError
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.deadlines.festivos import (
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
    CalendarCCAA,
    HolidayJurisdiction,
)
from cadrumo.domain.deadlines.errors import DeadlineValidationError
from dev.registry.compiler.categories import compile_category_profile_facts
from dev.registry.compiler.holidays import compile_holiday_calendar_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _catalogue(*facts):
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})


def _candidate_file(tmp_path: Path, *relative: str) -> Path:
    source = bundled_path("registry", "aeat").joinpath(*relative)
    target = tmp_path.joinpath(*relative)
    target.parent.mkdir(parents=True)
    copy2(source, target)
    return target


def test_authored_category_profiles_publish_a_year_specific_resolvable_fact() -> None:
    facts = compile_category_profile_facts(bundled_path("registry", "aeat"))
    resolved = resolve_governed_fact(
        _catalogue(*facts),
        MappingFactQuery(
            fact_id=CATEGORY_PROFILE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
            selectors=(FactSelector(name="category", value=SpendingCategory.SEGUROS_SALUD_AUTONOMO.value),),
        ),
        authority_digest="a" * 64,
    )

    values = {entry.key: entry.value for entry in resolved.payload.entries}
    assert values["proportionality_kind"] == "statutory_cap"
    assert values["statutory_cap_variant.general.eur"] == 500
    assert resolved.source_citations
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            _catalogue(*facts),
            MappingFactQuery(
                fact_id=CATEGORY_PROFILE_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(2099, 12, 31),
                selectors=(FactSelector(name="category", value=SpendingCategory.SEGUROS_SALUD_AUTONOMO.value),),
            ),
            authority_digest="a" * 64,
        )


def test_authored_holiday_calendars_publish_only_evidenced_years_and_exact_ccaa_events() -> None:
    facts = compile_holiday_calendar_facts(bundled_path("registry", "aeat"))
    catalogue = _catalogue(*facts)
    publication = resolve_governed_fact(
        catalogue,
        EventFactQuery(
            fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=date(2025, 3, 4),
        ),
        authority_digest="b" * 64,
    )
    event = resolve_governed_fact(
        catalogue,
        EventFactQuery(
            fact_id=HOLIDAY_EVENT_FACT_ID,
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=date(2025, 5, 2),
            selectors=(
                FactSelector(name="jurisdiction", value=HolidayJurisdiction.CCAA.value),
                FactSelector(name="ccaa_code", value=CalendarCCAA.MADRID.value),
            ),
        ),
        authority_digest="b" * 64,
    )

    assert dict((item.name, item.value) for item in publication.payload.outputs)["boe_ref"] == "boe-resolucion-festivos-2025"
    assert dict((item.name, item.value) for item in event.payload.outputs)["name"]
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=date(2026, 3, 4),
            ),
            authority_digest="b" * 64,
        )


def test_category_compiler_refuses_a_duplicate_category_in_an_isolated_authored_candidate(tmp_path: Path) -> None:
    target = _candidate_file(tmp_path, "categories", "profiles.toml")
    target.write_text(
        target.read_text(encoding="utf-8").replace('category = "vehiculo_combustible"', 'category = "hardware_amortizable"'),
        encoding="utf-8",
    )

    with pytest.raises(CategoryValidationError, match="duplicate spending category"):
        compile_category_profile_facts(tmp_path)


def test_holiday_compiler_refuses_a_calendar_whose_declared_year_disagrees_with_its_filename(tmp_path: Path) -> None:
    target = _candidate_file(tmp_path, "calendars", "festivos-2025.toml")
    target.write_text(
        target.read_text(encoding="utf-8").replace("year = 2025", "year = 2024", 1),
        encoding="utf-8",
    )

    with pytest.raises(DeadlineValidationError, match="holiday calendar year mismatch"):
        compile_holiday_calendar_facts(tmp_path)
