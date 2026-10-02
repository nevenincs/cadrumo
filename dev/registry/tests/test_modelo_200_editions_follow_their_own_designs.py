"""Each Modelo 200 year whose record design is held resolves to an edition built on that design.

AEAT publishes one diseno de registro per ejercicio for Modelo 200 and the designs
differ year to year: sheets are added, boxes are added and reused, captions change.
A supported year whose design is held is answered by its own edition rather than a
projection of a later one. The editions share storage from the support floor
forward; a carried row keeps its official caption or has a grounded label evolution,
and a row that first appears in an edition
says on the row why the edition before it does not carry it, citing that edition's
design.
"""

from __future__ import annotations

import re
from datetime import date
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaEvolutionKind
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..compiler.record_design import extract_record_design
from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_DESIGN_PREFIX = f"aeat-dr-{_MODELO}-"
_BOX = re.compile(r"\[([0-9]{3,6})\]")
_NUMBERED = re.compile(r"[0-9]{3,6}")
_ABSENCE = frozenset(
    {
        CasillaLineageOrigin.NEW_ON_FORM,
        CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT,
        CasillaLineageOrigin.NOT_ON_FORM,
    }
)


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo(_MODELO)


def _support() -> SupportedFilingYearsCatalogue:
    _, catalogues = _modelo()
    support = catalogues.supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support


def _design_of(revision: ModeloRevision) -> str:
    _, catalogues = _modelo()
    designs = [ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design"]
    assert len(designs) == 1, f"edition {revision.id} cites record designs {designs}"
    return designs[0]


@cache
def _captions(design: str) -> dict[tuple[str, str], frozenset[str]]:
    """Return, per (sheet, printed box), every caption the design prints it with."""
    _, catalogues = _modelo()
    corpus_path = catalogues.sources[design].corpus_path
    assert corpus_path is not None
    found: dict[tuple[str, str], set[str]] = {}
    for sheet in extract_record_design(bundled_path(*corpus_path.split("/"))).require_complete():
        for field in sheet.fields:
            for number in _BOX.findall(field.description):
                found.setdefault((sheet.name.strip(), number), set()).add(" ".join(field.description.split()))
    return {box: frozenset(texts) for box, texts in found.items()}


def _printed_with(design: str, segmento: str | None, number: str) -> frozenset[str]:
    return frozenset(
        caption
        for (sheet, printed), texts in _captions(design).items()
        if printed == number and (segmento is None or sheet == segmento)
        for caption in texts
    )


def _years_with_a_design() -> tuple[int, ...]:
    _, catalogues = _modelo()
    years = {
        source.applies_from.year
        for source_id, source in catalogues.sources.items()
        if source_id.startswith(_DESIGN_PREFIX)
        and source.kind == "record_design"
        and source.applies_from is not None
        and source.applies_to is not None
        and source.applies_from.year == source.applies_to.year
    }
    return tuple(sorted(year for year in years if year in _support().years))


def _selected(year: int) -> ModeloRevision:
    modelo, _ = _modelo()
    return select_revision(modelo, filing_year=year, period="0A", support=_support())


def _storage_pairs() -> list[tuple[ModeloRevision, ModeloRevision]]:
    modelo, _ = _modelo()
    return [
        (modelo.revisions[str(later.casilla_storage_baseline)], later)
        for later in ordered_revisions(modelo)
        if later.casilla_storage_baseline is not None
    ]


@pytest.mark.parametrize("year", _years_with_a_design())
def test_a_year_whose_design_is_held_resolves_to_the_edition_built_on_it(year: int) -> None:
    _, catalogues = _modelo()
    revision = _selected(year)
    resolution = revision_temporal_resolution(revision, filing_year=year, period="0A", support=_support())
    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    design = catalogues.sources[_design_of(revision)]
    assert design.applies_from is not None and design.applies_to is not None
    assert design.applies_from <= date(year, 1, 1) and date(year, 12, 31) <= design.applies_to
    for approval in revision.orden_aplicabilidad:
        governing = catalogues.legal[approval]
        if governing.governs_periods_from is not None:
            assert governing.governs_periods_from <= date(year, 1, 1)
            assert governing.governs_periods_to is None or date(year, 12, 31) <= governing.governs_periods_to


@pytest.mark.parametrize("year", _years_with_a_design())
def test_a_year_builds_an_applicability_snapshot_citing_only_sources_in_force(year: int) -> None:
    """A member inherited from another edition must not carry that edition's year-bound sources."""
    modelo, catalogues = _modelo()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=year,
        period="0A",
        grade=RegistryAuthorityGrade.APPLICABILITY,
    )
    assert str(snapshot.revision.id) == str(_selected(year).id)


@pytest.mark.parametrize("year", _years_with_a_design())
def test_an_edition_without_formulas_claims_no_more_than_applicability(year: int) -> None:
    revision = _selected(year)
    if not revision.formulas:
        assert revision.effective_authority_grade is RegistryAuthorityGrade.APPLICABILITY


@pytest.mark.parametrize("year", _years_with_a_design())
def test_an_applicability_year_refuses_a_calculation_snapshot(year: int) -> None:
    """A year answered by an applicability edition fails closed rather than borrowing a later edition's engine."""
    if _selected(year).effective_authority_grade is not RegistryAuthorityGrade.APPLICABILITY:
        return
    modelo, catalogues = _modelo()
    with pytest.raises(RegistryValidationError, match="applicability"):
        build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=year,
            period="0A",
            grade=RegistryAuthorityGrade.CALCULATION,
        )


@pytest.mark.parametrize("year", _years_with_a_design())
def test_an_authored_year_states_its_own_lis_124_window(year: int) -> None:
    """LIS art. 124.1: 25 dias naturales after the six months following a calendar-year period."""
    (window,) = [window for window in _selected(year).deadline_windows if window.filing_year == year]
    assert window.opens_on == date(year + 1, 7, 1)
    assert window.closes_on == date(year + 1, 7, 25)


def test_the_storage_chain_is_rooted_at_the_support_floor() -> None:
    modelo, _ = _modelo()
    roots = [revision for revision in ordered_revisions(modelo) if revision.casilla_storage_baseline is None]
    assert [str(root.id) for root in roots] == [str(_selected(_support().floor).id)]


def _caption_evolution_covers(
    modelo: ModeloDefinition, earlier: ModeloRevision, later: ModeloRevision, casilla_id: str
) -> bool:
    """Connect actual design captions only through grounded label changes."""
    _, catalogues = _modelo()
    occurrences = {
        str(revision.id): (revision, casilla)
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        if str(casilla.id) == casilla_id
    }
    captions = {
        rid: _printed_with(_design_of(revision), casilla.segmento, str(casilla.number))
        for rid, (revision, casilla) in occurrences.items()
    }
    links: dict[str, set[str]] = {rid: set() for rid in occurrences}
    for left, (_, left_row) in occurrences.items():
        for right, (_, right_row) in occurrences.items():
            if left_row.continuidad_id == right_row.continuidad_id and captions[left] & captions[right]:
                links[left].add(right)
    for revision in modelo.revisions.values():
        for evolution in revision.casilla_continuidad_evolutions:
            left, right = str(evolution.from_revision), str(evolution.to_revision)
            if left not in occurrences or right not in occurrences:
                continue
            if evolution.evolution_kind not in (
                CasillaEvolutionKind.LABEL_EVOLVED,
                CasillaEvolutionKind.LABEL_AND_LEGAL_REFS_EVOLVED,
            ):
                continue
            if not evolution.legal_refs or any(ref not in catalogues.legal for ref in evolution.legal_refs):
                continue
            if any(
                row.continuidad_id != evolution.continuidad_id
                or not captions[rid]
                or _design_of(edition) not in evolution.source_refs
                for rid in (left, right)
                for edition, row in (occurrences[rid],)
            ):
                continue
            links[left].add(right)
            links[right].add(left)
    pending = [str(earlier.id)]
    reached: set[str] = set()
    while pending:
        node = pending.pop()
        if node not in reached:
            reached.add(node)
            pending.extend(links[node] - reached)
    return str(later.id) in reached


def test_a_carried_row_keeps_its_caption_or_has_grounded_label_evolution() -> None:
    """Storage reuse preserves the printed concept; real caption changes require evidence."""
    modelo, _ = _modelo()
    checked = 0
    for earlier, later in _storage_pairs():
        if earlier.effective_authority_grade is not RegistryAuthorityGrade.APPLICABILITY:
            continue
        earlier_rows = {str(casilla.id): casilla for casilla in earlier.casillas}
        for casilla in later.casillas:
            if str(casilla.id) not in earlier_rows or not _NUMBERED.fullmatch(str(casilla.number)):
                continue
            shared = _printed_with(_design_of(earlier), casilla.segmento, str(casilla.number)) & _printed_with(
                _design_of(later), casilla.segmento, str(casilla.number)
            )
            assert shared or _caption_evolution_covers(modelo, earlier, later, str(casilla.id)), (
                f"{later.id} carries {casilla.id} from {earlier.id} "
                "without a shared caption or grounded label evolution"
            )
            checked += 1
    assert checked, "no applicability edition hands rows on, so this check proves nothing"


@pytest.mark.parametrize("defect", ("missing", "wrong_kind", "missing_endpoint_source"))
def test_a_changed_caption_cannot_be_carried_without_its_label_evidence(defect: str) -> None:
    modelo, _ = _modelo()
    earlier, later, row = next(
        (earlier, later, row)
        for earlier, later in _storage_pairs()
        for row in later.casillas
        if any(old.id == row.id for old in earlier.casillas)
        and not (
            _printed_with(_design_of(earlier), row.segmento, str(row.number))
            & _printed_with(_design_of(later), row.segmento, str(row.number))
        )
        and _caption_evolution_covers(modelo, earlier, later, str(row.id))
    )
    revisions = {}
    for rid, revision in modelo.revisions.items():
        evolutions = []
        for evolution in revision.casilla_continuidad_evolutions:
            if evolution.continuidad_id == row.continuidad_id:
                if defect == "missing":
                    continue
                update = (
                    {"evolution_kind": CasillaEvolutionKind.LEGAL_REFS_EVOLVED}
                    if defect == "wrong_kind"
                    else {"source_refs": ()}
                )
                evolution = evolution.model_copy(update=update)
            evolutions.append(evolution)
        revisions[rid] = revision.model_copy(update={"casilla_continuidad_evolutions": tuple(evolutions)})
    broken = modelo.model_copy(update={"revisions": revisions})
    assert not _caption_evolution_covers(broken, earlier, later, str(row.id))


def test_a_row_new_in_an_edition_says_why_citing_the_previous_design() -> None:
    for earlier, later in _storage_pairs():
        carried = {casilla.continuidad_id for casilla in earlier.casillas}
        for casilla in later.casillas:
            if casilla.continuidad_id in carried or casilla.inherited_from is not None:
                continue
            assert casilla.continuidad_origin in _ABSENCE, (later.id, casilla.id, casilla.continuidad_origin)
            assert casilla.continuidad_evidence is not None
            assert _design_of(earlier) in casilla.continuidad_evidence, (later.id, casilla.id)
