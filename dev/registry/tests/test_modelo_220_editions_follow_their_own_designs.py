"""Each Modelo 220 edition declares its boxes where its own record design prints them.

AEAT publishes one diseno de registro per ejercicio for Modelo 220, and the
designs differ year to year: records are added and renamed, boxes move between
records and a number can be reused for another concept. A year whose design is
held is therefore answered by an edition built on that design rather than by a
projection of a later one, each declared box sits on the record its edition's
own design prints it on, and a continuity chain shared by two consecutive
editions is printed on the same record by both designs.
"""

from __future__ import annotations

import re
from datetime import date
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..compiler.record_design import extract_record_design
from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "220"
_DESIGN_PREFIX = f"aeat-dr-{_MODELO}-"
_BOX = re.compile(r"\[\s*(\d{3,6})\s*\]")
_BOXED = re.compile(r"^\d{3,6}$")
_SPAN = re.compile(r"^(t[0-9a-z]+)\.(\d+)(?:-(\d+))?$")


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo(_MODELO)


def _design_of(revision: ModeloRevision) -> str:
    _, catalogues = _modelo()
    designs = [ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design"]
    assert len(designs) == 1, f"edition {revision.id} cites record designs {designs}"
    return designs[0]


@cache
def _printed(design: str) -> dict[str, tuple[frozenset[int], frozenset[tuple[int, int]]]]:
    """Return, per record, the boxes the design prints and its fields' (offset, length)."""
    _, catalogues = _modelo()
    corpus_path = catalogues.sources[design].corpus_path
    assert corpus_path is not None
    extraction = extract_record_design(bundled_path(*corpus_path.split("/")))
    return {
        sheet.name: (
            frozenset(int(box) for field in sheet.fields for box in _BOX.findall(field.description)),
            frozenset((field.offset, field.length) for field in sheet.fields),
        )
        for sheet in extraction.sheets
    }


def _record(casilla: CasillaDefinition) -> str | None:
    if casilla.segmento:
        return str(casilla.segmento)
    match = _SPAN.match(str(casilla.number))
    return str(match.group(1)).upper() if match else None


def _unprinted(revision: ModeloRevision, casillas: tuple[CasillaDefinition, ...] | None = None) -> list[str]:
    """Return the casillas whose box or byte span the edition's own design does not print on their record."""
    printed = _printed(_design_of(revision))
    missing: list[str] = []
    for casilla in revision.casillas if casillas is None else casillas:
        record, number = _record(casilla), str(casilla.number)
        if record is None:
            continue
        boxes, spans = printed.get(record, (frozenset(), frozenset()))
        if _BOXED.match(number) and casilla.segmento:
            if int(number) not in boxes:
                missing.append(str(casilla.id))
            continue
        span = _SPAN.match(number)
        if span:
            start = int(span.group(2))
            end = int(span.group(3) or start)
            if (start, end - start + 1) not in spans:
                missing.append(str(casilla.id))
    return missing


def _support() -> SupportedFilingYearsCatalogue:
    _, catalogues = _modelo()
    support = catalogues.supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support


def _years_with_a_design() -> tuple[int, ...]:
    _, catalogues = _modelo()
    years = {
        source.applies_from.year
        for source_id, source in catalogues.sources.items()
        if source_id.startswith(_DESIGN_PREFIX) and source.kind == "record_design" and source.applies_from is not None
    }
    return tuple(sorted(year for year in years if year in _support().years))


def _selected(year: int) -> ModeloRevision:
    modelo, _ = _modelo()
    return select_revision(modelo, filing_year=year, period="0A", support=_support())


def _editions() -> tuple[ModeloRevision, ...]:
    modelo, _ = _modelo()
    return ordered_revisions(modelo)


@pytest.mark.parametrize("year", _years_with_a_design())
def test_a_year_whose_design_is_held_resolves_to_the_edition_built_on_it(year: int) -> None:
    _, catalogues = _modelo()
    revision = _selected(year)
    resolution = revision_temporal_resolution(revision, filing_year=year, period="0A", support=_support())
    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    design = catalogues.sources[_design_of(revision)]
    assert design.applies_from is not None and design.applies_to is not None
    assert design.applies_from <= date(year, 1, 1) and date(year, 12, 31) <= design.applies_to
    assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY
    (approval,) = revision.orden_aplicabilidad
    governing = catalogues.legal[approval]
    if governing.governs_periods_from is not None:
        assert governing.governs_periods_from <= date(year, 1, 1)
        assert governing.governs_periods_to is None or date(year, 12, 31) <= governing.governs_periods_to


@pytest.mark.parametrize("revision_id", [str(revision.id) for revision in _editions()])
def test_every_declared_box_is_printed_on_its_record_by_the_editions_own_design(revision_id: str) -> None:
    modelo, _ = _modelo()
    assert _unprinted(modelo.revisions[revision_id]) == []


def test_a_box_its_design_does_not_print_on_the_record_is_reported() -> None:
    revision = _editions()[0]
    template = next(c for c in revision.casillas if c.segmento and _BOXED.match(str(c.number)))
    boxes, _ = _printed(_design_of(revision))[str(template.segmento)]
    unprinted = next(str(n).zfill(5) for n in range(1, 100000) if n not in boxes)
    planted = template.model_copy(update={"id": f"{template.segmento}:{unprinted}", "number": unprinted})
    assert _unprinted(revision, (template, planted)) == [planted.id]


def _shared_chains(earlier: ModeloRevision, later: ModeloRevision) -> list[tuple[CasillaDefinition, CasillaDefinition]]:
    by_chain = {c.continuidad_id: c for c in earlier.casillas if c.continuidad_id}
    return [(by_chain[c.continuidad_id], c) for c in later.casillas if c.continuidad_id in by_chain]


def _chains_off_their_record(
    earlier: ModeloRevision,
    later: ModeloRevision,
    pairs: list[tuple[CasillaDefinition, CasillaDefinition]] | None = None,
) -> list[str]:
    """Return the shared box-numbered chains the two designs do not both print on the row's record."""
    first, second = _printed(_design_of(earlier)), _printed(_design_of(later))
    off: list[str] = []
    for left, right in _shared_chains(earlier, later) if pairs is None else pairs:
        for casilla, printed in ((left, first), (right, second)):
            number = str(casilla.number)
            if casilla.segmento and _BOXED.match(number):
                boxes, _ = printed.get(str(casilla.segmento), (frozenset(), frozenset()))
                if int(number) not in boxes:
                    off.append(f"{casilla.continuidad_id}@{casilla.id}")
    return off


@pytest.mark.parametrize("index", range(len(_editions()) - 1))
def test_a_chain_two_consecutive_editions_share_is_printed_on_its_record_by_both_designs(index: int) -> None:
    earlier, later = _editions()[index], _editions()[index + 1]
    assert _shared_chains(earlier, later), f"{earlier.id} and {later.id} share no chain"
    assert _chains_off_their_record(earlier, later) == []


def test_a_chain_claimed_on_a_box_the_earlier_design_does_not_print_is_reported() -> None:
    earlier, later = _editions()[0], _editions()[1]
    left, right = next((a, b) for a, b in _shared_chains(earlier, later) if a.segmento and _BOXED.match(str(a.number)))
    boxes, _ = _printed(_design_of(earlier))[str(left.segmento)]
    unprinted = next(str(n).zfill(5) for n in range(1, 100000) if n not in boxes)
    planted = left.model_copy(update={"number": unprinted})
    assert _chains_off_their_record(earlier, later, [(planted, right)]) == [f"{left.continuidad_id}@{left.id}"]


@pytest.mark.parametrize("year", _years_with_a_design())
def test_each_edition_files_in_the_25_days_after_june_following_its_year(year: int) -> None:
    (window,) = _selected(year).deadline_windows
    assert (window.filing_year, window.opens_on, window.closes_on) == (
        year,
        date(year + 1, 7, 1),
        date(year + 1, 7, 25),
    )
    assert window.payment_cutoff_on is not None and window.opens_on < window.payment_cutoff_on < window.closes_on


def _cutoff_unstated(revision: ModeloRevision) -> list[str]:
    """Return the windows citing their approving orden whose cited provisions never state the payment cutoff."""
    _, catalogues = _modelo()
    (approval,) = revision.orden_aplicabilidad
    orden = approval.split(":", 1)[0]
    unstated = []
    for window in revision.deadline_windows:
        cited = [catalogues.legal[ref] for ref in window.legal_refs if ref.startswith(f"{orden}:")]
        if not cited or window.payment_cutoff_on is None:
            continue
        cutoff = f"hasta el {window.payment_cutoff_on.day} de julio de {window.payment_cutoff_on.year}"
        if not any(cutoff in text for ref in cited for text in ref.required_text):
            unstated.append(window.id)
    return unstated


def _cites_its_orden(revision: ModeloRevision) -> bool:
    (approval,) = revision.orden_aplicabilidad
    orden = approval.split(":", 1)[0]
    return any(ref.startswith(f"{orden}:") for window in revision.deadline_windows for ref in window.legal_refs)


def test_a_window_citing_its_ordens_domiciliacion_window_takes_its_cutoff_from_it() -> None:
    citing = [revision for revision in _editions() if _cites_its_orden(revision)]
    assert len(citing) >= 2, [revision.id for revision in citing]
    assert {str(revision.id): _cutoff_unstated(revision) for revision in citing} == {str(r.id): [] for r in citing}
    shifted = citing[0].model_copy(
        update={
            "deadline_windows": tuple(
                window.model_copy(update={"payment_cutoff_on": date(window.closes_on.year, 7, 24)})
                for window in citing[0].deadline_windows
            )
        }
    )
    assert _cutoff_unstated(shifted) == [window.id for window in citing[0].deadline_windows]
