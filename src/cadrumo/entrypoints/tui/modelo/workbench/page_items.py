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
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
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
from .vocabulary import NEEDS_ATTENTION

DETAILS_PAGE_ID: Final[str] = "details"
_DESIGN_CONSTANT_KEY: Final[str] = "tui.modelo.workbench.design_constant"
_DONE_MARK: Final[str] = "✓"
_PENDING_MARK: Final[str] = "!"


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

    def fields(self) -> tuple[ModeloFormField, ...]:
        """Every field the page holds, in reading order."""
        collected = [field for section in self.sections for field in section_fields(section)]
        collected.extend(self.details)
        return tuple(collected)


def workbench_pages(form: ModeloWorkForm) -> tuple[WorkbenchPage, ...]:
    """Return the form's pages, followed by the calculation details when it has any."""
    pages = [WorkbenchPage(id=page.id, heading=page.heading, sections=page.sections) for page in form.pages]
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
            )
        )
    return tuple(pages)


def _shown(field: ModeloFormField, staged: Mapping[AddressKey, StagedDisplay], mode: WorkbenchFilter) -> bool:
    if mode is WorkbenchFilter.ALL:
        return True
    key = address_key(field.address)
    if mode is WorkbenchFilter.ATTENTION:
        return key in staged or bool(field.blockers) or field.origin in NEEDS_ATTENTION
    return key in staged or field.origin in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}


def _entry(
    field: ModeloFormField,
    staged: Mapping[AddressKey, StagedDisplay],
    *,
    indent: int = 0,
    label: str | None = None,
) -> CasillaListEntry:
    change = staged.get(address_key(field.address))
    return CasillaListEntry(
        field=field,
        indent=indent,
        label=label,
        staged_text=None if change is None else change.text,
        previous_text=None if change is None else change.previous_text,
    )


def section_heading_text(section: ModeloFormSection) -> str:
    """Say whether a section is complete, or how many of its fields still need the filer."""
    pending = sum(1 for field in section_fields(section) if field.origin in NEEDS_ATTENTION)
    if pending:
        pending_text = tr("tui.modelo.workbench.section.pending", heading=section.heading.text, count=pending)
        return f"{_PENDING_MARK} {pending_text}"
    return f"{_DONE_MARK} {section.heading.text}"


def section_nav_text(section: ModeloFormSection, width: int) -> str:
    """Name a section in the navigator: a mark, the heading cut to fit, and what is still to do."""
    pending = sum(1 for field in section_fields(section) if field.origin in NEEDS_ATTENTION)
    mark, suffix = (_PENDING_MARK, f" ({pending})") if pending else (_DONE_MARK, "")
    room = max(width - 2 - len(suffix), 4)
    heading = section.heading.text
    if len(heading) > room:
        heading = heading[: room - 1] + "…"
    return f"{mark} {heading}{suffix}"


def _section_items(
    section: ModeloFormSection, staged: Mapping[AddressKey, StagedDisplay], mode: WorkbenchFilter
) -> list[CasillaListItem]:
    items: list[CasillaListItem] = []
    for block in section.blocks:
        if isinstance(block, ModeloFormFieldBlock):
            if _shown(block.field, staged, mode):
                items.append(_entry(block.field, staged))
        elif isinstance(block, ModeloFormBindingInputsBlock):
            items.extend(_entry(field, staged) for field in block.fields if _shown(field, staged, mode))
        elif isinstance(block, ModeloFormGridBlock):
            for row in block.rows:
                row_items: list[CasillaListItem] = []
                for column, cell in zip(block.columns, row.cells, strict=True):
                    if cell.field is not None and _shown(cell.field, staged, mode):
                        row_items.append(_entry(cell.field, staged, indent=2, label=column.heading.text))
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
    return [CasillaListHeading(section_heading_text(section)), *items]


def page_items(
    page: WorkbenchPage,
    *,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter = WorkbenchFilter.ALL,
) -> tuple[CasillaListItem, ...]:
    """Lay one page out as list lines, overlaying the filer's staged changes."""
    items: list[CasillaListItem] = []
    for section in page.sections:
        items.extend(_section_items(section, staged, mode))
    details = [_entry(field, staged) for field in page.details if _shown(field, staged, mode)]
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
        for field in page.fields():
            if field.origin in NEEDS_ATTENTION or field.blockers:
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
    "section_nav_text",
    "workbench_pages",
]
