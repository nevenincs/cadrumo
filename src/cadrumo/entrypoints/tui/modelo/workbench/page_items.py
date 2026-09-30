"""Turn one page of the editor form into the lines of the casilla list.

A section becomes a heading that says whether anything in it still needs the
filer; an official grid becomes its printed rows, each row heading followed by
its boxes in column order, labelled by their column, and carrying the row's
place in its grid so the list can draw the paper form's table; the records of
a repeating group become a read-only table. A value the official design fixes
is never an editable field. The working figures and the unplaced casillas are
one more page, so nothing the form holds is out of the filer's reach.

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
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormRepeatingBlock,
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
    shown_rate,
)
from .grid import CasillaListRecords, GridRowPlace, GridShape, GridSlot
from .vocabulary import BLOCKS_MARK, CONFIRM_MARK, DONE_MARK, MISSING_MARK, NEEDS_ATTENTION, WorkbenchMark

DETAILS_PAGE_ID: Final[str] = "details"
_RATIO_DATA_TYPE: Final[str] = "ratio"
_COUNTED_TO_DO: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.NEEDS_INPUT, ModeloFormOrigin.DEFAULT_TO_CONFIRM}
)
"""Origins a section's counts tally as still to do; the counts, not the bare origins, say how many."""
_COLUMN_UNNAMED_KEY: Final[str] = "tui.modelo.workbench.grid.column_unnamed"
_RECORDS_KEY: Final[str] = "tui.modelo.workbench.repeating"
_RECORDS_UNKNOWN_KEY: Final[str] = "tui.modelo.workbench.grid.records_unknown"
_RECORDS_READ_ONLY_KEY: Final[str] = "tui.modelo.workbench.grid.records_read_only"


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
    row_label: str | None = None,
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
        row_label=row_label,
        column_label=None if row_label is None else label,
    )


def _rate_box(row: ModeloFormGridRow) -> ModeloFormField | None:
    """The one rate box an official row prints, or ``None`` when it prints none or several."""
    rates = [cell.field for cell in row.cells if cell.field is not None and cell.field.data_type == _RATIO_DATA_TYPE]
    return rates[0] if len(rates) == 1 else None


def _column_headings(columns: tuple[ModeloFormGridColumn, ...], rows: tuple[ModeloFormGridRow, ...]) -> tuple[str, ...]:
    """Each column's heading: the official words, else the label of its first box, never a technical key."""
    headings: list[str] = []
    for index, column in enumerate(columns):
        if column.heading.disclosure is not ModeloFormTextDisclosure.TECHNICAL:
            headings.append(column.heading.text)
            continue
        labels = (
            cell.field.label
            for row in rows
            for cell in row.cells[index : index + 1]
            if cell.field is not None and cell.field.label.disclosure is not ModeloFormTextDisclosure.TECHNICAL
        )
        label = next(labels, None)
        headings.append(label.text if label is not None else tr(_COLUMN_UNNAMED_KEY, number=index + 1))
    return tuple(headings)


def _grid_items(
    block: ModeloFormGridBlock,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter,
    counts: ModeloFormCounts,
    *,
    recorded: bool,
) -> list[CasillaListItem]:
    """An official grid as its printed rows: each row's heading, then its boxes in column order.

    The heading carries the row's place in its grid, so the list can draw the
    grid as a table, with an empty slot wherever the paper form has no box or
    the filter hides one, or stack it when the table does not fit.
    """
    headings = _column_headings(block.columns, block.rows)
    shape = GridShape(id=block.id, headings=headings)
    items: list[CasillaListItem] = []
    for row in block.rows:
        row_items: list[CasillaListItem] = []
        slots: list[GridSlot] = []
        rate_box = _rate_box(row)
        for heading, cell in zip(headings, row.cells, strict=True):
            field = cell.field
            if field is not None and _shown(field, staged, mode, counts, recorded=recorded):
                row_items.append(
                    _entry(
                        field,
                        staged,
                        indent=2,
                        label=heading,
                        row_label=row.heading.text,
                        rate_of_row=field is rate_box,
                        recorded=recorded,
                    )
                )
                slots.append(GridSlot(key=address_key(field.address)))
            elif field is None and cell.literal is not None and mode is WorkbenchFilter.ALL:
                row_items.append(CasillaListNote(f"{heading}: {cell.literal}", indent=2))
                slots.append(GridSlot(literal=cell.literal))
            else:
                slots.append(GridSlot())
        if not row_items:
            continue
        place = GridRowPlace(
            grid=shape,
            heading=row.heading.text,
            slots=tuple(slots),
            span=len(row_items),
            rate=None if rate_box is None else shown_rate(rate_box),
            boxes=tuple(cell.field.box for cell in row.cells if cell.field is not None and cell.field.box),
        )
        items.append(CasillaListHeading(row.heading.text, level=1, row=place))
        items.extend(row_items)
    return items


def _record_items(block: ModeloFormRepeatingBlock) -> list[CasillaListItem]:
    """A repeating group's records, read-only, or a plain statement that their number is not known."""
    if not block.rows_known:
        return [CasillaListNote(tr(_RECORDS_UNKNOWN_KEY), indent=2)]
    items: list[CasillaListItem] = [CasillaListHeading(tr(_RECORDS_KEY, count=len(block.rows)), level=1)]
    if block.rows:
        headings = _column_headings(block.columns, ())
        items.append(CasillaListRecords(headings=headings, data_types=block.column_data_types, rows=block.rows))
        items.append(CasillaListNote(tr(_RECORDS_READ_ONLY_KEY), indent=2))
    return items


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
            items.extend(_grid_items(block, staged, mode, counts, recorded=recorded))
        elif mode is WorkbenchFilter.ALL:
            items.extend(_record_items(block))
    if not items:
        return []
    heading = CasillaListHeading(
        section_heading_text(section, recorded=recorded), mark=section_mark(section, recorded=recorded)
    )
    return [heading, *items]


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
