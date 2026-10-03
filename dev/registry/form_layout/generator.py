"""The modelo-independent form layout generator: one seed ladder for every revision.

The generator reads official anchors in a fixed order and declares a
:class:`~cadrumo.domain.calculations.registry.schema_form_layouts.FormLayoutDefinition`
for one revision. It has no per-modelo code; every decision is taken from the
revision's own typed declarations and the official sources it cites.

The ladder, per casilla:

1. an export field of the revision's derived layout (record order, offset),
   joined to the record-design row at the same record and offset;
2. for an XML-dictionary revision, the dictionary line that names the casilla;
3. the design row whose description prints the casilla's box ``[NN]`` -- used
   only when exactly one row prints it and no other casilla already sits there,
   otherwise the casilla is declared unplaced as ambiguous;
4. for a revision with no design, export record or dictionary line of its own,
   the declared predecessor's position of the same continuing box, kept only
   where a form the revision cites prints that page's label, the box and its
   apartado on one page (:mod:`.predecessor_layout`);
5. the casilla's numeric box number alone, placed on a numbered-boxes page;
6. otherwise a working figure when the casilla is not operator-entered, or
   unplaced without an official anchor when it is.

Pages are the design's records (or the dictionary's element groups); sections
are the contiguous runs of rows sharing a heading path; grids are rows whose
columns match the shared column vocabulary or repeat on the page. Manual-input
bindings no casilla owns become binding inputs; row-set sources and repeating
export records become repeating groups, never flattened rows.

Where a design names a part in no form the ladder can read, a reviewer's quote
of the official words (``official_headings.toml``) heads it, after the quote is
verified on the cited line of a source the revision cites.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FORM_LAYOUT_GENERATOR_VERSION,
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormLayoutSeedSource,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ..compiler.form_layout_integrity import form_layout_source_digest
from .generation_models import _Build
from .heading_quotes import _quoted_pages
from .official_form_pages import OfficialFormUnavailableError
from .official_headings import QuotedHeading, read_official_headings
from .page_assembly import _build_pages
from .page_placement import _placements
from .position_anchoring import (
    _anchor_casillas,
    _anchor_row_fields,
    _binding_primary,
    _dictionary_positions,
    _fixed_width_records,
    _manual_scalar_bindings,
)
from .predecessor_layout import ContinuedLayout, PredecessorLayout, continue_predecessor_layout
from .record_design_anchoring import _record_design_positions

__all__ = [
    "GENERATED_LAYOUT_ID",
    "LayoutGeneration",
    "generate_modelo_layouts",
    "generate_revision_layout",
]

GENERATED_LAYOUT_ID: Final[str] = "form-layout"


@dataclass(frozen=True, slots=True)
class LayoutGeneration:
    """One revision's generation outcome: a layout, or the reason there is none."""

    modelo_id: str
    revision_id: str
    layout: FormLayoutDefinition | None
    failure: str | None = None
    notes: tuple[str, ...] = ()


def _seed_source(build: _Build, continued: ContinuedLayout | None) -> FormLayoutSeedSource:
    if build.used_dictionary:
        return FormLayoutSeedSource.XML_DICTIONARY
    if build.used_design and build.used_export:
        return FormLayoutSeedSource.EXPORT_RECORD_DESIGN
    if build.used_design:
        return FormLayoutSeedSource.DESIGN_BOX_NUMBER
    if continued is not None:
        return FormLayoutSeedSource.PREDECESSOR_LAYOUT
    return FormLayoutSeedSource.CASILLA_NUMBER


def _has_own_layout_seed(build: _Build) -> bool:
    return bool(build.positions) or build.used_design or build.used_dictionary


def _follow_predecessor_layout(
    build: _Build,
    predecessor: PredecessorLayout,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> ContinuedLayout | None:
    try:
        continued = continue_predecessor_layout(build.revision, predecessor, sources=sources, data_root=data_root)
    except OfficialFormUnavailableError as error:
        build.notes.append(f"official form unavailable: {error}")
        return None
    if continued is None:
        build.notes.append(f"no form the revision cites confirms a page of predecessor {predecessor.revision.id}")
        return None
    if continued.unconfirmed:
        _note_unconfirmed_casillas(build, continued)
    _pin_continued_sources(build, continued)
    return continued


def _note_unconfirmed_casillas(build: _Build, continued: ContinuedLayout) -> None:
    build.notes.append(
        f"{len(continued.unconfirmed)} continuing casilla(s) not confirmed on the revision's own form: "
        + ", ".join(sorted(continued.unconfirmed))
    )


def _pin_continued_sources(build: _Build, continued: ContinuedLayout) -> None:
    pinned = {item.source_ref for item in build.design_sources}
    build.design_sources.extend(item for item in continued.design_sources if item.source_ref not in pinned)


def _continued_layout(
    build: _Build,
    predecessor: PredecessorLayout | None,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> ContinuedLayout | None:
    """Follow the predecessor only for a revision whose own anchors give no official position."""
    if predecessor is None or _has_own_layout_seed(build):
        return None
    return _follow_predecessor_layout(build, predecessor, sources=sources, data_root=data_root)


def _revision_position_inputs(
    revision: ModeloRevision,
) -> tuple[ExportLayoutDefinition | None, list[ExportRecordDefinition], dict[str, bool]]:
    layouts = derive_export_layouts_from_bindings(revision)
    manual_bindings = _manual_scalar_bindings(revision)
    xml_layout = next((layout for layout in layouts if layout.format is ExportLayoutFormat.XML_DICTIONARY), None)
    records = _fixed_width_records(layouts)
    return xml_layout, records, manual_bindings


def _seed_revision_positions(
    build: _Build,
    xml_layout: ExportLayoutDefinition | None,
    records: Sequence[ExportRecordDefinition],
    manual_bindings: Mapping[str, bool],
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> None:
    if xml_layout is not None and xml_layout.dictionary_source_ref is not None:
        _dictionary_positions(build, xml_layout, sources, data_root)
    else:
        _record_design_positions(build, sources, records, manual_bindings)
    _anchor_row_fields(build, records)
    build.used_export = any(position.records for position in build.positions)
    _anchor_casillas(build)
    build.binding_primary = _binding_primary(build)


def _headings_for_revision(
    modelo_id: str, revision: ModeloRevision, headings: Sequence[QuotedHeading] | None
) -> Sequence[QuotedHeading]:
    return read_official_headings().for_revision(modelo_id, str(revision.id)) if headings is None else headings


def generate_revision_layout(
    modelo_id: str,
    revision: ModeloRevision,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
    headings: Sequence[QuotedHeading] | None = None,
    predecessor: PredecessorLayout | None = None,
) -> LayoutGeneration:
    """Generate one revision's layout through the seed ladder.

    A revision declaring no casillas has no form to lay out and returns no
    layout with its reason, which coverage reports as undeclared. ``headings``
    replaces the reviewer's recorded quotes for this revision; by default they
    are read from ``official_headings.toml``. ``predecessor`` is the declared
    predecessor with its current layout; it is followed only when the revision
    has no official position of its own, never in place of its own design.

    Raises:
        OfficialHeadingRefusedError: When a quoted heading is not grounded on
            its cited line, or names a part the layout does not have.
    """
    if not revision.casillas:
        return LayoutGeneration(modelo_id, revision.id, None, failure="revision declares no casillas")
    build = _Build(modelo_id=modelo_id, revision=revision)
    xml_layout, records, manual_bindings = _revision_position_inputs(revision)
    _seed_revision_positions(
        build,
        xml_layout,
        records,
        manual_bindings,
        sources=sources,
        data_root=data_root,
    )
    repeating = {record.id: record for record in records if record.repeat is not None}
    continued = _continued_layout(build, predecessor, sources=sources, data_root=data_root)
    pages, section_of, shown, _placed_bindings = _build_pages(build, manual_bindings, repeating, continued)
    quotes = _headings_for_revision(modelo_id, revision, headings)
    pages = _quoted_pages(build, pages, quotes, sources=sources, data_root=data_root)
    layout = FormLayoutDefinition(
        id=GENERATED_LAYOUT_ID,
        revision_id=revision.id,
        seed_source=_seed_source(build, continued),
        generator_version=FORM_LAYOUT_GENERATOR_VERSION,
        source_state_digest=form_layout_source_digest(revision),
        design_sources=tuple(build.design_sources),
        pages=tuple(pages),
        placements=_placements(build, section_of, shown, {} if continued is None else continued.aliases),
    )
    return LayoutGeneration(modelo_id, revision.id, layout, notes=tuple(build.notes))


def generate_modelo_layouts(
    modelo: ModeloDefinition,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> dict[str, LayoutGeneration]:
    """Generate every revision of a modelo whose layout is not reviewed, each after its declared predecessor.

    A revision may follow its predecessor's layout, so the predecessor is
    generated first and its fresh layout is the one followed; a reviewed
    layout is never regenerated and is followed as declared.
    """
    outcomes: dict[str, LayoutGeneration] = {}

    def current(revision_id: str, visiting: frozenset[str]) -> FormLayoutDefinition | None:
        revision = modelo.revisions[revision_id]
        existing = revision.form_layouts[0] if revision.form_layouts else None
        if existing is not None and existing.review.state is FormLayoutReviewState.REVIEWED:
            return existing
        if revision_id not in outcomes:
            followed: PredecessorLayout | None = None
            declared = revision.predecessor
            if (
                isinstance(declared, DeclaredPredecessor)
                and declared.revision_id in modelo.revisions
                and declared.revision_id not in visiting
            ):
                layout = current(declared.revision_id, visiting | {revision_id})
                if layout is not None:
                    followed = PredecessorLayout(revision=modelo.revisions[declared.revision_id], layout=layout)
            outcomes[revision_id] = generate_revision_layout(
                str(modelo.id), revision, sources=sources, data_root=data_root, predecessor=followed
            )
        return outcomes[revision_id].layout

    for revision_id in sorted(modelo.revisions, key=str):
        current(revision_id, frozenset())
    return {
        revision_id: outcomes[revision_id]
        for revision_id in sorted(modelo.revisions, key=str)
        if revision_id in outcomes
    }
