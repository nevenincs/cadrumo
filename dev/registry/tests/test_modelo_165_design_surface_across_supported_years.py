"""Modelo 165 record-design surface across every supported filing year.

The ejercicio 2023 design repeats every campo of the 2016 design and adds
EMPRESA EMERGENTE at position 184 of the declarant record. Its casillas, export
layout, workbook pin, export link and construct grounding are therefore
authored on the edition that first covers ejercicio 2023 and inherited by the
later one, while the fourteen campos the 2016 design already lays out stay one
continuity chain from the support floor onward.

The year the new campo starts is read from Orden HFP/1284/2023 itself, and the
design governing each year from the source catalogue, so neither oracle is the
edition layout under test.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as CompiledAuthority
from cadrumo.domain.calculations.registry.revision_contracts import NoPredecessor, NoPredecessorCause
from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "165"
_NEW_CAMPO = "empresa-emergente"
_EXPORT = "modelo-165-fichero"
_EXPORT_LINK = "modelo-165-export"
_CONSTRUCT = "modelo-165-informative"
_DECLARANT_RECORD = "modelo-165-declarante"
_DESIGN_PREFIX = f"aeat-dr-{_MODELO}-"


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


SUPPORTED_YEARS = _supported_years()
FLOOR = min(SUPPORTED_YEARS)


@cache
def _amendment() -> tuple[int, int]:
    """Return the first ejercicio and declarant-record position Orden HFP/1284/2023 gives the new campo."""
    raw = bundled_path("corpus", "normatives", "html", "orden-hfp-1284-2023.html.extracted.md").read_text(
        encoding="utf-8"
    )
    # The BOE text separates numbers from their nouns with non-breaking spaces.
    text = raw.replace("\u00a0", " ")
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("# ") and "modelo 165" in line)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("# ")), len(lines))
    article = "\n".join(lines[start:end])
    position = re.search(r"«EMPRESA EMERGENTE», que ocupará la posición (\d+) del registro de tipo 1", article)
    first = re.search(r"por primera vez, a las declaraciones informativas correspondientes al ejercicio (\d{4})", text)
    assert position is not None and first is not None
    return int(first.group(1)), int(position.group(1))


@cache
def _governing_design(filing_year: int) -> str:
    """The Modelo 165 record design whose catalogued applicability covers ``filing_year``."""
    sources = load_shared_catalogues(bundled_path("registry", "aeat")).sources
    governing = [
        ref
        for ref, source in sources.items()
        if str(ref).startswith(_DESIGN_PREFIX)
        and (source.applies_from is None or source.applies_from.year <= filing_year)
        and (source.applies_to is None or source.applies_to.year >= filing_year)
    ]
    assert len(governing) == 1, (filing_year, governing)
    return str(governing[0])


@pytest.fixture(scope="module")
def edition(registry_authority: CompiledAuthority) -> Callable[[int], RegistrySnapshot]:
    """The Modelo 165 annual edition the canonical resolver selects for one filing year."""

    def select(filing_year: int) -> RegistrySnapshot:
        return registry_authority.snapshot(
            _MODELO, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.APPLICABILITY
        )

    return select


def test_the_oracle_places_the_new_campo_inside_the_envelope() -> None:
    first, position = _amendment()
    assert FLOOR < first <= max(SUPPORTED_YEARS)
    assert position == 184


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_design_casillas_are_one_chain_in_every_year(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    def chains(year: int) -> dict[str, tuple[str, str | None]]:
        return {
            str(casilla.id): (str(casilla.number), casilla.continuidad_id)
            for casilla in edition(year).revision.casillas
            if casilla.id != _NEW_CAMPO
        }

    floor_chains = chains(FLOOR)
    assert floor_chains
    assert all(chain is not None for _, chain in floor_chains.values()), floor_chains
    assert chains(filing_year) == floor_chains


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_the_new_campo_hydrates_from_its_first_ejercicio(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    first, position = _amendment()
    casillas = {str(casilla.id): casilla for casilla in edition(filing_year).revision.casillas}

    assert (_NEW_CAMPO in casillas) is (filing_year >= first), filing_year
    if filing_year >= first:
        assert str(casillas[_NEW_CAMPO].number) == f"tipo1.{position}"
        assert tuple(map(str, casillas[_NEW_CAMPO].source_refs)) == (_governing_design(filing_year),)


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_the_export_layout_follows_the_governing_design(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    first, position = _amendment()
    revision = edition(filing_year).revision
    layout = next(item for item in revision.export_layouts if item.id == _EXPORT)
    record = next(item for item in layout.records if item.id == _DECLARANT_RECORD)
    spans = {str(field.id): (field.offset, field.length) for field in record.fields}
    at_position = next(field for field in record.fields if field.offset == position)
    design = _governing_design(filing_year)

    assert tuple(map(str, layout.source_refs)) == (design,)
    assert sum(length or 0 for _, length in spans.values()) == 500
    if filing_year >= first:
        assert at_position.casilla_id == _NEW_CAMPO
        assert spans["modelo-165-t1-blancos"] == (position + 1, 500 - position)
    else:
        assert at_position.id == "modelo-165-t1-blancos"
        assert spans["modelo-165-t1-blancos"] == (position, 500 - position + 1)


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_export_link_construct_and_workbook_pin_cite_the_governing_design(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    revision = edition(filing_year).revision
    design = _governing_design(filing_year)
    link = next(item for item in revision.application_links if item.id == _EXPORT_LINK)
    construct = next(item for item in revision.constructs if item.id == _CONSTRUCT)
    pins = {str(item.id): item for item in revision.workbook_parity_refs}

    assert tuple(map(str, link.source_refs)) == (design,)
    assert design in {str(ref) for ref in construct.source_refs}
    assert {str(ref) for ref in construct.source_refs if str(ref).startswith(_DESIGN_PREFIX)} == {design}
    assert set(map(str, construct.workbook_parity_refs)) == set(pins)
    assert {str(pin.workbook_source) for pin in pins.values()} == {design}


def _first_design_edition() -> tuple[ModeloRevision, ModeloRevision]:
    """Return the edition that first covers the new campo's ejercicio and the edition before it."""
    first, _ = _amendment()
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", _MODELO))
    ordered = sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from)
    index = next(i for i, revision in enumerate(ordered) if revision.valid_from.year == first)
    return ordered[index], ordered[index - 1]


def test_the_first_design_edition_reuses_storage_without_a_legal_predecessor() -> None:
    edition_2023, before = _first_design_edition()

    assert isinstance(edition_2023.predecessor, NoPredecessor)
    assert edition_2023.predecessor.cause is NoPredecessorCause.lower_grade
    assert edition_2023.casilla_storage_baseline == before.id
    assert edition_2023.family_storage_baseline == before.id
    assert edition_2023.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY
    assert before.effective_authority_grade is RegistryAuthorityGrade.FILING


def test_the_later_edition_keeps_filing_grade_and_its_own_window(
    edition: Callable[[int], RegistrySnapshot],
) -> None:
    edition_2023, _ = _first_design_edition()
    later_year = max(SUPPORTED_YEARS)
    revision = edition(later_year).revision
    construct = next(item for item in revision.constructs if item.id == _CONSTRUCT)

    assert revision.id != edition_2023.id
    assert revision.effective_authority_grade is RegistryAuthorityGrade.FILING
    assert tuple(map(str, construct.deadline_windows)) == (f"modelo-165-{later_year}-0a",)
    assert {str(window.id) for window in revision.deadline_windows} == {f"modelo-165-{later_year}-0a"}
