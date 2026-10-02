"""Following the declared predecessor's layout where a revision has no record design of its own.

An edition the AEAT has published only as a form, with no diseño de registro
yet, would otherwise fall to the numbered-boxes page and lose the form's pages
and apartados. Its declared predecessor's layout states that structure, read
from the predecessor's own design, and the edition's own form proves how much
of it still holds. A casilla keeps its predecessor's page and section only when:

* it continues across the declared edge: the same continuity key the
  stability gate compares, and the same printed box, which is its own declared
  number (a box the predecessor joined to it through an export field is a fact
  of that export layout);
* the predecessor shows it in a field or a grid cell, not as a design constant
  or a column of an export-record repeating group, which are facts of the
  predecessor's export layout;
* a form the revision cites prints the predecessor's page label on exactly one
  page, and that page prints the box; and
* when the predecessor's section heading opens with an apartado ordinal, that
  page prints the apartado.

Nothing the edition's form cannot prove is carried: binding inputs print no
box, an alias stands only where the form prints the box again, page conditions
are export facts of the predecessor and fall back to ``always``, and every
casilla failing a condition falls through to the numbered-boxes page. The
headings are the predecessor's design words under the same heading keys, so
the layout pins the predecessor's design sources beside the revision's form.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormAliasPosition,
    FormBlockDefinition,
    FormCell,
    FormCellKind,
    FormDesignSource,
    FormFieldBlock,
    FormGridBlock,
    FormGridRow,
    FormLayoutDefinition,
    FormPageCondition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormSectionDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .official_form_pages import OfficialFormPages, PrintedPage, apartado_ordinal, read_official_form_pages
from .stability import continuity_keys

__all__ = ["ContinuedLayout", "PredecessorLayout", "continue_predecessor_layout"]


@dataclass(frozen=True, slots=True)
class PredecessorLayout:
    """A revision's declared predecessor together with the layout it currently declares."""

    revision: ModeloRevision
    layout: FormLayoutDefinition


@dataclass(frozen=True, slots=True)
class ContinuedLayout:
    """The predecessor's pages a revision's own form confirms, holding only the confirmed casillas.

    ``unconfirmed`` names the continuing casillas the predecessor shows on its
    form that this layout does not continue -- the box is not their own, or the
    revision's form does not confirm it; they fall through the ladder.
    """

    pages: tuple[FormPageDefinition, ...]
    aliases: Mapping[str, tuple[FormAliasPosition, ...]]
    design_sources: tuple[FormDesignSource, ...]
    unconfirmed: frozenset[str]


def _one_to_one(keys: Mapping[str, str]) -> dict[str, str]:
    """Map each continuity key held by exactly one casilla to that casilla."""
    counts = Counter(keys.values())
    return {key: casilla_id for casilla_id, key in keys.items() if counts[key] == 1}


def _printed_box(casilla: CasillaDefinition) -> str | None:
    if casilla.number.isdigit():
        return casilla.number
    return casilla.form_number if casilla.form_number is not None and casilla.form_number.isdigit() else None


@dataclass(slots=True)
class _Continuation:
    """The state of following one predecessor layout for one revision."""

    revision: ModeloRevision
    predecessor: PredecessorLayout
    form: OfficialFormPages
    labels: frozenset[str]
    successor_of: dict[str, str] = field(default_factory=dict)
    casillas: dict[str, CasillaDefinition] = field(default_factory=dict)
    placements: dict[str, FormPlacementDefinition] = field(default_factory=dict)
    printed: dict[str, PrintedPage | None] = field(default_factory=dict)
    unconfirmed: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        mine = _one_to_one(continuity_keys(self.revision))
        theirs = _one_to_one(continuity_keys(self.predecessor.revision))
        self.successor_of = {theirs[key]: mine[key] for key in mine.keys() & theirs.keys()}
        self.casillas = {casilla.id: casilla for casilla in self.revision.casillas}
        self.placements = {placement.casilla_id: placement for placement in self.predecessor.layout.placements}

    def page(self, label: str | None) -> PrintedPage | None:
        """Return the one page of the revision's form printing the predecessor's page label."""
        if label is None:
            return None
        if label not in self.printed:
            self.printed[label] = self.form.page_labelled(label, labels=self.labels)
        return self.printed[label]

    def continuing(self, casilla_id: str) -> tuple[str, str] | None:
        """Return the revision's casilla and printed box continuing a predecessor on-form casilla."""
        successor = self.successor_of.get(casilla_id)
        placement = self.placements.get(casilla_id)
        if successor is None or placement is None or placement.kind is not FormPlacementKind.ON_FORM:
            return None
        box = placement.box_number
        if box is None or _printed_box(self.casillas[successor]) != box:
            return None
        return successor, box

    def confirmed(self, casilla_id: str, page: PrintedPage | None) -> str | None:
        """Return the revision's casilla when its form prints the continuing box on ``page``.

        A continuing casilla the predecessor shows under a box that is not its
        own declared number took that box from the predecessor's export field,
        so it is refused like one the form does not print.
        """
        continuing = self.continuing(casilla_id)
        if continuing is None:
            self.refuse([casilla_id])
            return None
        successor, box = continuing
        if page is None or not page.prints_box(box):
            self.unconfirmed.add(successor)
            return None
        return successor

    def refuse(self, casilla_ids: list[str]) -> None:
        """Record continuing casillas the predecessor shows in a part this layout does not continue."""
        for casilla_id in casilla_ids:
            successor = self.successor_of.get(casilla_id)
            placement = self.placements.get(casilla_id)
            if successor is not None and placement is not None and placement.kind is FormPlacementKind.ON_FORM:
                self.unconfirmed.add(successor)


def _block_casilla_ids(block: FormBlockDefinition) -> list[str]:
    if isinstance(block, FormFieldBlock):
        return [] if block.casilla_id is None else [block.casilla_id]
    if isinstance(block, FormGridBlock):
        return [cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id is not None]
    if isinstance(block, FormRepeatingGroupBlock):
        return [column.casilla_id for column in block.columns if column.casilla_id is not None]
    return []


def _continued_block(
    state: _Continuation, block: FormBlockDefinition, page: PrintedPage | None
) -> FormBlockDefinition | None:
    """Return the block holding only the casillas the revision's form confirms, or ``None``."""
    if isinstance(block, FormFieldBlock):
        if block.casilla_id is None:
            return None
        if block.design_constant is not None:
            state.refuse([block.casilla_id])
            return None
        successor = state.confirmed(block.casilla_id, page)
        return None if successor is None else block.model_copy(update={"casilla_id": successor})
    if isinstance(block, FormGridBlock):
        rows: list[FormGridRow] = []
        for row in block.rows:
            cells = tuple(_continued_cell(state, cell, page) for cell in row.cells)
            if any(cell.kind is not FormCellKind.BLANK for cell in cells):
                rows.append(row.model_copy(update={"cells": cells}))
        return block.model_copy(update={"rows": tuple(rows)}) if rows else None
    state.refuse(_block_casilla_ids(block))
    return None


def _continued_cell(state: _Continuation, cell: FormCell, page: PrintedPage | None) -> FormCell:
    blank = FormCell(kind=FormCellKind.BLANK)
    if cell.kind is FormCellKind.DESIGN_CONSTANT and cell.casilla_id is not None:
        state.refuse([cell.casilla_id])
        return blank
    if cell.kind is not FormCellKind.CASILLA or cell.casilla_id is None:
        return blank
    successor = state.confirmed(cell.casilla_id, page)
    return blank if successor is None else FormCell(kind=FormCellKind.CASILLA, casilla_id=successor)


def _continued_section(
    state: _Continuation, section: FormSectionDefinition, page: PrintedPage | None
) -> FormSectionDefinition | None:
    ordinal = apartado_ordinal(section.official_heading)
    if page is None or (ordinal is not None and not page.prints_apartado(ordinal)):
        state.refuse([casilla_id for block in section.blocks for casilla_id in _block_casilla_ids(block)])
        return None
    blocks = tuple(
        continued for block in section.blocks if (continued := _continued_block(state, block, page)) is not None
    )
    return section.model_copy(update={"blocks": blocks}) if blocks else None


def _continued_aliases(
    state: _Continuation, pages: tuple[FormPageDefinition, ...]
) -> dict[str, tuple[FormAliasPosition, ...]]:
    """Keep each alias whose page and section continue and whose page the form shows printing the box again."""
    sections = {(page.id, section.id) for page in pages for section in page.sections}
    shown = {
        casilla_id
        for page in pages
        for section in page.sections
        for block in section.blocks
        for casilla_id in _block_casilla_ids(block)
    }
    aliases: dict[str, tuple[FormAliasPosition, ...]] = {}
    for casilla_id, placement in state.placements.items():
        continuing = state.continuing(casilla_id)
        if continuing is None or continuing[0] not in shown or not placement.aliases:
            continue
        successor, box = continuing
        kept = tuple(
            alias
            for alias in placement.aliases
            if (alias.page_id, alias.section_id) in sections
            and (printed := state.page(alias.official_ref)) is not None
            and printed.prints_box(box)
        )
        if kept:
            aliases[successor] = kept
    return aliases


def continue_predecessor_layout(
    revision: ModeloRevision,
    predecessor: PredecessorLayout,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> ContinuedLayout | None:
    """Return the predecessor's pages the revision's own form confirms, or ``None`` when it confirms none.

    Raises:
        OfficialFormUnavailableError: When a form the revision cites cannot be
            trusted (missing, re-hashed, or with stale extracted text).
    """
    form = read_official_form_pages(revision.source_refs, sources, data_root)
    if not form.pages:
        return None
    labels = frozenset(page.official_ref for page in predecessor.layout.pages if page.official_ref is not None)
    state = _Continuation(revision=revision, predecessor=predecessor, form=form, labels=labels)
    pages: list[FormPageDefinition] = []
    for page in predecessor.layout.pages:
        printed = state.page(page.official_ref)
        sections = tuple(
            continued
            for section in page.sections
            if (continued := _continued_section(state, section, printed)) is not None
        )
        if sections:
            pages.append(
                page.model_copy(
                    update={
                        "sections": sections,
                        "condition": FormPageCondition.ALWAYS,
                        "condition_casilla_id": None,
                        "condition_periods": (),
                    }
                )
            )
    if not pages:
        return None
    continued = tuple(pages)
    design_sources: dict[str, FormDesignSource] = {}
    for item in (*predecessor.layout.design_sources, *form.pins):
        design_sources.setdefault(item.source_ref, item)
    return ContinuedLayout(
        pages=continued,
        aliases=_continued_aliases(state, continued),
        design_sources=tuple(design_sources.values()),
        unconfirmed=frozenset(state.unconfirmed),
    )
