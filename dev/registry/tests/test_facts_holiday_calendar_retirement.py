"""Direct-fact coverage for the retired legal-holiday calendar adapter."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from shutil import copy2

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import EventFactQuery, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import FactSelector, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.deadlines.festivos import (
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
)
from dev.registry.compiler.fact_loader import load_governed_facts
from dev.registry.compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_IDS = frozenset((HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID, HOLIDAY_EVENT_FACT_ID))
_AUTHORITY_DIGEST = "b" * 64
_LEGAL_REF = "ley-39-2015:art-30.5"
_CITATION_TEXT = "Calendario del contribuyente"

# This independent master is the retirement contract, not a reflection of the
# direct facts under test. It preserves every previously published value.
_PUBLICATION_MASTER = {
    "holiday-calendar-publication:2024": (
        date(2024, 1, 1),
        date(2024, 12, 31),
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "holiday-calendar-publication:2025": (
        date(2025, 1, 1),
        date(2025, 12, 31),
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
}

_EVENT_MASTER = {
    "2024-01-01:national:es": (
        date(2024, 1, 1),
        "national",
        None,
        "A\xf1o Nuevo",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-01-06:national:es": (
        date(2024, 1, 6),
        "national",
        None,
        "Epifan\xeda del Se\xf1or",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-03-29:national:es": (
        date(2024, 3, 29),
        "national",
        None,
        "Viernes Santo",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-05-01:national:es": (
        date(2024, 5, 1),
        "national",
        None,
        "Fiesta del Trabajo",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-08-15:national:es": (
        date(2024, 8, 15),
        "national",
        None,
        "Asunci\xf3n de la Virgen",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-10-12:national:es": (
        date(2024, 10, 12),
        "national",
        None,
        "Fiesta Nacional de Espa\xf1a",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-11-01:national:es": (
        date(2024, 11, 1),
        "national",
        None,
        "Todos los Santos",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-12-06:national:es": (
        date(2024, 12, 6),
        "national",
        None,
        "D\xeda de la Constituci\xf3n Espa\xf1ola",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-12-25:national:es": (
        date(2024, 12, 25),
        "national",
        None,
        "Natividad del Se\xf1or",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-05-02:ccaa:es-md": (
        date(2024, 5, 2),
        "ccaa",
        "ES-MD",
        "Fiesta de la Comunidad de Madrid",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-09-11:ccaa:es-ct": (
        date(2024, 9, 11),
        "ccaa",
        "ES-CT",
        "Diada Nacional de Catalu\xf1a",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-02-28:ccaa:es-an": (
        date(2024, 2, 28),
        "ccaa",
        "ES-AN",
        "D\xeda de Andaluc\xeda",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2024-10-09:ccaa:es-vc": (
        date(2024, 10, 9),
        "ccaa",
        "ES-VC",
        "D\xeda de la Comunitat Valenciana",
        "aeat-calendario-contribuyente-2024",
        "boe-resolucion-festivos-2024",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2023-21965",
    ),
    "2025-01-01:national:es": (
        date(2025, 1, 1),
        "national",
        None,
        "A\xf1o Nuevo",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-01-06:national:es": (
        date(2025, 1, 6),
        "national",
        None,
        "Epifan\xeda del Se\xf1or",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-04-18:national:es": (
        date(2025, 4, 18),
        "national",
        None,
        "Viernes Santo",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-05-01:national:es": (
        date(2025, 5, 1),
        "national",
        None,
        "Fiesta del Trabajo",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-08-15:national:es": (
        date(2025, 8, 15),
        "national",
        None,
        "Asunci\xf3n de la Virgen",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-11-01:national:es": (
        date(2025, 11, 1),
        "national",
        None,
        "Todos los Santos",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-12-06:national:es": (
        date(2025, 12, 6),
        "national",
        None,
        "D\xeda de la Constituci\xf3n Espa\xf1ola",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-12-08:national:es": (
        date(2025, 12, 8),
        "national",
        None,
        "Inmaculada Concepci\xf3n",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-12-25:national:es": (
        date(2025, 12, 25),
        "national",
        None,
        "Natividad del Se\xf1or",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-05-02:ccaa:es-md": (
        date(2025, 5, 2),
        "ccaa",
        "ES-MD",
        "Fiesta de la Comunidad de Madrid",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-07-25:ccaa:es-md": (
        date(2025, 7, 25),
        "ccaa",
        "ES-MD",
        "Santiago Ap\xf3stol",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-11-10:ccaa:es-md": (
        date(2025, 11, 10),
        "ccaa",
        "ES-MD",
        "Lunes siguiente a la Almudena (trasladada)",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-04-21:ccaa:es-ct": (
        date(2025, 4, 21),
        "ccaa",
        "ES-CT",
        "Lunes de Pascua Granada",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-06-24:ccaa:es-ct": (
        date(2025, 6, 24),
        "ccaa",
        "ES-CT",
        "San Juan",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-09-11:ccaa:es-ct": (
        date(2025, 9, 11),
        "ccaa",
        "ES-CT",
        "Diada Nacional de Catalu\xf1a",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-12-26:ccaa:es-ct": (
        date(2025, 12, 26),
        "ccaa",
        "ES-CT",
        "San Esteban",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-02-28:ccaa:es-an": (
        date(2025, 2, 28),
        "ccaa",
        "ES-AN",
        "D\xeda de Andaluc\xeda",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-04-17:ccaa:es-an": (
        date(2025, 4, 17),
        "ccaa",
        "ES-AN",
        "Jueves Santo",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-04-17:ccaa:es-vc": (
        date(2025, 4, 17),
        "ccaa",
        "ES-VC",
        "Jueves Santo",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-04-21:ccaa:es-vc": (
        date(2025, 4, 21),
        "ccaa",
        "ES-VC",
        "Lunes de San Vicente Ferrer",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
    "2025-10-09:ccaa:es-vc": (
        date(2025, 10, 9),
        "ccaa",
        "ES-VC",
        "D\xeda de la Comunitat Valenciana",
        "aeat-calendario-contribuyente-2025",
        "boe-resolucion-festivos-2025",
        "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-22011",
    ),
}


def _catalogue(facts_dir: Path | None = None) -> GovernedFactCatalogue:
    root = facts_dir or bundled_path("registry", "aeat", "facts")
    facts = load_governed_facts(root)
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _FACT_IDS})


def _publication_semantics(catalogue: GovernedFactCatalogue) -> dict[str, tuple[date, date, str, str, str]]:
    fact = catalogue.facts[HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID]
    result: dict[str, tuple[date, date, str, str, str]] = {}
    for variant in fact.variants:
        outputs = {output.name: output.value for output in variant.payload.outputs}
        assert variant.date_axis is DateAxis.SUBMISSION_DATE
        assert variant.payload.event_date == variant.valid_from
        assert variant.legal_refs == (_LEGAL_REF,)
        assert variant.source_refs == (variant.source_citations[0].source_ref,)
        assert variant.source_citations[0].required_text == (_CITATION_TEXT,)
        assert variant.ownership.value == "authored"
        result[variant.variant_id] = (
            variant.valid_from,
            variant.valid_to,
            variant.source_refs[0],
            outputs["boe_ref"],
            outputs["boe_url"],
        )
    return result


def _event_semantics(catalogue: GovernedFactCatalogue) -> dict[str, tuple[date, str, str | None, str, str, str, str]]:
    fact = catalogue.facts[HOLIDAY_EVENT_FACT_ID]
    result: dict[str, tuple[date, str, str | None, str, str, str, str]] = {}
    for variant in fact.variants:
        selectors = {selector.name: selector.value for selector in variant.selectors}
        outputs = {output.name: output.value for output in variant.payload.outputs}
        assert variant.date_axis is DateAxis.SUBMISSION_DATE
        assert variant.valid_to == variant.valid_from == variant.payload.event_date
        assert variant.payload.event_code == "public_holiday"
        assert variant.legal_refs == (_LEGAL_REF,)
        assert variant.source_refs == (variant.source_citations[0].source_ref,)
        assert variant.source_citations[0].required_text == (_CITATION_TEXT,)
        assert variant.ownership.value == "authored"
        result[variant.variant_id] = (
            variant.valid_from,
            selectors["jurisdiction"],
            selectors.get("ccaa_code"),
            outputs["name"],
            variant.source_refs[0],
            outputs["boe_ref"],
            outputs["boe_url"],
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
        resolved = resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=date(publication.valid_from.year, 7, 1),
            ),
            authority_digest=_AUTHORITY_DIGEST,
        )
        assert resolved.variant_id == publication.variant_id

    event_fact = catalogue.facts[HOLIDAY_EVENT_FACT_ID]
    for event in event_fact.variants:
        resolved = resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=event.valid_from,
                selectors=event.selectors,
            ),
            authority_digest=_AUTHORITY_DIGEST,
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
    marker = '[[fact.variants]]\nvariant_id = "2025-05-02:ccaa:es-md"'
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
                effective_date=date(2025, 5, 2),
                selectors=(
                    FactSelector(name="jurisdiction", value="ccaa"),
                    FactSelector(name="ccaa_code", value="ES-MD"),
                ),
            ),
            authority_digest=_AUTHORITY_DIGEST,
        )


def test_holiday_adapter_and_raw_calendar_census_are_empty() -> None:
    """Retirement is atomic: no raw calendar compiler, directory, or provider survives."""
    registry_root = bundled_path("registry", "aeat")
    repository_root = Path(__file__).resolve().parents[3]

    assert not tuple((registry_root / "calendars").glob("festivos-*.toml"))
    assert not (repository_root / "dev" / "registry" / "compiler" / "holidays.py").exists()
    assert "legal-holiday-calendars" not in {registration.provider_id for registration in FACT_PROVIDER_REGISTRATIONS}
