"""The navigator's words: official headings, what each page and section still needs, and a breadcrumb.

A heading is the official one or a plain description of where the section
sits, never a registry id: a heading that reads like an identifier (such as
``rdtotrabajores``, ``modelo-349-operador`` or ``DatosEconomicos/Resultados``)
is refused for the official heading, or the section is named by the boxes it
holds, "Boxes 0018 to 0025", or, holding none, by its place, "Page 2, part 3".

Each section counts what needs the filer on the one attention scale the list
headings, the grid rows and the header share: what blocks filing, what is
missing, what could not be calculated and what is assumed, and, dimmed, what
still waits on an import or a calculation and what the last check found worth
checking. A section is done only when nothing is to do and nothing waits.
Pages carry the same counts and fold open and closed; a finished page starts
closed, and the page holding the cursor or anything to do starts open. Below
the navigator's width the same facts become one breadcrumb line, so the counts
are never lost.

A layout may print two parts of one page under the same heading; the
navigator lists that heading once, with the parts' counts added together.

A page the read model states does not apply to this period is dimmed, says so
in place of its counts, starts closed, and counts nothing as to do: its boxes
are not asked of the filer. A page that only may not apply, which the data
cannot decide, is listed and counted like any other, so nothing is set aside on
a guess.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from rich.cells import cell_len
from rich.text import Text

from .....application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormBindingInputsBlock,
    ModeloFormBlock,
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from .....core.i18n.render import tr
from ...components.cell_text import ellipsize
from .casilla_list import AddressKey
from .page_items import WorkbenchPage
from .vocabulary import (
    CHECK_MARK,
    COLLAPSED_MARK,
    DONE_MARK,
    EXPANDED_MARK,
    HERE_MARK,
    AttentionCounts,
    WorkbenchMark,
    field_counts,
)

_JOINERS: Final[frozenset[str]] = frozenset("/-_.")
_CAMEL_JOIN: Final[re.Pattern[str]] = re.compile(r"[a-z][A-Z]")
_LONGEST_PLAIN_WORD: Final[int] = 11
_DIMMED: Final[str] = "dim"
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
    return _has_identifier_join(stripped) or _is_long_lowercase_identifier(stripped)


def _has_identifier_join(text: str) -> bool:
    return any(character in _JOINERS for character in text) or _CAMEL_JOIN.search(text) is not None


def _is_long_lowercase_identifier(text: str) -> bool:
    lower = text == text.lower() and any(character.isalpha() for character in text)
    return lower and (len(text) > _LONGEST_PLAIN_WORD or any(character.isdigit() for character in text))


def readable_text(text: ModeloFormText) -> str | None:
    """A text a filer can read, or ``None`` when it is only a technical name."""
    if text.disclosure is ModeloFormTextDisclosure.TECHNICAL or looks_like_identifier(text.text):
        return None
    return text.text


def section_title(section: ModeloFormSection, *, page_number: int, part_number: int) -> ModeloFormText:
    """The words a section is shown under: its heading, its official heading, the boxes it holds, or its place."""
    if readable_text(section.heading) is not None:
        return section.heading
    official = section.official_heading
    if official and not looks_like_identifier(official):
        return ModeloFormText(text=official, disclosure=ModeloFormTextDisclosure.OFFICIAL_SPANISH)
    boxes = list(dict.fromkeys(field.box for field in section_fields(section) if field.box))
    return _section_location_title(boxes, page_number=page_number, part_number=part_number)


def _section_location_title(boxes: list[str], *, page_number: int, part_number: int) -> ModeloFormText:
    if len(boxes) == 1:
        text = tr("tui.modelo.workbench.section.box", box=boxes[0])
    elif boxes and all(box.isascii() and box.isdecimal() for box in boxes):
        text = tr("tui.modelo.workbench.section.boxes", first=min(boxes, key=int), last=max(boxes, key=int))
    else:
        text = tr("tui.modelo.workbench.section.part", page=page_number, part=part_number)
    return ModeloFormText(text=text, disclosure=ModeloFormTextDisclosure.LOCALIZED)


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


def inapplicable_pages(form: ModeloWorkForm) -> frozenset[str]:
    """The official pages the read model states do not apply to this filing, by id."""
    return frozenset(page.id for page in form.pages if page.applies is False)


def applicable_fields(form: ModeloWorkForm) -> tuple[ModeloFormField, ...]:
    """Every field the filer may be asked about: all but those on pages the read model states do not apply.

    It is the population :func:`to_do_counts` counts over, so a list of what
    is missing or assumed names exactly the boxes the header counts.
    """
    set_aside = inapplicable_pages(form)
    kept = [
        field
        for page in form.pages
        if page.id not in set_aside
        for section in page.sections
        for field in section_fields(section)
    ]
    kept.extend(form.working_figures)
    kept.extend(item.field for item in form.unplaced)
    return tuple(kept)


def to_do_counts(form: ModeloWorkForm) -> ModeloFormCounts:
    """The form's counts without what the pages that do not apply hold as missing or assumed.

    Those pages ask nothing of the filer, so their boxes are never to do; every
    other count, blockers included, stays as the read model states it.
    """
    set_aside = [page.counts for page in form.pages if page.applies is False]
    if not set_aside:
        return form.counts
    counts = form.counts
    return counts.model_copy(
        update={
            "needs_input": max(counts.needs_input - sum(item.needs_input for item in set_aside), 0),
            "default_to_confirm": max(
                counts.default_to_confirm - sum(item.default_to_confirm for item in set_aside), 0
            ),
        }
    )


def checked_boxes(form: ModeloWorkForm) -> dict[str, int]:
    """How many of the last check's warnings name each box."""
    counts: dict[str, int] = {}
    for issue in form.issues:
        if issue.attention is ModeloFormAttention.CHECK and issue.box is not None:
            counts[issue.box] = counts.get(issue.box, 0) + 1
    return counts


def page_counts(page: WorkbenchPage, checked: Mapping[str, int]) -> AttentionCounts:
    """What one page needs, over its sections, their tables of records and its calculation details."""
    counts = field_counts(page.fields(), checked, recorded=page.recorded, applies=page.applies)
    for records in page.records.values():
        counts = counts + records
    return counts


def _room(width: int, lead: Text, tail: Text) -> int:
    """The cells a heading gets between what leads its line and the chips after it."""
    return width - cell_len(lead.plain) - (cell_len(tail.plain) + 1 if tail.plain else 0)


def _fit(text: str, room: int) -> str:
    return ellipsize(text, max(room, _MIN_ROOM))


def _suffix(counts: AttentionCounts) -> tuple[Text, tuple[WorkbenchMark, ...]]:
    """A page's counts after its title: its chips, or done with anything worth checking dimmed.

    A page whose boxes still wait on an import or a calculation is not done,
    so it shows what waits rather than the done mark.
    """
    if counts.to_do or counts.waiting:
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

    def expanded(self, page: WorkbenchPage, *, current: bool, counts: AttentionCounts, applies: bool = True) -> bool:
        """Whether a page is open: the filer's choice, else open when current or with something to do.

        A page that does not apply this period starts closed, even under the cursor.
        """
        chosen = self.chosen.get(page.id)
        if chosen is not None:
            return chosen
        return applies and (current or counts.to_do > 0)

    def toggle(
        self,
        page: WorkbenchPage,
        *,
        current: bool,
        counts: AttentionCounts,
        open_: bool | None,
        applies: bool = True,
    ) -> None:
        """Open, close or flip one page."""
        now = self.expanded(page, current=current, counts=counts, applies=applies)
        self.chosen[page.id] = (not now) if open_ is None else open_


def heading_groups(page: WorkbenchPage) -> tuple[tuple[ModeloFormSection, ...], ...]:
    """The page's sections gathered under their headings, in the order each heading first appears.

    A layout that prints two parts of the page under one heading yields one
    group holding both, so the navigator names that heading once.
    """
    groups: dict[str, list[ModeloFormSection]] = {}
    for section in page.sections:
        groups.setdefault(section.heading.text, []).append(section)
    return tuple(tuple(group) for group in groups.values())


def _section_rows(
    index: int,
    page: WorkbenchPage,
    *,
    checked: Mapping[str, int],
    width: int,
    show_attention: bool,
    applies: bool,
) -> list[NavigatorRow]:
    """One line per heading of an open page; a page that does not apply draws its lines dimmed and uncounted."""
    return [
        _section_row(
            index,
            page,
            group,
            checked=checked,
            width=width,
            show_attention=show_attention,
            applies=applies,
        )
        for group in heading_groups(page)
    ]


def _section_row(
    index: int,
    page: WorkbenchPage,
    group: tuple[ModeloFormSection, ...],
    *,
    checked: Mapping[str, int],
    width: int,
    show_attention: bool,
    applies: bool,
) -> NavigatorRow:
    first = group[0]
    line = Text("    ")
    section_marks: list[WorkbenchMark] = []
    chips = Text()
    counts = _section_attention(group, page, checked, show_attention=show_attention, applies=applies)
    if counts is not None:
        chips = counts.text()
        line.append(f"{counts.mark.glyph} ")
        section_marks.append(counts.mark)
        section_marks.extend(counts.drawn())
    line.append(_fit(first.heading.text, _room(width, line, chips)))
    if chips.plain:
        line.append(" ").append_text(chips)
    if not applies:
        line.stylize(_DIMMED)
    return NavigatorRow(f"section:{index}:{first.id}", line, tuple(section_marks))


def _section_attention(
    group: tuple[ModeloFormSection, ...],
    page: WorkbenchPage,
    checked: Mapping[str, int],
    *,
    show_attention: bool,
    applies: bool,
) -> AttentionCounts | None:
    if not show_attention or not applies:
        return None
    counts = field_counts((item for section in group for item in section_fields(section)), checked)
    for section in group:
        records = page.records.get(section.id)
        if records is not None:
            counts = counts + records
    return counts


def navigator_rows(
    pages: tuple[WorkbenchPage, ...],
    *,
    current: int,
    state: NavigatorState,
    checked: Mapping[str, int],
    width: int,
    show_attention: bool,
    inapplicable: frozenset[str] = frozenset(),
    not_applying: str = "",
) -> tuple[NavigatorRow, ...]:
    """Lay the pages and their sections out as navigator lines, closed pages without their sections.

    A page in ``inapplicable`` is dimmed and says ``not_applying`` in place of
    its counts; it counts nothing as to do and starts closed. Without
    ``show_attention``, as on a declaration recorded as filed, no page counts
    anything, so none opens for something to do.
    """
    rows: list[NavigatorRow] = []
    for index, page in enumerate(pages):
        applies, counts, expanded = _navigator_page_state(
            index,
            page,
            current=current,
            state=state,
            checked=checked,
            show_attention=show_attention,
            inapplicable=inapplicable,
        )
        rows.append(
            _page_row(
                index,
                page,
                current=index == current,
                applies=applies,
                counts=counts,
                width=width,
                show_attention=show_attention,
                not_applying=not_applying,
                expanded=expanded,
            )
        )
        if expanded:
            rows.extend(
                _section_rows(index, page, checked=checked, width=width, show_attention=show_attention, applies=applies)
            )
    return tuple(rows)


def _navigator_page_state(
    index: int,
    page: WorkbenchPage,
    *,
    current: int,
    state: NavigatorState,
    checked: Mapping[str, int],
    show_attention: bool,
    inapplicable: frozenset[str],
) -> tuple[bool, AttentionCounts, bool]:
    applies = page.id not in inapplicable
    # Nothing counts on an inapplicable page or when attention is hidden for a filed declaration.
    counts = page_counts(page, checked) if applies and show_attention else AttentionCounts()
    expanded = (
        state.expanded(page, current=index == current, counts=counts, applies=applies) if page.sections else False
    )
    return applies, counts, expanded


def _page_row(
    index: int,
    page: WorkbenchPage,
    *,
    current: bool,
    applies: bool,
    counts: AttentionCounts,
    width: int,
    show_attention: bool,
    not_applying: str,
    expanded: bool,
) -> NavigatorRow:
    prompt, marks = _page_prefix(page, current=current, expanded=expanded)
    suffix, suffix_marks = _page_suffix(
        applies=applies,
        show_attention=show_attention,
        counts=counts,
        not_applying=not_applying,
    )
    marks.extend(suffix_marks)
    prompt = _finish_page_prompt(page, prompt, suffix, width=width, applies=applies)
    return NavigatorRow(f"page:{index}", prompt, tuple(marks))


def _page_prefix(
    page: WorkbenchPage,
    *,
    current: bool,
    expanded: bool,
) -> tuple[Text, list[WorkbenchMark]]:
    fold = (EXPANDED_MARK if expanded else COLLAPSED_MARK) if page.sections else None
    marks: list[WorkbenchMark] = []
    prompt = Text()
    prompt.append(f"{fold.glyph} " if fold is not None else "  ")
    if fold is not None:
        marks.append(fold)
    if current:
        prompt.append(f"{HERE_MARK.glyph} ")
        marks.append(HERE_MARK)

    return prompt, marks


def _page_suffix(
    *,
    applies: bool,
    show_attention: bool,
    counts: AttentionCounts,
    not_applying: str,
) -> tuple[Text, list[WorkbenchMark]]:
    suffix = Text(not_applying) if not applies else Text()
    marks: list[WorkbenchMark] = []
    if applies and show_attention:
        suffix, drawn = _suffix(counts)
        marks.extend(drawn)

    return suffix, marks


def _finish_page_prompt(
    page: WorkbenchPage,
    prompt: Text,
    suffix: Text,
    *,
    width: int,
    applies: bool,
) -> Text:
    start = len(prompt.plain)
    prompt.append(_fit(page.heading.text, _room(width, prompt, suffix)))
    if suffix.plain:
        prompt.append(" ").append_text(suffix)
    if not applies:
        prompt.stylize(_DIMMED, start)
    return prompt


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
    not_applying: str | None = None,
) -> tuple[Text, tuple[WorkbenchMark, ...]]:
    """The navigator in one line for a narrow terminal: the page, the section and what the page needs.

    ``not_applying`` is said, dimmed, in place of the counts of a page that does not apply this period.
    """
    page = pages[current]
    parts = [tr("tui.modelo.workbench.page_position", current=current + 1, total=len(pages)), page.heading.text]
    if section is not None:
        parts.append(section.heading.text)
    line = Text(" · ".join(parts))
    marks: tuple[WorkbenchMark, ...] = ()
    if not_applying is not None:
        line.append(" · ").append(not_applying, style=_DIMMED)
    elif show_attention:
        chips, marks = _suffix(page_counts(page, checked))
        line.append(" · ").append_text(chips)
    return line, marks


__all__ = [
    "NavigatorRow",
    "NavigatorState",
    "applicable_fields",
    "breadcrumb",
    "checked_boxes",
    "heading_groups",
    "inapplicable_pages",
    "looks_like_identifier",
    "navigator_rows",
    "page_counts",
    "page_title",
    "presented_form",
    "readable_text",
    "section_of",
    "section_title",
    "to_do_counts",
]
