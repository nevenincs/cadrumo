"""Behavioral publication coverage for the holiday adapter."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from shutil import copy2

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import EventFactQuery, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import (
    FactSelector,
    GovernedFactCatalogue,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.deadlines.errors import DeadlineValidationError
from cadrumo.domain.deadlines.festivos import (
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
    CalendarCCAA,
    HolidayJurisdiction,
)
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

    assert (
        dict((item.name, item.value) for item in publication.payload.outputs)["boe_ref"]
        == "boe-resolucion-festivos-2025"
    )
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


def test_holiday_compiler_refuses_a_calendar_whose_declared_year_disagrees_with_its_filename(tmp_path: Path) -> None:
    target = _candidate_file(tmp_path, "calendars", "festivos-2025.toml")
    target.write_text(
        target.read_text(encoding="utf-8").replace("year = 2025", "year = 2024", 1),
        encoding="utf-8",
    )

    with pytest.raises(DeadlineValidationError, match="holiday calendar year mismatch"):
        compile_holiday_calendar_facts(tmp_path)
