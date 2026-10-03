"""Turn one page of the editor form into the lines of the casilla list.

A section becomes a heading that says, on the attention scale the navigator
and the header share, whether anything in it still needs the filer or waits
on an import or a calculation; an official grid becomes its printed rows,
each row heading followed by its boxes in column order, labelled by their
column, and carrying the row's place in its grid so the list can draw the
paper form's table; the records of a repeating group become a read-only
table. A value the official design fixes
is never an editable field. The working figures and the unplaced casillas are
one more page, so nothing the form holds is out of the filer's reach.

Filters narrow a page without changing it: showing only what needs attention,
only the filer's own values, only values from their records, only calculated
values, or only boxes holding an amount other than zero keeps the headings of
the sections that still have lines.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from .....application.modelo.source_policy import SourceFamily
from .....application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormBindingInputsBlock,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormOrigin,
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
from .vocabulary import (
    DONE_MARK,
    AttentionCounts,
    WorkbenchMark,
    field_counts,
    field_needs_filer,
    holds_nothing,
    holds_zero,
)

DETAILS_PAGE_ID: Final[str] = "details"
_RATIO_DATA_TYPE: Final[str] = "ratio"
_COLUMN_UNNAMED_KEY: Final[str] = "tui.modelo.workbench.grid.column_unnamed"
_NAMELESS_DISCLOSURES: Final[frozenset[ModeloFormTextDisclosure]] = frozenset(
    {ModeloFormTextDisclosure.TECHNICAL, ModeloFormTextDisclosure.UNNAMED}
)
"""Labels that name no column: a technical name, or words saying the form gives the box no name."""
_RECORDS_KEY: Final[str] = "tui.modelo.workbench.repeating"
#: The kind of address that names a casilla, as a finding about a record column names it.
_CASILLA_KIND: Final[str] = "casilla"
_RECORDS_UNKNOWN_KEY: Final[str] = "tui.modelo.workbench.grid.records_unknown"
_RECORDS_READ_ONLY_KEY: Final[str] = "tui.modelo.workbench.grid.records_read_only"


_RECORD_FINDING_LEVELS: Final[Mapping[ModeloFormAttention, str]] = MappingProxyType(
    {
        ModeloFormAttention.BLOCKS: "blocks",
        ModeloFormAttention.MISSING: "missing",
        ModeloFormAttention.CONFIRM: "confirm",
        ModeloFormAttention.CHECK: "check",
    }
)
"""Where a finding about a table's values counts on the attention scale; one for information counts nowhere."""


class WorkbenchFilter(StrEnum):
    """Which fields a page shows."""

    ALL = "all"
    ATTENTION = "attention"
    MINE = "mine"
    RECORDS = "records"
    CALCULATED = "calculated"
    AMOUNT = "amount"


_MINE_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}
)
_RECORD_FAMILIES: Final[frozenset[SourceFamily]] = frozenset({SourceFamily.RECORDS, SourceFamily.REGISTERS})
_FROM_SOURCE_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.NOT_IMPORTED_YET}
)
_NO_AMOUNT_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {
        ModeloFormOrigin.NOT_APPLICABLE,
        ModeloFormOrigin.NOT_CALCULATED_YET,
        ModeloFormOrigin.CALCULATION_FAILED,
        ModeloFormOrigin.NOT_IMPORTED_YET,
        ModeloFormOrigin.CLEARED,
    }
)
"""Origins whose value is not there, whatever the field still holds, so it is no amount the filer declares."""


def _from_records(field: ModeloFormField) -> bool:
    source = field.source
    return field.origin in _FROM_SOURCE_ORIGINS and source is not None and source.family in _RECORD_FAMILIES


def _holds_amount(field: ModeloFormField) -> bool:
    """Whether a box holds an amount other than zero: a figure, never nothing, a held zero or a yes-or-no."""
    value = field.value
    if field.origin in _NO_AMOUNT_ORIGINS or holds_nothing(value) or holds_zero(value) or isinstance(value, bool):
        return False
    return isinstance(value, Decimal | int)


@dataclass(frozen=True, slots=True)
class StagedDisplay:
    """How a staged change reads on its line: the new value and the value it replaces."""

    text: str
    previous_text: str
    #: A typed SET, including False/0, rather than a clear or restore label.
    concrete_value: bool = False


@dataclass(frozen=True, slots=True)
class WorkbenchPage:
    """One page of the workbench: an official page, or the calculation details."""

    id: str
    heading: ModeloFormText
    sections: tuple[ModeloFormSection, ...]
    details: tuple[ModeloFormField, ...] = ()
    #: The declaration is recorded as filed, so nothing on it is left to enter or confirm.
    recorded: bool = False
    #: ``False`` when the read model states the page does not apply this period, so it asks for no value.
    applies: bool = True
    #: What the last check found about the values of each section's tables of records, by section id.
    records: Mapping[str, AttentionCounts] = dataclass_field(default_factory=lambda: MappingProxyType({}))

    def fields(self) -> tuple[ModeloFormField, ...]:
        """Every field the page holds, in reading order."""
        collected = [field for section in self.sections for field in section_fields(section)]
        collected.extend(self.details)
        return tuple(collected)


def records_attention(
    form: ModeloWorkForm, sections: tuple[ModeloFormSection, ...], *, recorded: bool, applies: bool
) -> Mapping[str, AttentionCounts]:
    """What the last check found about the values of each section's tables of records, by section id.

    A finding about a value every record of a table carries names no box, so
    it stands for the section that holds the table: a section is not done
    while one of its tables misses a value. As for boxes, nothing is asked of
    a declaration recorded as filed or of a page that does not apply.
    """
    asked = not recorded and applies
    counts: dict[str, AttentionCounts] = {}
    for section in sections:
        columns = _record_columns(section)
        if not columns:
            continue
        total = _section_record_attention(form, columns, asked=asked)
        if total != AttentionCounts():
            counts[section.id] = total
    return MappingProxyType(counts)


def _record_columns(section: ModeloFormSection) -> set[str]:
    return {
        casilla_id
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
        for casilla_id in block.column_casilla_ids
        if casilla_id is not None
    }


def _section_record_attention(form: ModeloWorkForm, columns: set[str], *, asked: bool) -> AttentionCounts:
    total = AttentionCounts()
    for issue in form.issues:
        casilla_id = issue.finding.casilla_id
        if casilla_id is None or str(casilla_id) not in columns:
            continue
        level = _RECORD_FINDING_LEVELS.get(issue.attention)
        if level is None or (level != "check" and not asked):
            continue
        total = total + AttentionCounts(**{level: 1, "pending": int(level != "check")})
    return total


def workbench_pages(form: ModeloWorkForm) -> tuple[WorkbenchPage, ...]:
    """Return the form's pages, followed by the calculation details when it has any."""
    recorded = form.filing is not None
    pages = [
        WorkbenchPage(
            id=page.id,
            heading=page.heading,
            sections=page.sections,
            recorded=recorded,
            applies=page.applies is not False,
            records=records_attention(form, page.sections, recorded=recorded, applies=page.applies is not False),
        )
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


def _shown(
    field: ModeloFormField, staged: Mapping[AddressKey, StagedDisplay], mode: WorkbenchFilter, page: WorkbenchPage
) -> bool:
    if mode is WorkbenchFilter.ALL:
        return True
    key = address_key(field.address)
    if key in staged:
        return True
    if mode is WorkbenchFilter.ATTENTION:
        return field_needs_filer(field, recorded=page.recorded, applies=page.applies)
    if mode is WorkbenchFilter.RECORDS:
        return _from_records(field)
    if mode is WorkbenchFilter.CALCULATED:
        return field.origin is ModeloFormOrigin.CALCULATED
    if mode is WorkbenchFilter.AMOUNT:
        return _holds_amount(field)
    return field.origin in _MINE_ORIGINS


def _entry(
    field: ModeloFormField,
    staged: Mapping[AddressKey, StagedDisplay],
    *,
    indent: int = 0,
    label: str | None = None,
    row_label: str | None = None,
    rate_of_row: bool = False,
    row_base_empty: bool | None = None,
    page: WorkbenchPage,
) -> CasillaListEntry:
    change = staged.get(address_key(field.address))
    return CasillaListEntry(
        field=field,
        indent=indent,
        label=label,
        staged_text=None if change is None else change.text,
        previous_text=None if change is None else change.previous_text,
        staged_concrete_value=False if change is None else change.concrete_value,
        rate_of_row=rate_of_row,
        row_base_empty=row_base_empty if rate_of_row else None,
        recorded=page.recorded,
        applies=page.applies,
        row_label=row_label,
        column_label=None if row_label is None else label,
    )


def _base_empty(row: ModeloFormGridRow, rate_box: ModeloFormField | None) -> bool | None:
    """Whether the base box before a row's rate box holds no amount; ``None`` where the row has no such box."""
    if rate_box is None:
        return None
    fields = [cell.field for cell in row.cells]
    index = next((position for position, item in enumerate(fields) if item is rate_box), None)
    base = None if not index else fields[index - 1]
    if base is None or base.data_type == _RATIO_DATA_TYPE:
        return None
    return not _holds_amount(base)


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
            if cell.field is not None and cell.field.label.disclosure not in _NAMELESS_DISCLOSURES
        )
        label = next(labels, None)
        headings.append(label.text if label is not None else tr(_COLUMN_UNNAMED_KEY, number=index + 1))
    return tuple(headings)


def _grid_cell_item(
    heading: str,
    cell: ModeloFormGridCell,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter,
    page: WorkbenchPage,
    *,
    row_label: str,
    rate_box: ModeloFormField | None,
    base_empty: bool | None,
) -> tuple[CasillaListItem | None, GridSlot]:
    field = cell.field
    if field is not None and _shown(field, staged, mode, page):
        entry = _entry(
            field,
            staged,
            indent=2,
            label=heading,
            row_label=row_label,
            rate_of_row=field is rate_box,
            row_base_empty=base_empty,
            page=page,
        )
        return entry, GridSlot(key=address_key(field.address))
    if field is None and cell.literal is not None and mode is WorkbenchFilter.ALL:
        return CasillaListNote(f"{heading}: {cell.literal}", indent=2), GridSlot(literal=cell.literal)
    return None, GridSlot()


def _grid_row_items(
    row: ModeloFormGridRow,
    headings: tuple[str, ...],
    shape: GridShape,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter,
    page: WorkbenchPage,
) -> tuple[CasillaListHeading | None, list[CasillaListItem]]:
    rate_box = _rate_box(row)
    base_empty = _base_empty(row, rate_box)
    row_items: list[CasillaListItem] = []
    slots: list[GridSlot] = []
    for heading, cell in zip(headings, row.cells, strict=True):
        item, slot = _grid_cell_item(
            heading,
            cell,
            staged,
            mode,
            page,
            row_label=row.heading.text,
            rate_box=rate_box,
            base_empty=base_empty,
        )
        if item is not None:
            row_items.append(item)
        slots.append(slot)
    if not row_items:
        return None, []
    place = GridRowPlace(
        grid=shape,
        heading=row.heading.text,
        slots=tuple(slots),
        span=len(row_items),
        rate=None if rate_box is None else shown_rate(rate_box),
        boxes=tuple(cell.field.box for cell in row.cells if cell.field is not None and cell.field.box),
    )
    return CasillaListHeading(row.heading.text, level=1, row=place), row_items


def _grid_items(
    block: ModeloFormGridBlock,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter,
    page: WorkbenchPage,
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
        row_heading, row_items = _grid_row_items(
            row,
            headings,
            shape,
            staged,
            mode,
            page,
        )
        if row_heading is None:
            continue
        items.append(row_heading)
        items.extend(row_items)
    return items


def _record_items(block: ModeloFormRepeatingBlock) -> list[CasillaListItem]:
    """Keep a known table, including an empty one, or state that its record count is unknown."""
    if not block.rows_known:
        return [CasillaListNote(tr(_RECORDS_UNKNOWN_KEY), indent=2, column_casilla_ids=block.column_casilla_ids)]
    return [
        CasillaListHeading(tr(_RECORDS_KEY, count=len(block.rows)), level=1),
        CasillaListRecords(
            headings=_column_headings(block.columns, ()),
            data_types=block.column_data_types,
            rows=block.rows,
            column_casilla_ids=block.column_casilla_ids,
        ),
        CasillaListNote(tr(_RECORDS_READ_ONLY_KEY), indent=2),
    ]


def section_counts(
    section: ModeloFormSection,
    *,
    recorded: bool = False,
    applies: bool = True,
    records: AttentionCounts | None = None,
) -> AttentionCounts:
    """What one section holds on the attention scale the navigator, the grid rows and the header share.

    ``records`` is what the last check found about the values of the
    section's tables of records (:func:`records_attention`).
    """
    counts = field_counts(section_fields(section), recorded=recorded, applies=applies)
    return counts if records is None else counts + records


def section_mark(
    section: ModeloFormSection,
    *,
    recorded: bool = False,
    applies: bool = True,
    records: AttentionCounts | None = None,
) -> WorkbenchMark | None:
    """The most severe thing a section holds: a blocker, a missing, failed or assumed value, then what still waits.

    A section is done only when nothing is to do and nothing waits on an
    import or a calculation. On a declaration recorded as filed, and on a page
    that does not apply, no value is asked, but a failure or a wait is still a
    fact about the box and keeps its mark. A filed declaration draws no done
    mark, as its navigator draws none: completing it is no longer the filer's
    task.
    """
    mark = section_counts(section, recorded=recorded, applies=applies, records=records).mark
    return None if recorded and mark is DONE_MARK else mark


def section_heading_text(
    section: ModeloFormSection,
    *,
    recorded: bool = False,
    applies: bool = True,
    records: AttentionCounts | None = None,
) -> str:
    """Say whether a section is complete, or how many of its fields still need the filer."""
    counts = section_counts(section, recorded=recorded, applies=applies, records=records)
    if counts.pending:
        pending_text = tr("tui.modelo.workbench.section.pending", heading=section.heading.text, count=counts.pending)
        return f"{counts.mark.glyph} {pending_text}"
    mark = section_mark(section, recorded=recorded, applies=applies, records=records)
    return section.heading.text if mark is None else f"{mark.glyph} {section.heading.text}"


def _section_items(
    section: ModeloFormSection,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter,
    page: WorkbenchPage,
) -> list[CasillaListItem]:
    items: list[CasillaListItem] = []
    for block in section.blocks:
        if isinstance(block, ModeloFormFieldBlock):
            if _shown(block.field, staged, mode, page):
                items.append(_entry(block.field, staged, page=page))
        elif isinstance(block, ModeloFormBindingInputsBlock):
            items.extend(
                _entry(field, staged, page=page) for field in block.fields if _shown(field, staged, mode, page)
            )
        elif isinstance(block, ModeloFormGridBlock):
            items.extend(_grid_items(block, staged, mode, page))
        elif mode is WorkbenchFilter.ALL:
            items.extend(_record_items(block))
    if not items:
        return []
    records = page.records.get(section.id)
    heading = CasillaListHeading(
        section_heading_text(section, recorded=page.recorded, applies=page.applies, records=records),
        mark=section_mark(section, recorded=page.recorded, applies=page.applies, records=records),
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
        items.extend(_section_items(section, staged, mode, page))
    details = [_entry(field, staged, page=page) for field in page.details if _shown(field, staged, mode, page)]
    if details:
        items.append(CasillaListHeading(page.heading.text))
        items.extend(details)
    return tuple(items)


def page_of(pages: tuple[WorkbenchPage, ...], key: AddressKey) -> int | None:
    """Return the index of the page that shows one address, if any does.

    A casilla that is a column of a repeating group's records is shown on the
    page holding that group's table.
    """
    for index, page in enumerate(pages):
        if any(address_key(field.address) == key for field in page.fields()):
            return index
    kind, identifier = key
    if kind != _CASILLA_KIND:
        return None
    for index, page in enumerate(pages):
        if any(identifier in block.column_casilla_ids for block in _repeating_blocks(page)):
            return index
    return None


def _repeating_blocks(page: WorkbenchPage) -> tuple[ModeloFormRepeatingBlock, ...]:
    return tuple(
        block for section in page.sections for block in section.blocks if isinstance(block, ModeloFormRepeatingBlock)
    )


__all__ = [
    "DETAILS_PAGE_ID",
    "StagedDisplay",
    "WorkbenchFilter",
    "WorkbenchPage",
    "page_items",
    "page_of",
    "records_attention",
    "section_counts",
    "section_heading_text",
    "section_mark",
    "workbench_pages",
]
