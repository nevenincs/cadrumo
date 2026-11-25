"""The holiday-calendar coverage gate refuses a deadline year without a complete calendar.

Every year is read from the registry: the support envelope selects the filing
years, their governing deadline windows give the calendar years, and the
territory catalogue gives the jurisdictions. The planted defects remove one
derived year's publication, or one derived territory's verification, from an
isolated copy of the authored facts and load it through the real fact loader.
"""

from __future__ import annotations

import shutil
from datetime import date
from functools import cache
from typing import TYPE_CHECKING

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority

from ..fact_loader import load_governed_facts
from ..holiday_calendar_coverage import (
    HolidayCalendarYearDemand,
    holiday_calendar_coverage_failures,
    holiday_calendar_year_demand,
    verify_holiday_calendar_coverage,
)
from ..loader import load_registry_tree

if TYPE_CHECKING:
    from pathlib import Path

    from cadrumo.domain.calculations.registry.schema import ModeloDefinition
    from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PUBLICATION_FILE = "0066-holiday-calendar-publication.toml"


@cache
def _bundled_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return load_registry_tree(bundled_path("registry", "aeat"))


@cache
def _bundled_demand() -> HolidayCalendarYearDemand:
    modelos, catalogues = _bundled_tree()
    return holiday_calendar_year_demand(modelos, catalogues)


def _catalogues_with_facts(facts_dir: Path) -> RegistryCatalogues:
    _, catalogues = _bundled_tree()
    facts = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in load_governed_facts(facts_dir)})
    return catalogues.model_copy(update={"facts": facts})


def _isolated_facts(tmp_path: Path) -> Path:
    facts_dir = tmp_path / "facts"
    shutil.copytree(bundled_path("registry", "aeat", "facts"), facts_dir)
    return facts_dir


def _publication_block(text: str, year: int) -> tuple[int, int]:
    marker = f'[[fact.variants]]\nvariant_id = "holiday-calendar-publication:{year}"'
    start = text.index(marker)
    following = text.find("[[fact.variants]]\nvariant_id", start + len(marker))
    return start, len(text) if following == -1 else following


def test_every_deadline_year_of_the_bundled_registry_has_a_complete_calendar() -> None:
    """The authored registry passes, and its demand spans every supported filing year."""
    modelos, catalogues = _bundled_tree()
    demand = _bundled_demand()

    assert set(catalogues.require_supported_filing_years().years) <= demand.required
    assert all(year > max(demand.required) for year in demand.awaiting_publication)
    assert holiday_calendar_coverage_failures(demand, catalogues) == ()
    assert verify_holiday_calendar_coverage(modelos, catalogues) == demand


@pytest.mark.parametrize("end_of_demand", ["earliest", "latest"])
def test_a_required_year_without_its_publication_fails_the_gate(tmp_path: Path, end_of_demand: str) -> None:
    """Removing one derived year's calendar publication is refused, at either end of the demand."""
    modelos, _ = _bundled_tree()
    required = _bundled_demand().required
    year = min(required) if end_of_demand == "earliest" else max(required)
    facts_dir = _isolated_facts(tmp_path)
    publication = facts_dir / _PUBLICATION_FILE
    text = publication.read_text(encoding="utf-8")
    start, end = _publication_block(text, year)
    publication.write_text(text[:start] + text[end:], encoding="utf-8", newline="\n")
    catalogues = _catalogues_with_facts(facts_dir)

    failures = holiday_calendar_coverage_failures(_bundled_demand(), catalogues)

    assert failures
    assert all(failure.startswith(f"holiday calendar {year}:") for failure in failures)
    with pytest.raises(RegistryValidationError, match=f"holiday calendar {year}: no publication"):
        verify_holiday_calendar_coverage(modelos, catalogues)


def test_a_required_year_missing_one_jurisdiction_fails_the_gate(tmp_path: Path) -> None:
    """A publication that leaves one catalogue territory unverified is refused for that territory."""
    modelos, bundled_catalogues = _bundled_tree()
    year = min(_bundled_demand().required)
    territory = str(
        resolve_calendar_ccaa_catalogue(
            effective_date=date(year, 1, 1),
            authority=CandidateFactAuthority(
                bundled_catalogues.facts, bundled_catalogues.require_supported_filing_years()
            ),
        ).choices[-1]
    )
    facts_dir = _isolated_facts(tmp_path)
    publication = facts_dir / _PUBLICATION_FILE
    text = publication.read_text(encoding="utf-8")
    start, end = _publication_block(text, year)
    block = text[start:end]
    narrowed = block.replace(f",{territory}", "", 1)
    assert narrowed != block, "the planted territory was not found in the publication"
    publication.write_text(text[:start] + narrowed + text[end:], encoding="utf-8", newline="\n")
    catalogues = _catalogues_with_facts(facts_dir)

    failures = holiday_calendar_coverage_failures(_bundled_demand(), catalogues)

    assert any(f"holiday calendar {year}: territory {territory} " in failure for failure in failures)
    with pytest.raises(RegistryValidationError, match=f"territory {territory} "):
        verify_holiday_calendar_coverage(modelos, catalogues)
