"""The workbench's status header in the filer's words: who, until when, how much, and what needs them.

Three lines, answering the filer's first questions from every state of the
workbench. The first names the declaration and its deadline, the last day of
the filing window with the days left, "today" or "passed". The second gives
the result: the direction in words, the amount and the box that settles it,
"not calculated yet" before the first calculation, an out-of-date mark while
changes wait to be applied or after the filer's records changed under the
calculation, and one chip per attention level that has anything in it. The
third, the stepper and the next action, is :mod:`.progress`'s.

Everything shown is what the read model states, through
:mod:`~cadrumo.application.modelo.work_form_header`: the counts, the result and
its words, the deadline and how urgently it reads, and the latest file are
decided there once, for every frontend, and drawn here from the served views
themselves. This module adds only what a terminal owns: the marks, the keys
that act, the out-of-date mark of changes held here unapplied, and choosing
among the served words the ones that fit the screen's width.

The header never drops the result to fit, and never runs past the screen's
edge. A narrow terminal loses the modelo's name before the deadline, and the
result's box before any chip. When the result and its chips still do not fit
one line, the result takes a line of its own, in fewer words if it must (a
choice still to be made reads as its two directions and the amount, the rest
said in the help), and the out-of-date mark and the chips share the next.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from rich.cells import cell_len
from textual.content import Content

from .....application.modelo.work_form_findings import ModeloFormAttention
from .....application.modelo.work_form_header import (
    ModeloFormAttentionCount,
    ModeloFormDeadlineView,
    ModeloFormFileView,
    ModeloFormResultState,
    ModeloFormResultView,
    attention_counts,
)
from .....application.modelo.work_form_header import file_view as form_file_view
from .....application.modelo.work_form_header import result_view as form_result_view
from .....application.modelo.work_form_models import ModeloWorkForm
from .....application.modelo.work_form_wording import modelo_number, modelo_title, period_words
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from ...components.cell_text import ellipsize
from .issue_scale import levels_marked
from .vocabulary import (
    BLOCKS_MARK,
    CHECK_MARK,
    CONFIRM_MARK,
    LIMITATION_MARK,
    MISSING_MARK,
    STALE_MARK,
    WorkbenchMark,
)

_PART_GAP: Final[str] = "   "
_IDENTITY_SEPARATOR: Final[str] = " · "
_CALCULATE_KEY: Final[str] = "c"
_ISSUES_KEY: Final[str] = "i"
_REVIEW_KEY: Final[str] = "R"
_EXPORT_KEY: Final[str] = "e"
_RESULT_KEYS: Final[Mapping[ModeloFormResultState, str]] = MappingProxyType(
    {ModeloFormResultState.NOT_CALCULATED: _CALCULATE_KEY, ModeloFormResultState.FAILED: _ISSUES_KEY}
)
"""The key a result with no figure names: calculating it, or opening the issues that say why it failed."""
_STALE_LOCALE_KEY: Final[str] = "workspace.modelo.header.stale.changes"

_CHIP_MARKS: Final[Mapping[ModeloFormAttention, WorkbenchMark]] = MappingProxyType(
    {
        ModeloFormAttention.BLOCKS: BLOCKS_MARK,
        ModeloFormAttention.MISSING: MISSING_MARK,
        ModeloFormAttention.CONFIRM: CONFIRM_MARK,
        ModeloFormAttention.CHECK: CHECK_MARK,
        ModeloFormAttention.LIMITATION: LIMITATION_MARK,
    }
)
URGENT_CHIPS: Final[frozenset[ModeloFormAttention]] = frozenset(
    {ModeloFormAttention.BLOCKS, ModeloFormAttention.MISSING}
)
"""Chips the result line never drops to keep itself on one line: it takes a second line first."""


@dataclass(frozen=True, slots=True)
class HeaderResult:
    """The result the read model serves, as the header draws it, with this terminal's out-of-date mark.

    ``served`` is the read model's view itself. A result with no figure is
    drawn with the key that calculates it, or that opens the issues saying
    why it could not be; ``stale`` is the out-of-date mark, which names the
    changes held here unapplied before the read model's own.
    """

    served: ModeloFormResultView
    stale: str | None

    def _keyed(self, words: str) -> str:
        key = _RESULT_KEYS.get(self.served.state)
        return words if key is None else f"{words} [{key}]"

    @property
    def text(self) -> str:
        """The served words that name the box."""
        return self._keyed(self.served.text)

    @property
    def short_text(self) -> str:
        """The served words without the box."""
        return self._keyed(self.served.short_text)

    @property
    def briefest(self) -> str:
        """The fewest served words that still state the result."""
        return self._keyed(self.served.brief_text)

    @property
    def marks(self) -> tuple[WorkbenchMark, ...]:
        """The marks the result part draws."""
        return (STALE_MARK,) if self.stale is not None else ()


def file_text(view: ModeloFormFileView) -> str:
    """The served words for the latest file; one that is out of date names the key that creates it again."""
    return view.words if view.current else f"{view.words} [{_EXPORT_KEY}]"


@dataclass(frozen=True, slots=True)
class AttentionChip:
    """One attention level with something in it, as the read model counts it.

    A ``brief`` chip keeps its glyph and count without the words, for a line
    too narrow to say every level in full: the level and how many it holds
    still read, and its accessible meaning is the glyph's.
    """

    tally: ModeloFormAttentionCount
    brief: bool = False

    @property
    def level(self) -> ModeloFormAttention:
        """The level counted."""
        return self.tally.level

    @property
    def count(self) -> int:
        """How many things the level holds."""
        return self.tally.count

    @property
    def mark(self) -> WorkbenchMark:
        """The level's glyph and meaning, as every surface draws it."""
        return _CHIP_MARKS[self.level]

    @property
    def text(self) -> str:
        """The chip as the header shows it: the glyph, then its count in words, or the bare count when brief."""
        if self.brief:
            return f"{self.mark.glyph} {self.tally.count}"
        return f"{self.mark.glyph} {self.tally.words}"

    def briefly(self) -> AttentionChip:
        """The same chip with its glyph and count only."""
        return AttentionChip(self.tally, brief=True)

    @property
    def content(self) -> Content:
        """The chip as drawn: its level's glyph in that level's colour, as every surface draws it."""
        return levels_marked(self.text)


def identity_text(form: ModeloWorkForm, language: OutputLanguage, *, short: bool) -> str:
    """Name the declaration: its modelo, with its title unless ``short``, and its period in words."""
    modelo = str(form.modelo)
    name = modelo_number(modelo) if short else modelo_title(modelo, language)
    return f"{name}{_IDENTITY_SEPARATOR}{period_words(form.period)}"


def deadline_text(form: ModeloWorkForm, language: OutputLanguage, view: ModeloFormDeadlineView, width: int) -> str:
    """The served deadline, in its fewer served words where it would not fit beside the declaration's number."""
    if cell_len(identity_text(form, language, short=True)) + cell_len(view.text) + len(_PART_GAP) > width:
        return view.short_text
    return view.text


def _result_stale_notice(view: ModeloFormResultView, *, staged: int, recorded: bool) -> str | None:
    if staged and not recorded:
        return f"{STALE_MARK.glyph} {tr(_STALE_LOCALE_KEY, count=staged)} [{_REVIEW_KEY}]"
    if view.out_of_date_words is not None:
        return f"{STALE_MARK.glyph} {view.out_of_date_words} [{_CALCULATE_KEY}]"
    return None


def header_result(
    form: ModeloWorkForm, language: OutputLanguage, *, staged: int, recorded: bool
) -> HeaderResult | None:
    """The read model's result, marked out of date while ``staged`` changes wait; ``None`` with no result box.

    Changes held here unapplied are known only to this frontend, so their mark
    is added here.
    """
    view = form_result_view(form, language, recorded=recorded)
    if view is None:
        return None
    return HeaderResult(view, _result_stale_notice(view, staged=staged, recorded=recorded))


def attention_chips(
    form: ModeloWorkForm, *, recorded: bool, language: OutputLanguage | None = None
) -> tuple[AttentionChip, ...]:
    """One chip per level the read model counts anything in, most urgent first; none once recorded."""
    spoken = language if language is not None else OutputLanguage(output_language())
    return tuple(AttentionChip(count) for count in attention_counts(form, spoken, recorded=recorded))


@dataclass(frozen=True, slots=True)
class ResultLine:
    """The parts of the result line that fit one width: the result, the stale mark and the chips kept.

    ``stacked`` puts the result on a line of its own, above the stale mark and the chips.
    """

    result: str
    stale: str | None
    chips: tuple[AttentionChip, ...]
    stacked: bool = False
    #: The latest file for the AEAT in words, kept whatever the width, as the stale mark is.
    file: str | None = None

    def marks_text(self) -> str:
        """The stale mark, the file and the chips as one string, as the second line of a stacked result shows them."""
        parts = (self.stale, self.file, *(chip.text for chip in self.chips))
        return _PART_GAP.join(part for part in parts if (part is not None and part))

    def chips_content(self) -> Content:
        """The chips kept, as drawn side by side: a blocker's in the error colour."""
        return Content(_PART_GAP).join(chip.content for chip in self.chips)

    def text(self) -> str:
        """The line as one string."""
        return _PART_GAP.join(part for part in (self.result, self.marks_text()) if part)


def fit_result_line(
    view: HeaderResult, chips: tuple[AttentionChip, ...], width: int, *, file: str | None = None
) -> ResultLine:
    """Keep what fits in ``width``, never running past it; the result, the stale mark and the file always stay.

    On one line the box goes first, then the chips worth checking or
    confirming, least urgent first; the result's words are never cut there.
    When the words do not fit one line beside what blocks or is missing, the
    result takes a line of its own in the fullest words that fit, and the
    stale mark, the file and the chips share the line below, the least urgent
    chips going first there.
    """
    line = ResultLine(view.text, view.stale, chips, file=file)
    if cell_len(line.text()) <= width:
        return line
    line = ResultLine(view.short_text, view.stale, chips, file=file)
    kept = list(chips)
    while kept and kept[-1].level not in URGENT_CHIPS and cell_len(line.text()) > width:
        kept.pop()
        line = ResultLine(view.short_text, view.stale, tuple(kept), file=file)
    if cell_len(line.text()) <= width:
        return line
    result = next(
        (text for text in (view.text, view.short_text, view.briefest) if cell_len(text) <= width),
        ellipsize(view.briefest, width),
    )
    below = ResultLine(result, view.stale, chips, stacked=True, file=file)
    kept = list(chips)
    while kept and cell_len(below.marks_text()) > width:
        kept.pop()
        below = ResultLine(result, view.stale, tuple(kept), stacked=True, file=file)
    return below


@dataclass(frozen=True, slots=True)
class IdentityLine:
    """The complete declaration identity, with the deadline below when they cannot share a line."""

    text: str
    stacked: bool = False


def fit_identity(form: ModeloWorkForm, language: OutputLanguage, deadline: str | None, width: int) -> IdentityLine:
    """Keep the Modelo, worded period and year; the descriptive title gives way before a second line."""
    full = identity_text(form, language, short=False)
    beside = cell_len(deadline) + len(_PART_GAP) if deadline is not None else 0
    if cell_len(full) + beside <= width:
        return IdentityLine(full)
    short = identity_text(form, language, short=True)
    return IdentityLine(short, stacked=cell_len(short) + beside > width)


@dataclass(frozen=True, slots=True)
class StatusLine:
    """The header's result line, for a dialog that covers the header to repeat at its top.

    A dialog has one line for it, so it never wraps: at any width the result
    keeps its fewest words and the least urgent chips go first, and each chip
    keeps its level's colour.
    """

    view: HeaderResult | None
    chips: tuple[AttentionChip, ...]
    file: str | None = None

    def _line(self, result: str, chips: tuple[AttentionChip, ...]) -> ResultLine:
        return ResultLine(result, None if self.view is None else self.view.stale, chips, file=self.file)

    def text(self) -> str:
        """The whole line as one string, at any width."""
        return self._line("" if self.view is None else self.view.text, self.chips).text()

    def fitted(self, width: int) -> ResultLine:
        """The line within ``width`` cells on one line: the fullest result that fits, then as many chips as fit.

        Before any chip is dropped, the least urgent chips give up their words
        and keep their glyph and count, so every level still reads.
        """
        view = self.view
        results = ("",) if view is None else (view.text, view.short_text, view.briefest)
        for result in results:
            kept = list(self.chips)
            line = self._line(result, tuple(kept))
            worded = len(kept)
            while worded and cell_len(line.text()) > width:
                worded -= 1
                kept[worded] = kept[worded].briefly()
                line = self._line(result, tuple(kept))
            while kept and cell_len(line.text()) > width:
                kept.pop()
                line = self._line(result, tuple(kept))
            if cell_len(line.text()) <= width:
                return line
        return self._line(ellipsize(results[-1], width), ())

    def content(self, width: int) -> Content:
        """The line as drawn within ``width`` cells: each chip in its level's colour."""
        line = self.fitted(width)
        lead = _PART_GAP.join(part for part in (line.result, line.stale, line.file) if (part is not None and part))
        if not line.chips:
            return Content(ellipsize(lead, width))
        return Content(_PART_GAP).join([Content(lead), line.chips_content()] if lead else [line.chips_content()])


def status_line(form: ModeloWorkForm, language: OutputLanguage, *, staged: int, recorded: bool) -> StatusLine | None:
    """The header's result line for a dialog to repeat, or ``None`` when it would say nothing."""
    view = header_result(form, language, staged=staged, recorded=recorded)
    chips = attention_chips(form, recorded=recorded, language=language)
    file = form_file_view(form, language, recorded=recorded)
    line = StatusLine(view, chips, None if file is None else file_text(file))
    return line if line.text() else None


__all__ = [
    "AttentionChip",
    "HeaderResult",
    "ResultLine",
    "StatusLine",
    "attention_chips",
    "deadline_text",
    "file_text",
    "fit_identity",
    "fit_result_line",
    "header_result",
    "identity_text",
    "status_line",
]
