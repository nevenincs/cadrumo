"""Turn one page of the editor form into the lines of the casilla list.

A section becomes a heading that says whether anything in it still needs the
filer; an official grid becomes its printed rows, each row's cells listed under
the row heading with the column heading as their label; a value the official
design fixes becomes an informational line, never an editable field. The
working figures and the unplaced casillas are one more page, so nothing the
form holds is out of the filer's reach.

Filters narrow a page without changing it: showing only what needs attention,
or only the filer's own values, keeps the headings of the sections that still
have lines.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .....application.modelo.work_form_models import (
    ModeloFormBindingInputsBlock,
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridRow,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from .....core.i18n.render import tr
from .casilla_list import (
    AddressKey,
    CasillaListEntry,
    CasillaListHeading,
    CasillaListItem,
    CasillaListNote,
)
from .vocabulary import BLOCKS_MARK, CONFIRM_MARK, DONE_MARK, MISSING_MARK, NEEDS_ATTENTION, WorkbenchMark

DETAILS_PAGE_ID: Final[str] = "details"
_RATIO_DATA_TYPE: Final[str] = "ratio"
_COUNTED_TO_DO: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.NEEDS_INPUT, ModeloFormOrigin.DEFAULT_TO_CONFIRM}
)
"""Origins a section's counts tally as still to do; the counts, not the bare origins, say how many."""
_DESIGN_CONSTANT_KEY: Final[str] = "tui.modelo.workbench.design_constant"


class WorkbenchFilter(StrEnum):
    """Which fields a page shows."""

    ALL = "all"
    ATTENTION = "attention"
    MINE = "mine"


@dataclass(frozen=True, slots=True)
class StagedDisplay:
    """How a staged change reads on its line: the new value and the value it replaces."""

    text: str
    previous_text: str


@dataclass(frozen=True, slots=True)
class WorkbenchPage:
    """One page of the workbench: an official page, or the calculation details."""

    id: str
    heading: ModeloFormText
    sections: tuple[ModeloFormSection, ...]
    details: tuple[ModeloFormField, ...] = ()
    #: The declaration is recorded as filed, so nothing on it is left to enter or confirm.
    recorded: bool = False

    def fields(self) -> tuple[ModeloFormField, ...]:
        """Every field the page holds, in reading order."""
        collected = [field for section in self.sections for field in section_fields(section)]
        collected.extend(self.details)
        return tuple(collected)


def workbench_pages(form: ModeloWorkForm) -> tuple[WorkbenchPage, ...]:
    """Return the form's pages, followed by the calculation details when it has any."""
    recorded = form.filing is not None
    pages = [
        WorkbenchPage(id=page.id, heading=page.heading, sections=page.sections, recorded=recorded)
        for page in form.pages
    ]
    details = (*form.working_figures, *(item.field for item in form.unplaced))
    if details:
        pages.append(
            WorkbenchPage(
                id=DETAILS_PAGE_ID,
                heading=ModeloFormText(
                    text=tr("tui.modelo.workbench.details_page"), disclosure=ModeloFormTextDisclosure.LOCALIZED
                ),
                sections=(),
                details=details,
                recorded=recorded,
            )
        )
    return tuple(pages)


def _to_do(field: ModeloFormField, counts: ModeloFormCounts | None, *, recorded: bool) -> bool:
    """Whether a field still needs the filer.

    Nothing on a declaration recorded as filed does, whatever origin its boxes
    keep. Otherwise a missing or assumed value counts only while its section's
    counts still tally one; a field outside any section has no counts, so its
    origin decides.
    """
    if recorded:
        return False
    if field.blockers:
        return True
    if field.origin in _COUNTED_TO_DO:
        if counts is None:
            return True
        tally = counts.needs_input if field.origin is ModeloFormOrigin.NEEDS_INPUT else counts.default_to_confirm
        return tally > 0
    return field.origin in NEEDS_ATTENTION


def _shown(
    field: ModeloFormField,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter,
    counts: ModeloFormCounts | None = None,
    *,
    recorded: bool = False,
) -> bool:
    if mode is WorkbenchFilter.ALL:
        return True
    key = address_key(field.address)
    if mode is WorkbenchFilter.ATTENTION:
        return key in staged or _to_do(field, counts, recorded=recorded)
    return key in staged or field.origin in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}


def _entry(
    field: ModeloFormField,
    staged: Mapping[AddressKey, StagedDisplay],
    *,
    indent: int = 0,
    label: str | None = None,
    rate_of_row: bool = False,
    recorded: bool = False,
) -> CasillaListEntry:
    change = staged.get(address_key(field.address))
    return CasillaListEntry(
        field=field,
        indent=indent,
        label=label,
        staged_text=None if change is None else change.text,
        previous_text=None if change is None else change.previous_text,
        rate_of_row=rate_of_row,
        recorded=recorded,
    )


def _rate_box(row: ModeloFormGridRow) -> ModeloFormField | None:
    """The one rate box an official row prints, or ``None`` when it prints none or several."""
    rates = [cell.field for cell in row.cells if cell.field is not None and cell.field.data_type == _RATIO_DATA_TYPE]
    return rates[0] if len(rates) == 1 else None


def _pending(section: ModeloFormSection, *, recorded: bool = False) -> int:
    """How many of a section's fields still need the filer, taking missing and assumed values from its counts.

    Nothing on a declaration recorded as filed does.
    """
    if recorded:
        return 0
    counts = section.counts
    others = sum(
        1
        for field in section_fields(section)
        if field.origin not in _COUNTED_TO_DO and (field.blockers or field.origin in NEEDS_ATTENTION)
    )
    return counts.needs_input + counts.default_to_confirm + others


def section_mark(section: ModeloFormSection, *, recorded: bool = False) -> WorkbenchMark:
    """The most severe thing a section still holds: a blocker, then a missing value, then an assumed one.

    A section of a declaration recorded as filed holds nothing left to do.
    """
    if recorded:
        return DONE_MARK
    fields = section_fields(section)
    if any(field.blockers for field in fields):
        return BLOCKS_MARK
    missing = any(field.origin in NEEDS_ATTENTION and field.origin not in _COUNTED_TO_DO for field in fields)
    if missing or section.counts.needs_input:
        return MISSING_MARK
    if section.counts.default_to_confirm:
        return CONFIRM_MARK
    return DONE_MARK


def section_heading_text(section: ModeloFormSection, *, recorded: bool = False) -> str:
    """Say whether a section is complete, or how many of its fields still need the filer."""
    mark = section_mark(section, recorded=recorded).glyph
    pending = _pending(section, recorded=recorded)
    if pending:
        pending_text = tr("tui.modelo.workbench.section.pending", heading=section.heading.text, count=pending)
        return f"{mark} {pending_text}"
    return f"{mark} {section.heading.text}"


def section_nav_text(section: ModeloFormSection, width: int, *, recorded: bool = False) -> str:
    """Name a section in the navigator: its most severe mark, the heading cut to fit, and what is still to do."""
    pending = _pending(section, recorded=recorded)
    suffix = f" ({pending})" if pending else ""
    room = max(width - 2 - len(suffix), 4)
    heading = section.heading.text
    if len(heading) > room:
        heading = heading[: room - 1] + "…"
    return f"{section_mark(section, recorded=recorded).glyph} {heading}{suffix}"


def _section_items(
    section: ModeloFormSection,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter,
    *,
    recorded: bool,
) -> list[CasillaListItem]:
    items: list[CasillaListItem] = []
    counts = section.counts
    for block in section.blocks:
        if isinstance(block, ModeloFormFieldBlock):
            if _shown(block.field, staged, mode, counts, recorded=recorded):
                items.append(_entry(block.field, staged, recorded=recorded))
        elif isinstance(block, ModeloFormBindingInputsBlock):
            items.extend(
                _entry(field, staged, recorded=recorded)
                for field in block.fields
                if _shown(field, staged, mode, counts, recorded=recorded)
            )
        elif isinstance(block, ModeloFormGridBlock):
            for row in block.rows:
                row_items: list[CasillaListItem] = []
                rate_box = _rate_box(row)
                for column, cell in zip(block.columns, row.cells, strict=True):
                    if cell.field is not None and _shown(cell.field, staged, mode, counts, recorded=recorded):
                        row_items.append(
                            _entry(
                                cell.field,
                                staged,
                                indent=2,
                                label=column.heading.text,
                                rate_of_row=cell.field is rate_box,
                                recorded=recorded,
                            )
                        )
                    elif cell.literal is not None and mode is WorkbenchFilter.ALL:
                        fixed = tr(_DESIGN_CONSTANT_KEY, column=column.heading.text, value=cell.literal)
                        row_items.append(CasillaListNote(fixed, indent=2))
                if row_items:
                    items.append(CasillaListHeading(row.heading.text, level=1))
                    items.extend(row_items)
        elif mode is WorkbenchFilter.ALL:
            items.append(CasillaListHeading(tr("tui.modelo.workbench.repeating", count=len(block.rows)), level=1))
            if not block.rows_known:
                items.append(CasillaListNote(tr("tui.modelo.workbench.repeating_unknown"), indent=2))
    if not items:
        return []
    return [CasillaListHeading(section_heading_text(section, recorded=recorded)), *items]


def page_items(
    page: WorkbenchPage,
    *,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter = WorkbenchFilter.ALL,
) -> tuple[CasillaListItem, ...]:
    """Lay one page out as list lines, overlaying the filer's staged changes."""
    items: list[CasillaListItem] = []
    for section in page.sections:
        items.extend(_section_items(section, staged, mode, recorded=page.recorded))
    details = [
        _entry(field, staged, recorded=page.recorded)
        for field in page.details
        if _shown(field, staged, mode, recorded=page.recorded)
    ]
    if details:
        items.append(CasillaListHeading(page.heading.text))
        items.extend(details)
    return tuple(items)


def page_of(pages: tuple[WorkbenchPage, ...], key: AddressKey) -> int | None:
    """Return the index of the page that shows one address, if any does."""
    for index, page in enumerate(pages):
        if any(address_key(field.address) == key for field in page.fields()):
            return index
    return None


def first_attention(pages: tuple[WorkbenchPage, ...]) -> tuple[int, AddressKey] | None:
    """Return the first field anywhere in the form that needs the filer."""
    for index, page in enumerate(pages):
        placed = [(field, section.counts) for section in page.sections for field in section_fields(section)]
        details: list[tuple[ModeloFormField, ModeloFormCounts | None]] = [(field, None) for field in page.details]
        for field, counts in (*placed, *details):
            if _to_do(field, counts, recorded=page.recorded):
                return index, address_key(field.address)
    return None


def official_page(form: ModeloWorkForm, page_id: str) -> ModeloFormPage | None:
    """Return the form page with one id, or ``None`` for the details page."""
    return next((page for page in form.pages if page.id == page_id), None)


__all__ = [
    "DETAILS_PAGE_ID",
    "StagedDisplay",
    "WorkbenchFilter",
    "WorkbenchPage",
    "first_attention",
    "official_page",
    "page_items",
    "page_of",
    "section_heading_text",
    "section_mark",
    "section_nav_text",
    "workbench_pages",
]
