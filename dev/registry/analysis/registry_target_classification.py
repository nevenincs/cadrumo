"""Registry-declared classification of generated-tree targets that are not gaps to author."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector, SourceReference
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision_for_year

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..compiler.validate_export_exemption import modelo_publishes_a_record_design

#: Reason tokens opening the detail of a ``not-applicable`` target.
INAPPLICABLE_BELOW_FLOOR: Final = "below_supported_floor"
INAPPLICABLE_NO_RECORD_DESIGN: Final = "no_published_record_design"


def classify_inapplicable_target(
    modelo: ModeloDefinition,
    revision_id: str,
    sources: Mapping[str, SourceReference],
    *,
    floor: int,
    has_committed_tree: bool,
) -> str | None:
    """Name why the registry itself places a revision outside every generated export tree.

    A generated tree is reproduced from an official record design for a filing
    year the product supports. Two registry facts remove that expectation and
    neither is a defect of the revision: every filing year it declares lies below
    the supported floor (refused at every grade), or no source of its modelo is a
    record design, so there is nothing to render from. Any other revision stays
    unreadable, because a design is published and the years are supported, so a
    missing tree is a gap to author.

    A revision that already ships a tree is never placed here: it was expected to
    render, and a failure to do so must stay visible.

    Returns the reason detail (opening with its reason token), or ``None``.
    """
    if has_committed_tree:
        return None
    years = declared_revision_filing_years(modelo, revision_id)
    if years and max(years) < floor:
        return (
            f"{INAPPLICABLE_BELOW_FLOOR}: every filing year the revision declares (through {max(years)}) "
            f"lies below the supported filing-years floor {floor}"
        )
    if not modelo_publishes_a_record_design(modelo, sources):
        return (
            f"{INAPPLICABLE_NO_RECORD_DESIGN}: no source of modelo {modelo.id} is a record design, "
            "so no generated export tree can exist for it"
        )
    return None


#: Reason token opening the detail of a ``projected`` target.
PROJECTED_FROM_NEAREST_EDITION: Final = "projected_from"

#: The render refusal the compiler gives a revision none of whose cited sources covers its declared frame.
_NO_OWN_RECORD_DESIGN_MARKER: Final = "cites no record-design source"


def classify_projected_target(
    modelo: ModeloDefinition,
    revision_id: str,
    sources: Mapping[str, SourceReference],
    *,
    tree_revisions: frozenset[str],
    support: SupportedFilingYearsCatalogue,
    render_refusal: str = "",
) -> str | None:
    """Name the authored edition that serves a revision which has no record design of its own.

    A revision citing no record design has nothing to render a tree from. The
    registry answers such a year from the nearest authored edition, forward from
    the newest and backward from the oldest, through the canonical temporal
    resolver; the answer reaches calculation grade at most. The candidates are
    the editions that ship a generated tree, so the resolver is asked only about
    editions able to serve a layout. A revision that cites a record design covering its frame is a
    gap to author, and one already shipping a tree is not projected.

    Returns the reason detail (opening with its token and naming the source
    edition), or ``None`` when the revision is not a projection.
    """
    revision = modelo.revisions[revision_id]
    if revision_id in tree_revisions or _cites_own_record_design(revision, sources, render_refusal):
        return None
    candidates = {rid: edition for rid, edition in modelo.revisions.items() if str(rid) in tree_revisions}
    year = _representative_filing_year(revision.period_selector)
    if not candidates or year is None:
        return None
    return _nearest_edition_projection(modelo.model_copy(update={"revisions": candidates}), year, support)


def _cites_own_record_design(
    revision: ModeloRevision, sources: Mapping[str, SourceReference], render_refusal: str
) -> bool:
    """Whether the revision cites a record design that the compiler accepted as covering its frame."""
    if _NO_OWN_RECORD_DESIGN_MARKER in render_refusal:
        return False
    return any(
        (source := sources.get(ref)) is not None and source.kind is RegistrySourceKind.RECORD_DESIGN
        for ref in (*revision.source_refs, *(revision.casilla_source_refs or ()))
    )


def _nearest_edition_projection(
    candidates: ModeloDefinition, year: int, support: SupportedFilingYearsCatalogue
) -> str | None:
    """The projection reason for one filing year, or ``None`` when no candidate edition can serve it."""
    try:
        serving = select_revision_for_year(candidates, filing_year=year, support=support)
        resolution = revision_temporal_resolution(serving, filing_year=year, period=None, support=support)
    except RegistryError:
        return None
    return (
        f"{PROJECTED_FROM_NEAREST_EDITION}: {serving.id} ({resolution.projection_direction.value}) "
        f"for filing year {year}; calculation grade at most"
    )


def _representative_filing_year(selector: PeriodSelector) -> int | None:
    """The filing year a projection is asked for: the last year a bounded selector declares.

    The last year is the one nearest the supported envelope, so a span that
    begins below the floor is still answerable.
    """
    if selector.years:
        return max(selector.years)
    return selector.year_to if selector.year_to is not None else selector.year_from


def tree_bearing_revisions(registry_root: Path, modelo: ModeloDefinition) -> frozenset[str]:
    """The revisions of one modelo that ship a committed generated export tree."""
    modelo_root = registry_root / "modelos" / str(modelo.id) / "revisions"
    return frozenset(
        str(revision_id)
        for revision_id in modelo.revisions
        if (modelo_root / str(revision_id) / "export" / EXPORT_FRAGMENT_PROVENANCE_FILENAME).is_file()
    )


def declared_revision_filing_years(modelo: ModeloDefinition, revision_id: str) -> tuple[int, ...]:
    """The filing years a revision's selector declares, whether it lists them or spans a range.

    A selector declared with ``year_from``/``year_to`` lists no years, so its last
    declared year is the range's end; an open-ended range declares no last year.
    """
    selector = next(
        revision.period_selector
        for candidate_id, revision in modelo.revisions.items()
        if str(candidate_id) == revision_id
    )
    if selector.years:
        return tuple(selector.years)
    return (selector.year_to,) if selector.year_to is not None else ()
