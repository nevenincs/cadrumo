"""The navigator's words: official headings, what each page and section still needs, and a breadcrumb.

A heading is the official one or a plain description of where the section
sits, never a registry id: a heading that reads like an identifier (such as
``rdtotrabajores``, ``modelo-349-operador`` or ``DatosEconomicos/Resultados``)
is refused for the official heading, or the section is named by its place,
"Page 2, part 3".

Each section counts what needs the filer on the one attention scale: what
blocks filing, what is missing and what is assumed, and, dimmed, what the last
check found worth checking. A section with none of the first three is done.
Pages carry the same counts and fold open and closed; a finished page starts
closed, and the page holding the cursor or anything to do starts open. Below
the navigator's width the same facts become one breadcrumb line, so the counts
are never lost.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Final

from rich.text import Text

from .....application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormBindingInputsBlock,
    ModeloFormBlock,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormOrigin,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from .....core.i18n.render import tr
from .casilla_list import AddressKey
from .page_items import WorkbenchPage
from .vocabulary import (
    BLOCKS_MARK,
    CHECK_MARK,
    COLLAPSED_MARK,
    CONFIRM_MARK,
    DONE_MARK,
    EXPANDED_MARK,
    HERE_MARK,
    MISSING_MARK,
    WorkbenchMark,
)

_JOINERS: Final[frozenset[str]] = frozenset("/-_.")
_CAMEL_JOIN: Final[re.Pattern[str]] = re.compile(r"[a-z][A-Z]")
_LONGEST_PLAIN_WORD: Final[int] = 11
_DIMMED: Final[str] = "dim"
_ELLIPSIS: Final[str] = "…"
_MIN_ROOM: Final[int] = 4


def looks_like_identifier(text: str) -> bool:
    """Whether a heading reads like an identifier rather than words a filer would read.

    A heading with no space is an identifier when it joins parts with ``/``,
    ``-``, ``_`` or ``.``, when it runs CamelCase words together, or when it is
    one lower-case token longer than a plain word or carrying digits. A single
    word such as "Resultado" or "Liquidación" stays.
    """
    stripped = text.strip()
    if not stripped or any(character.isspace() for character in stripped):
        return False
    if any(character in _JOINERS for character in stripped) or _CAMEL_JOIN.search(stripped):
        return True
    lower = stripped == stripped.lower() and any(character.isalpha() for character in stripped)
    return lower and (len(stripped) > _LONGEST_PLAIN_WORD or any(character.isdigit() for character in stripped))


def readable_text(text: ModeloFormText) -> str | None:
    """A text a filer can read, or ``None`` when it is only a technical name."""
    if text.disclosure is ModeloFormTextDisclosure.TECHNICAL or looks_like_identifier(text.text):
        return None
    return text.text


def section_title(section: ModeloFormSection, *, page_number: int, part_number: int) -> ModeloFormText:
    """The words a section is shown under: its heading, then its official heading, then its place."""
    if readable_text(section.heading) is not None:
        return section.heading
    official = section.official_heading
    if official and not looks_like_identifier(official):
        return ModeloFormText(text=official, disclosure=ModeloFormTextDisclosure.OFFICIAL_SPANISH)
    return ModeloFormText(
        text=tr("tui.modelo.workbench.section.part", page=page_number, part=part_number),
        disclosure=ModeloFormTextDisclosure.LOCALIZED,
    )


def page_title(heading: ModeloFormText, *, page_number: int) -> ModeloFormText:
    """The words a page is shown under: its heading, or its number when the heading reads like an id."""
    if readable_text(heading) is not None:
        return heading
    return ModeloFormText(
        text=tr("tui.modelo.workbench.page_number", page=page_number), disclosure=ModeloFormTextDisclosure.LOCALIZED
    )


def _settled(field: ModeloFormField) -> ModeloFormField:
    return field.model_copy(update={"blockers": ()}) if field.blockers else field


def _settled_block(block: ModeloFormBlock) -> ModeloFormBlock:
    if isinstance(block, ModeloFormFieldBlock):
        return block.model_copy(update={"field": _settled(block.field)})
    if isinstance(block, ModeloFormBindingInputsBlock):
        return block.model_copy(update={"fields": tuple(_settled(field) for field in block.fields)})
    if isinstance(block, ModeloFormGridBlock):
        rows = tuple(
            row.model_copy(
                update={
                    "cells": tuple(
                        cell if cell.field is None else cell.model_copy(update={"field": _settled(cell.field)})
                        for cell in row.cells
                    )
                }
            )
            for row in block.rows
        )
        return block.model_copy(update={"rows": rows})
    return block


def presented_form(form: ModeloWorkForm, *, recorded: bool = False) -> ModeloWorkForm:
    """The form with every page and section under words a filer can read.

    A declaration recorded as filed asks nothing more of the filer, so its
    boxes carry no blocker mark; nothing else changes.
    """
    pages = []
    for page_number, page in enumerate(form.pages, start=1):
        sections = tuple(
            section.model_copy(
                update={
                    "heading": section_title(section, page_number=page_number, part_number=part_number),
                    "blocks": tuple(_settled_block(block) for block in section.blocks) if recorded else section.blocks,
                }
            )
            for part_number, section in enumerate(page.sections, start=1)
        )
        pages.append(
            page.model_copy(update={"heading": page_title(page.heading, page_number=page_number), "sections": sections})
        )
    update: dict[str, object] = {"pages": tuple(pages)}
    if recorded:
        update["working_figures"] = tuple(_settled(field) for field in form.working_figures)
        update["unplaced"] = tuple(item.model_copy(update={"field": _settled(item.field)}) for item in form.unplaced)
    return form.model_copy(update=update)


@dataclass(frozen=True, slots=True)
class AttentionCounts:
    """What in one part of the form needs the filer, on the attention scale."""

    blocks: int = 0
    missing: int = 0
    confirm: int = 0
    check: int = 0

    @property
    def to_do(self) -> int:
        """What must be done before filing: blockers, missing values and assumed values."""
        return self.blocks + self.missing + self.confirm

    def __add__(self, other: AttentionCounts) -> AttentionCounts:
        """Add two parts' counts."""
        return AttentionCounts(
            self.blocks + other.blocks,
            self.missing + other.missing,
            self.confirm + other.confirm,
            self.check + other.check,
        )

    @property
    def mark(self) -> WorkbenchMark:
        """The most urgent level present, or done when nothing is to do."""
        if self.blocks:
            return BLOCKS_MARK
        if self.missing:
            return MISSING_MARK
        if self.confirm:
            return CONFIRM_MARK
        return DONE_MARK

    def chips(self) -> tuple[tuple[WorkbenchMark, int], ...]:
        """The levels with anything in them, most urgent first."""
        levels = ((BLOCKS_MARK, self.blocks), (MISSING_MARK, self.missing), (CONFIRM_MARK, self.confirm))
        return tuple((mark, count) for mark, count in levels if count)

    def text(self) -> Text:
        """The counts as compact chips, what is worth checking dimmed."""
        line = Text(" ".join(f"{mark.glyph}{count}" for mark, count in self.chips()))
        if self.check:
            line.append(f"{' ' if line.plain else ''}{CHECK_MARK.glyph}{self.check}", style=_DIMMED)
        return line

    def drawn(self) -> tuple[WorkbenchMark, ...]:
        """The marks these counts draw as chips."""
        return (*(mark for mark, _ in self.chips()), *((CHECK_MARK,) if self.check else ()))


def field_counts(fields: Iterable[ModeloFormField], checked_boxes: Mapping[str, int]) -> AttentionCounts:
    """Count what the fields need, with the check findings that name their boxes."""
    blocks = missing = confirm = check = 0
    for item in fields:
        if item.blockers:
            blocks += 1
        if item.origin is ModeloFormOrigin.NEEDS_INPUT:
            missing += 1
        elif item.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM:
            confirm += 1
        if item.box is not None:
            check += checked_boxes.get(item.box, 0)
    return AttentionCounts(blocks, missing, confirm, check)


def checked_boxes(form: ModeloWorkForm) -> dict[str, int]:
    """How many of the last check's warnings name each box."""
    counts: dict[str, int] = {}
    for issue in form.issues:
        if issue.attention is ModeloFormAttention.CHECK and issue.box is not None:
            counts[issue.box] = counts.get(issue.box, 0) + 1
    return counts


def page_counts(page: WorkbenchPage, checked: Mapping[str, int]) -> AttentionCounts:
    """What one page needs, over its sections and its calculation details."""
    return field_counts(page.fields(), checked)


def _room(width: int, lead: Text, tail: Text) -> int:
    """The cells a heading gets between what leads its line and the chips after it."""
    return width - len(lead.plain) - (len(tail.plain) + 1 if tail.plain else 0)


def _fit(text: str, room: int) -> str:
    room = max(room, _MIN_ROOM)
    return text if len(text) <= room else text[: room - 1] + _ELLIPSIS


def _suffix(counts: AttentionCounts) -> tuple[Text, tuple[WorkbenchMark, ...]]:
    """A page's counts after its title: its chips, or done with anything worth checking dimmed."""
    if counts.to_do:
        return counts.text(), counts.drawn()
    text = Text(DONE_MARK.glyph)
    if not counts.check:
        return text, (DONE_MARK,)
    text.append(f" {CHECK_MARK.glyph}{counts.check}", style=_DIMMED)
    return text, (DONE_MARK, CHECK_MARK)


@dataclass(frozen=True, slots=True)
class NavigatorRow:
    """One navigator line: a page or a section, what it shows and the marks it draws."""

    option_id: str
    prompt: Text
    marks: tuple[WorkbenchMark, ...]


@dataclass(slots=True)
class NavigatorState:
    """Which pages the filer opened or closed; any other page follows the default."""

    chosen: dict[str, bool] = field(default_factory=dict)

    def expanded(self, page: WorkbenchPage, *, current: bool, counts: AttentionCounts) -> bool:
        """Whether a page is open: the filer's choice, else open when current or with something to do."""
        chosen = self.chosen.get(page.id)
        if chosen is not None:
            return chosen
        return current or counts.to_do > 0

    def toggle(self, page: WorkbenchPage, *, current: bool, counts: AttentionCounts, open_: bool | None) -> None:
        """Open, close or flip one page."""
        now = self.expanded(page, current=current, counts=counts)
        self.chosen[page.id] = (not now) if open_ is None else open_


def navigator_rows(
    pages: tuple[WorkbenchPage, ...],
    *,
    current: int,
    state: NavigatorState,
    checked: Mapping[str, int],
    width: int,
    show_attention: bool,
) -> tuple[NavigatorRow, ...]:
    """Lay the pages and their sections out as navigator lines, closed pages without their sections."""
    rows: list[NavigatorRow] = []
    for index, page in enumerate(pages):
        counts = page_counts(page, checked)
        is_current = index == current
        expanded = state.expanded(page, current=is_current, counts=counts) if page.sections else False
        fold = (EXPANDED_MARK if expanded else COLLAPSED_MARK) if page.sections else None
        marks: list[WorkbenchMark] = []
        prompt = Text()
        prompt.append(f"{fold.glyph} " if fold is not None else "  ")
        if fold is not None:
            marks.append(fold)
        if is_current:
            prompt.append(f"{HERE_MARK.glyph} ")
            marks.append(HERE_MARK)
        suffix = Text()
        if show_attention:
            suffix, drawn = _suffix(counts)
            marks.extend(drawn)
        prompt.append(_fit(page.heading.text, _room(width, prompt, suffix)))
        if suffix.plain:
            prompt.append(" ").append_text(suffix)
        rows.append(NavigatorRow(f"page:{index}", prompt, tuple(marks)))
        if not expanded:
            continue
        for section in page.sections:
            section_counts = field_counts(section_fields(section), checked)
            line = Text("    ")
            section_marks: list[WorkbenchMark] = []
            chips = section_counts.text() if show_attention else Text()
            if show_attention:
                mark = section_counts.mark
                line.append(f"{mark.glyph} ")
                section_marks.append(mark)
                section_marks.extend(section_counts.drawn())
            line.append(_fit(section.heading.text, _room(width, line, chips)))
            if chips.plain:
                line.append(" ").append_text(chips)
            rows.append(NavigatorRow(f"section:{index}:{section.id}", line, tuple(section_marks)))
    return tuple(rows)


def section_of(page: WorkbenchPage, field_key: AddressKey) -> ModeloFormSection | None:
    """The section of ``page`` that shows the field with ``field_key``, if any."""
    for section in page.sections:
        if any(address_key(item.address) == field_key for item in section_fields(section)):
            return section
    return None


def breadcrumb(
    pages: tuple[WorkbenchPage, ...],
    *,
    current: int,
    section: ModeloFormSection | None,
    checked: Mapping[str, int],
    show_attention: bool,
) -> tuple[Text, tuple[WorkbenchMark, ...]]:
    """The navigator in one line for a narrow terminal: the page, the section and what the page needs."""
    page = pages[current]
    parts = [tr("tui.modelo.workbench.page_position", current=current + 1, total=len(pages)), page.heading.text]
    if section is not None:
        parts.append(section.heading.text)
    line = Text(" · ".join(parts))
    marks: tuple[WorkbenchMark, ...] = ()
    if show_attention:
        chips, marks = _suffix(page_counts(page, checked))
        line.append(" · ").append_text(chips)
    return line, marks


__all__ = [
    "AttentionCounts",
    "NavigatorRow",
    "NavigatorState",
    "breadcrumb",
    "checked_boxes",
    "field_counts",
    "looks_like_identifier",
    "navigator_rows",
    "page_counts",
    "page_title",
    "presented_form",
    "readable_text",
    "section_of",
    "section_title",
]
