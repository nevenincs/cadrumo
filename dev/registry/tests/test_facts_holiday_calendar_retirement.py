"""Direct-fact coverage for the retired legal-holiday calendar adapter."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from shutil import copy2

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import EventFactPayload
from cadrumo.domain.calculations.registry.facts.resolution import EventFactQuery, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.facts.variants import FactSelector
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.deadlines.festivos import (
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
)

from ..compiler.fact_loader import load_governed_facts
from ..compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_IDS = frozenset((HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID, HOLIDAY_EVENT_FACT_ID))
_AUTHORITY_DIGEST = "b" * 64
_LEGAL_REF = "ley-39-2015:art-30.5"

# This independent master is the published contract, kept in a recorded data
# file beside this test and extracted from boe.es separately from the facts
# under test: every día inhábil of the Secretaría de Estado de Función Pública
# resolutions and of the Dirección General de Trabajo relación de fiestas
# laborales for the years the facts cover, with each national fiesta that falls
# on a weekend and without sub-territorial days such as the Val d'Aran swap of
# 26 December. The years live only in that recording and in the facts.
_MASTER_PATH = Path(__file__).with_name("data") / "holiday_calendar_master.json"


def _load_master() -> tuple[
    dict[str, tuple[date, date, str, str, str]],
    dict[str, tuple[date, str, str | None, str, str, str, str]],
]:
    recorded = json.loads(_MASTER_PATH.read_text(encoding="utf-8"))
    publications = {
        key: (date.fromisoformat(row[0]), date.fromisoformat(row[1]), row[2], row[3], row[4])
        for key, row in recorded["publications"].items()
    }
    events = {
        key: (date.fromisoformat(row[0]), row[1], row[2], row[3], row[4], row[5], row[6])
        for key, row in recorded["events"].items()
    }
    return publications, events


_PUBLICATION_MASTER, _EVENT_MASTER = _load_master()


def _catalogue(facts_dir: Path | None = None) -> GovernedFactCatalogue:
    root = facts_dir or bundled_path("registry", "aeat", "facts")
    facts = load_governed_facts(root)
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _FACT_IDS})


def _publication_semantics(catalogue: GovernedFactCatalogue) -> dict[str, tuple[date, date, str, str, str]]:
    fact = catalogue.facts[HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID]
    result: dict[str, tuple[date, date, str, str, str]] = {}
    for variant in fact.variants:
        assert isinstance(variant.payload, EventFactPayload)
        outputs = {output.name: output.value for output in variant.payload.outputs}
        valid_from = variant.valid_from
        valid_to = variant.valid_to
        assert valid_from is not None
        assert valid_to is not None
        boe_ref = outputs["boe_ref"]
        boe_url = outputs["boe_url"]
        assert isinstance(boe_ref, str)
        assert isinstance(boe_url, str)
        assert variant.date_axis is DateAxis.SUBMISSION_DATE
        assert variant.payload.event_date == valid_from
        assert _LEGAL_REF in variant.legal_refs
        assert variant.source_refs == (variant.source_citations[0].source_ref,)
        assert variant.source_citations[0].required_text
        assert variant.ownership.value == "authored"
        result[variant.variant_id] = (
            valid_from,
            valid_to,
            variant.source_refs[0],
            boe_ref,
            boe_url,
        )
    return result


def _event_semantics(catalogue: GovernedFactCatalogue) -> dict[str, tuple[date, str, str | None, str, str, str, str]]:
    fact = catalogue.facts[HOLIDAY_EVENT_FACT_ID]
    result: dict[str, tuple[date, str, str | None, str, str, str, str]] = {}
    for variant in fact.variants:
        assert isinstance(variant.payload, EventFactPayload)
        selectors = {selector.name: selector.value for selector in variant.selectors}
        outputs = {output.name: output.value for output in variant.payload.outputs}
        valid_from = variant.valid_from
        valid_to = variant.valid_to
        assert valid_from is not None
        assert valid_to is not None
        jurisdiction = selectors["jurisdiction"]
        ccaa_code = selectors.get("ccaa_code")
        name = outputs["name"]
        boe_ref = outputs["boe_ref"]
        boe_url = outputs["boe_url"]
        assert isinstance(jurisdiction, str)
        assert ccaa_code is None or isinstance(ccaa_code, str)
        assert isinstance(name, str)
        assert isinstance(boe_ref, str)
        assert isinstance(boe_url, str)
        assert variant.date_axis is DateAxis.SUBMISSION_DATE
        assert valid_to == valid_from == variant.payload.event_date
        assert variant.payload.event_code == "public_holiday"
        assert _LEGAL_REF in variant.legal_refs
        assert variant.source_refs == (variant.source_citations[0].source_ref,)
        assert variant.source_citations[0].required_text
        assert variant.ownership.value == "authored"
        result[variant.variant_id] = (
            valid_from,
            jurisdiction,
            ccaa_code,
            name,
            variant.source_refs[0],
            boe_ref,
            boe_url,
        )
    return result


def _assert_exact_master(catalogue: GovernedFactCatalogue) -> None:
    assert _publication_semantics(catalogue) == _PUBLICATION_MASTER
    assert _event_semantics(catalogue) == _EVENT_MASTER


def test_authored_holiday_facts_match_the_complete_publication_and_event_master() -> None:
    """Every supported publication and event retains its direct semantic record."""
    catalogue = _catalogue()
    _assert_exact_master(catalogue)

    publication_fact = catalogue.facts[HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID]
    for publication in publication_fact.variants:
        assert publication.valid_from is not None
        resolved = resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=date(publication.valid_from.year, 7, 1),
            ),
            authority_digest=_AUTHORITY_DIGEST,
            support=committed_supported_filing_years(),
        )
        assert resolved.variant_id == publication.variant_id

    event_fact = catalogue.facts[HOLIDAY_EVENT_FACT_ID]
    for event in event_fact.variants:
        assert event.valid_from is not None
        resolved = resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=event.valid_from,
                selectors=event.selectors,
            ),
            authority_digest=_AUTHORITY_DIGEST,
            support=committed_supported_filing_years(),
        )
        assert resolved.variant_id == event.variant_id


def test_a_same_count_holiday_substitution_breaks_the_direct_fact_master(tmp_path: Path) -> None:
    """Mutation bite: matching the old row count cannot mask a changed event."""
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    source = bundled_path("registry", "aeat", "facts", "0067-public-holiday.toml")
    target = facts_dir / source.name
    copy2(source, target)

    original = target.read_text(encoding="utf-8")
    mutated = original.replace(
        'value = "Fiesta de la Comunidad de Madrid"',
        'value = "Fiesta de la Comunidad de Murcia"',
        1,
    )
    assert mutated != original, "the same-count mutation target was not found"
    target.write_text(mutated, encoding="utf-8")

    catalogue = _catalogue(facts_dir)
    assert len(_event_semantics(catalogue)) == len(_EVENT_MASTER)
    with pytest.raises(AssertionError):
        assert _event_semantics(catalogue) == _EVENT_MASTER


def test_removing_a_direct_holiday_variant_breaks_its_exact_query(tmp_path: Path) -> None:
    """Mutation bite: a deleted direct fact cannot be masked by any adapter."""
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    source = bundled_path("registry", "aeat", "facts", "0067-public-holiday.toml")
    target = facts_dir / source.name
    copy2(source, target)

    original = target.read_text(encoding="utf-8")
    variant_id, (removed_date, *_rest) = min((key, row) for key, row in _EVENT_MASTER.items() if row[2] == "ES-MD")
    marker = f'[[fact.variants]]\nvariant_id = "{variant_id}"'
    start = original.index(marker)
    next_variant = original.index("[[fact.variants]]", start + len(marker))
    target.write_text(original[:start] + original[next_variant:], encoding="utf-8")

    catalogue = _catalogue(facts_dir)
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=removed_date,
                selectors=(
                    FactSelector(name="jurisdiction", value="ccaa"),
                    FactSelector(name="ccaa_code", value="ES-MD"),
                ),
            ),
            authority_digest=_AUTHORITY_DIGEST,
            support=committed_supported_filing_years(),
        )


def test_holiday_adapter_and_raw_calendar_census_are_empty() -> None:
    """Retirement is atomic: no raw calendar compiler, directory, or provider survives."""
    registry_root = bundled_path("registry", "aeat")
    repository_root = Path(__file__).resolve().parents[3]

    assert not tuple((registry_root / "calendars").glob("festivos-*.toml"))
    assert not (repository_root / "dev" / "registry" / "compiler" / "holidays.py").exists()
    assert "legal-holiday-calendars" not in {registration.provider_id for registration in FACT_PROVIDER_REGISTRATIONS}
