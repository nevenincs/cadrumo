"""Assemble generated form pages, placements, and operator-input surfaces."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.schema_exports import (
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormPageCondition,
    FormPageDefinition,
    FormSectionDefinition,
)

from .generation_constants import _INPUTS_PAGE, _NUMBERED_PAGE
from .generation_models import _Build, _RowDraft, _SectionDraft
from .official_text import node_slug
from .page_fallbacks import _inputs_page, _numbered_casillas, _numbered_page
from .page_placement import _block_bindings, _block_casillas
from .page_sections import (
    _heading_key,
    _page_sections,
    _row_drafts,
    _section_blocks,
    _section_slug,
    _signature,
    _unique,
)
from .predecessor_layout import ContinuedLayout


@dataclass(slots=True)
class _PageBuildState:
    build: _Build
    manual_bindings: Mapping[str, bool]
    repeating: Mapping[str, ExportRecordDefinition]
    pages: list[FormPageDefinition]
    section_of: dict[int, tuple[str, str]]
    placed_bindings: set[str]
    shown: set[str]
    emitted_repeating: set[str]
    used_pages: set[str]
    primary: dict[str, int]


def _page_condition(records: Iterable[ExportRecordDefinition]) -> tuple[FormPageCondition, str | None]:
    """Return the page condition the page's export records structurally declare."""
    listed = list(records)
    gated = sorted({record.requires_positive_casilla_id for record in listed if record.requires_positive_casilla_id})
    if len(gated) == 1 and all(record.requires_positive_casilla_id for record in listed):
        return FormPageCondition.REQUIRES_POSITIVE_CASILLA, gated[0]
    if listed and all(not record.required for record in listed):
        return FormPageCondition.OPTIONAL_RECORD, None
    return FormPageCondition.ALWAYS, None


def _continued_pages(continued: ContinuedLayout | None) -> list[FormPageDefinition]:
    return [] if continued is None else list(continued.pages)


def _continued_casillas(continued: ContinuedLayout | None) -> set[str]:
    if continued is None:
        return set()
    return _block_casillas(block for page in continued.pages for section in page.sections for block in section.blocks)


def _position_indexes(build: _Build) -> tuple[dict[str, list[int]], dict[str, str | None]]:
    pages: dict[str, list[int]] = {}
    refs: dict[str, str | None] = {}
    for index, position in enumerate(build.positions):
        pages.setdefault(position.page_key, []).append(index)
        refs.setdefault(position.page_key, position.page_ref)
    return pages, refs


def _page_signatures(build: _Build, drafts: Sequence[_SectionDraft]) -> Counter[tuple[str, ...]]:
    entries = (entry for draft in drafts for entry in _row_drafts(build, draft.items))
    return Counter(_signature(entry.columns) for entry in entries if isinstance(entry, _RowDraft))


def _section_for_page(
    state: _PageBuildState,
    draft: _SectionDraft,
    *,
    page_id: str,
    signatures: Counter[tuple[str, ...]],
    used_sections: set[str],
) -> FormSectionDefinition | None:
    section_id = _unique(node_slug(draft.heading) if draft.heading else _section_slug(draft.key), used_sections)
    blocks = _section_blocks(
        state.build,
        draft,
        page_signatures=signatures,
        repeating=state.repeating,
        emitted_repeating=state.emitted_repeating,
    )
    if not blocks:
        used_sections.discard(section_id)
        return None
    for index in draft.positions:
        state.section_of[index] = (page_id, section_id)
    state.shown.update(_block_casillas(blocks))
    state.placed_bindings.update(_block_bindings(blocks))
    heading = node_slug(draft.heading) if draft.heading else section_id
    return FormSectionDefinition(
        id=section_id,
        heading_key=_heading_key(state.build.modelo_id, "section", heading),
        official_heading=draft.heading,
        blocks=tuple(blocks),
    )


def _sections_for_page(
    state: _PageBuildState,
    drafts: Sequence[_SectionDraft],
    *,
    page_id: str,
    signatures: Counter[tuple[str, ...]],
    used_sections: set[str],
) -> list[FormSectionDefinition]:
    sections: list[FormSectionDefinition] = []
    for draft in drafts:
        section = _section_for_page(
            state,
            draft,
            page_id=page_id,
            signatures=signatures,
            used_sections=used_sections,
        )
        if section is not None:
            sections.append(section)
    return sections


def _records_on_page(build: _Build, indexes: Sequence[int]) -> dict[str, ExportRecordDefinition]:
    return {record_id: record for index in indexes for record_id, record in build.positions[index].records.items()}


def _append_source_page(
    state: _PageBuildState,
    page_key: str,
    indexes: Sequence[int],
    official_ref: str | None,
) -> None:
    drafts = _page_sections(state.build, indexes, state.primary)
    signatures = _page_signatures(state.build, drafts)
    page_id = _unique(page_key, state.used_pages)
    sections = _sections_for_page(
        state,
        drafts,
        page_id=page_id,
        signatures=signatures,
        used_sections=set(),
    )
    if not sections:
        state.used_pages.discard(page_id)
        return
    condition, gate = _page_condition(_records_on_page(state.build, indexes).values())
    state.pages.append(
        FormPageDefinition(
            id=page_id,
            official_ref=official_ref,
            heading_key=_heading_key(state.build.modelo_id, "page", page_id),
            condition=condition,
            condition_casilla_id=gate,
            sections=tuple(sections),
        )
    )


def _append_source_pages(
    state: _PageBuildState,
    pages: Mapping[str, Sequence[int]],
    refs: Mapping[str, str | None],
) -> None:
    for page_key, indexes in pages.items():
        _append_source_page(state, page_key, indexes, refs[page_key])


def _mark_repeating_bindings(state: _PageBuildState) -> None:
    state.placed_bindings.update(
        binding_id
        for position in state.build.positions
        if any(record_id in state.repeating for record_id in position.records)
        for binding_id in position.binding_ids
    )


def _append_numbered_page(state: _PageBuildState) -> None:
    numbered = [
        casilla_id for casilla_id in _numbered_casillas(state.build, state.primary) if casilla_id not in state.shown
    ]
    if not numbered:
        return
    page_id = _unique(_NUMBERED_PAGE, state.used_pages)
    state.pages.append(_numbered_page(state.build, page_id, numbered))
    state.shown.update(numbered)


def _append_inputs_page(state: _PageBuildState) -> None:
    page_id = _unique(_INPUTS_PAGE, state.used_pages)
    page = _inputs_page(state.build, page_id, state.manual_bindings, state.placed_bindings)
    if page is not None:
        state.pages.append(page)


def _build_pages(
    build: _Build,
    manual_bindings: Mapping[str, bool],
    repeating: Mapping[str, ExportRecordDefinition],
    continued: ContinuedLayout | None,
) -> tuple[list[FormPageDefinition], dict[int, tuple[str, str]], set[str], set[str]]:
    pages, refs = _position_indexes(build)
    continued_pages = _continued_pages(continued)
    state = _PageBuildState(
        build=build,
        manual_bindings=manual_bindings,
        repeating=repeating,
        pages=continued_pages,
        section_of={},
        placed_bindings=set(),
        shown=_continued_casillas(continued),
        emitted_repeating=set(),
        used_pages={page.id for page in continued_pages},
        primary={casilla_id: anchors[0] for casilla_id, anchors in build.anchors.items()},
    )
    _append_source_pages(state, pages, refs)
    _mark_repeating_bindings(state)
    _append_numbered_page(state)
    _append_inputs_page(state)
    return state.pages, state.section_of, state.shown, state.placed_bindings
