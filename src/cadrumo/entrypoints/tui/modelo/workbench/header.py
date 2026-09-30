"""The workbench's status header in the filer's words: who, until when, how much, and what needs them.

Three lines, answering the filer's first questions from every state of the
workbench. The first names the declaration and its deadline, the last day of
the filing window with the days left, "today" or "passed". The second gives
the result: the direction in words, the amount and the box that settles it,
"not calculated yet" before the first calculation, an out-of-date mark while
changes wait to be applied, and one chip per attention level that has anything
in it. The third, the stepper and the next action, is :mod:`.progress`'s.

Everything shown is what the read model states. The direction comes from the
settlement box's declared disposition, never from the sign; when nothing
declares it the amount keeps its sign under the plain word "Result" and the
help says why. Money is formatted by the same function as the rows, the
magnitude where a word carries the direction. A declaration recorded as filed
shows its result undimmed, no deadline and no attention chips: nothing is left
to do on it here.

The header never drops the result to fit. A narrow terminal loses the modelo's
name before the deadline, and the result's box before any chip.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from rich.cells import cell_len

from .....application.modelo.value_presentation import format_casilla_value
from .....application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormResultDirection,
    ModeloWorkForm,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.result_disposition import ResultDisposition
from .casilla_list import CasillaListEntry, value_text
from .vocabulary import BLOCKS_MARK, CHECK_MARK, CONFIRM_MARK, MISSING_MARK, STALE_MARK, WorkbenchMark
from .wording import date_text, modelo_number, modelo_title, period_words

_MONEY: Final[str] = "money"
_PART_GAP: Final[str] = "   "
_WORD_GAP: Final[str] = "  "
_IDENTITY_SEPARATOR: Final[str] = " · "
_AMBER_DAYS: Final[int] = 7
_RED_DAYS: Final[int] = 3
_CALCULATE_KEY: Final[str] = "c"
_ISSUES_KEY: Final[str] = "i"
_REVIEW_KEY: Final[str] = "R"

_DIRECTION_LOCALE_KEYS: Final[Mapping[ModeloFormResultDirection, str]] = MappingProxyType(
    {
        ModeloFormResultDirection.TO_PAY: "tui.modelo.workbench.header.result.to_pay",
        ModeloFormResultDirection.TO_REFUND: "tui.modelo.workbench.header.result.to_refund",
        ModeloFormResultDirection.TO_CARRY_FORWARD: "tui.modelo.workbench.header.result.to_carry_forward",
        ModeloFormResultDirection.NIL: "tui.modelo.workbench.header.result.zero",
        ModeloFormResultDirection.UNKNOWN: "tui.modelo.workbench.header.result.unknown",
    }
)
"""The words for each direction the read model states; total over the directions."""

_NEGATIVE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.header.result.negative"
_CHOICE_PENDING_LOCALE_KEY: Final[str] = "tui.modelo.workbench.header.result.choice_pending"
_NOT_CALCULATED_LOCALE_KEY: Final[str] = "tui.modelo.workbench.header.result.not_calculated"
_FAILED_LOCALE_KEY: Final[str] = "tui.modelo.workbench.header.result.failed"
_STALE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.header.stale.changes"


class ChipLevel(StrEnum):
    """The attention levels the header counts, most urgent first."""

    BLOCKS = "blocks"
    MISSING = "missing"
    CONFIRM = "confirm"
    CHECK = "check"


_CHIP_MARKS: Final[Mapping[ChipLevel, WorkbenchMark]] = MappingProxyType(
    {
        ChipLevel.BLOCKS: BLOCKS_MARK,
        ChipLevel.MISSING: MISSING_MARK,
        ChipLevel.CONFIRM: CONFIRM_MARK,
        ChipLevel.CHECK: CHECK_MARK,
    }
)
_CHIP_LOCALE_KEYS: Final[Mapping[ChipLevel, str]] = MappingProxyType(
    {
        ChipLevel.BLOCKS: "tui.modelo.workbench.header.chip.blocks",
        ChipLevel.MISSING: "tui.modelo.workbench.header.chip.missing",
        ChipLevel.CONFIRM: "tui.modelo.workbench.header.chip.confirm",
        ChipLevel.CHECK: "tui.modelo.workbench.header.chip.check",
    }
)


class DeadlineTone(StrEnum):
    """How urgently the deadline reads; colour only reinforces the words."""

    NORMAL = "normal"
    SOON = "soon"
    URGENT = "urgent"
    MUTED = "muted"


@dataclass(frozen=True, slots=True)
class DeadlineView:
    """The deadline's words and how urgently they read."""

    text: str
    tone: DeadlineTone


@dataclass(frozen=True, slots=True)
class ResultView:
    """The result's words, with and without its box, and whether a stale mark dims it."""

    text: str
    short_text: str
    stale: str | None
    failed: bool
    help: tuple[str, ...]
    #: The direction in words and the amount it carries, once both are known.
    settled: tuple[str, str] | None = None

    @property
    def marks(self) -> tuple[WorkbenchMark, ...]:
        """The marks the result part draws."""
        return (STALE_MARK,) if self.stale is not None else ()


@dataclass(frozen=True, slots=True)
class AttentionChip:
    """One attention level with something in it, as the header counts it."""

    level: ChipLevel
    count: int

    @property
    def mark(self) -> WorkbenchMark:
        """The level's glyph and meaning, as every surface draws it."""
        return _CHIP_MARKS[self.level]

    @property
    def text(self) -> str:
        """The chip as the header shows it: the glyph, then its count in words."""
        return f"{self.mark.glyph} {tr(_CHIP_LOCALE_KEYS[self.level], count=self.count)}"


def identity_text(form: ModeloWorkForm, language: OutputLanguage, *, short: bool) -> str:
    """Name the declaration: its modelo, with its title unless ``short``, and its period in words."""
    modelo = str(form.modelo)
    name = modelo_number(modelo) if short else modelo_title(modelo, language)
    return f"{name}{_IDENTITY_SEPARATOR}{period_words(form.period)}"


def deadline_view(form: ModeloWorkForm, language: OutputLanguage, *, recorded: bool) -> DeadlineView | None:
    """Say when the filing window closes, or ``None`` once the declaration is recorded as filed.

    The date is the effective one, after any weekend or holiday shift; the days
    are the read model's own count, so the header and the calendar agree.
    """
    if recorded:
        return None
    deadline = form.deadline
    if deadline is None:
        return DeadlineView(tr("tui.modelo.workbench.header.no_deadline"), DeadlineTone.MUTED)
    closes = date_text(deadline.closes_on, language)
    if deadline.days_overdue is not None:
        return DeadlineView(tr("tui.modelo.workbench.header.deadline_passed", date=closes), DeadlineTone.URGENT)
    days = deadline.days_remaining or 0
    if days == 0:
        return DeadlineView(tr("tui.modelo.workbench.header.deadline_today", date=closes), DeadlineTone.URGENT)
    if days <= _RED_DAYS:
        tone = DeadlineTone.URGENT
    elif days <= _AMBER_DAYS:
        tone = DeadlineTone.SOON
    else:
        tone = DeadlineTone.NORMAL
    return DeadlineView(tr("tui.modelo.workbench.header.deadline", date=closes, days=days), tone)


def deadline_help(form: ModeloWorkForm, language: OutputLanguage, *, recorded: bool) -> str | None:
    """Explain a deadline a weekend or holiday moved, naming the usual date; ``None`` otherwise."""
    deadline = form.deadline
    if recorded or deadline is None or deadline.closes_on == deadline.nominal_closes_on:
        return None
    return tr(
        "tui.modelo.workbench.header.deadline_shifted_help",
        nominal=date_text(deadline.nominal_closes_on, language),
        date=date_text(deadline.closes_on, language),
    )


def _result_fields(form: ModeloWorkForm) -> dict[str, ModeloFormField]:
    wanted = {str(casilla_id) for casilla_id in form.result_addresses}
    if form.result is not None:
        wanted.add(str(form.result.casilla_id))
    fields: dict[str, ModeloFormField] = {}
    for field in form.fields():
        address = field.address
        if isinstance(address, ModeloFormCasillaAddressV1) and str(address.casilla_id) in wanted:
            fields.setdefault(str(address.casilla_id), field)
    return fields


def _money(value: Decimal, field: ModeloFormField | None, language: OutputLanguage) -> str:
    data_type = field.data_type if field is not None else _MONEY
    return format_casilla_value(value, data_type=data_type, language=language)


def _boxed(parts: list[str], box: str | None) -> tuple[str, str]:
    short = _WORD_GAP.join(parts)
    return (f"{short}{_WORD_GAP}[{box}]" if box else short), short


def _other_boxes_help(
    form: ModeloWorkForm, settling: str, fields: Mapping[str, ModeloFormField], language: OutputLanguage
) -> str | None:
    others = [
        fields[str(casilla_id)]
        for casilla_id in form.result_addresses
        if str(casilla_id) != settling and str(casilla_id) in fields
    ]
    if not others:
        return None
    named = ", ".join(
        f"[{field.box}] {value_text(CasillaListEntry(field), language)}" if field.box else field.label.text
        for field in others
    )
    return tr("tui.modelo.workbench.header.result.other_boxes", boxes=named)


def result_view(form: ModeloWorkForm, language: OutputLanguage, *, staged: int, recorded: bool) -> ResultView | None:
    """The result as the header states it, or ``None`` when the form names no result box at all.

    Without a declared settlement box the first result box in form order
    stands, under the plain word "Result".
    """
    fields = _result_fields(form)
    result = form.result
    if result is not None:
        settling = str(result.casilla_id)
    elif form.result_addresses:
        settling = str(form.result_addresses[0])
    else:
        return None
    field = fields.get(settling)
    box = (result.box if result is not None else None) or (field.box if field is not None else None)
    value = result.value if result is not None else _field_amount(field)
    direction = result.direction if result is not None else ModeloFormResultDirection.UNKNOWN
    stale = (
        f"{STALE_MARK.glyph} {tr(_STALE_LOCALE_KEY, count=staged, key=_REVIEW_KEY)}"
        if staged and not recorded
        else None
    )
    help_lines: list[str] = [tr("tui.modelo.workbench.header.own_calculation")]
    origin = field.origin if field is not None else None
    failed = origin is ModeloFormOrigin.CALCULATION_FAILED
    if failed:
        text = tr(_FAILED_LOCALE_KEY, key=_ISSUES_KEY)
        return ResultView(text=text, short_text=text, stale=stale, failed=True, help=tuple(help_lines))
    if form.calculation_revision_id is None or origin is ModeloFormOrigin.NOT_CALCULATED_YET or value is None:
        text = tr(_NOT_CALCULATED_LOCALE_KEY, key=_CALCULATE_KEY)
        return ResultView(text=text, short_text=text, stale=stale, failed=False, help=())
    disposition = result.disposition if result is not None else None
    settled: tuple[str, str] | None = None
    if result is not None and result.election_may_change:
        settled = (tr(_CHOICE_PENDING_LOCALE_KEY), _money(abs(value), field, language))
        full, short = _boxed(list(settled), box)
    elif disposition is ResultDisposition.RESULTADO_A_DEDUCIR:
        full, short = _boxed([tr(_NEGATIVE_LOCALE_KEY)], box)
    elif direction is ModeloFormResultDirection.UNKNOWN:
        settled = (tr(_DIRECTION_LOCALE_KEYS[direction]), _money(value, field, language))
        full, short = _boxed(list(settled), box)
        help_lines.append(tr("tui.modelo.workbench.header.result.direction_unknown_help"))
    elif direction is ModeloFormResultDirection.NIL:
        full, short = _boxed([tr(_DIRECTION_LOCALE_KEYS[direction])], box)
    else:
        settled = (tr(_DIRECTION_LOCALE_KEYS[direction]), _money(abs(value), field, language))
        full, short = _boxed(list(settled), box)
    if value < 0 and settled is not None and direction is not ModeloFormResultDirection.UNKNOWN and box:
        help_lines.append(
            tr("tui.modelo.workbench.header.result.sign_help", box=box, value=_money(value, field, language))
        )
    other = _other_boxes_help(form, settling, fields, language)
    if other is not None:
        help_lines.append(other)
    return ResultView(text=full, short_text=short, stale=stale, failed=False, help=tuple(help_lines), settled=settled)


def _field_amount(field: ModeloFormField | None) -> Decimal | None:
    if field is None or isinstance(field.value, bool) or not isinstance(field.value, Decimal | int):
        return None
    return Decimal(field.value)


def is_result_field(form: ModeloWorkForm, field: ModeloFormField) -> bool:
    """Whether ``field`` is one of the boxes that state the declaration's result."""
    address = field.address
    if not isinstance(address, ModeloFormCasillaAddressV1):
        return False
    settling = form.result.casilla_id if form.result is not None else None
    return address.casilla_id == settling or address.casilla_id in form.result_addresses


def attention_chips(form: ModeloWorkForm, *, recorded: bool) -> tuple[AttentionChip, ...]:
    """One chip per attention level with anything in it, counted from the form; none once recorded.

    What blocks is every blocking finding of the last check, and a result box
    the calculation could not produce when no finding already names it.
    """
    if recorded:
        return ()
    blocking = [issue for issue in form.issues if issue.attention is ModeloFormAttention.BLOCKS]
    blocks = len(blocking)
    view_fields = _result_fields(form)
    named = {issue.box for issue in blocking if issue.box is not None}
    blocks += sum(
        1
        for field in view_fields.values()
        if field.origin is ModeloFormOrigin.CALCULATION_FAILED
        and field.box not in named
        and is_result_field(form, field)
    )
    counts = {
        ChipLevel.BLOCKS: blocks,
        ChipLevel.MISSING: form.counts.needs_input,
        ChipLevel.CONFIRM: form.counts.default_to_confirm,
        ChipLevel.CHECK: sum(1 for issue in form.issues if issue.attention is ModeloFormAttention.CHECK),
    }
    return tuple(AttentionChip(level, count) for level, count in counts.items() if count)


@dataclass(frozen=True, slots=True)
class ResultLine:
    """The parts of the result line that fit one width: the result, the stale mark and the chips kept."""

    result: str
    stale: str | None
    chips: tuple[AttentionChip, ...]

    def text(self) -> str:
        """The line as one string."""
        return _PART_GAP.join(part for part in (self.result, self.stale, *(chip.text for chip in self.chips)) if part)


def fit_result_line(view: ResultView, chips: tuple[AttentionChip, ...], width: int) -> ResultLine:
    """Keep what fits in ``width``: the box goes first, then the least urgent chips; the result stays."""
    line = ResultLine(view.text, view.stale, chips)
    if cell_len(line.text()) <= width:
        return line
    line = ResultLine(view.short_text, view.stale, chips)
    kept = list(chips)
    while kept and cell_len(line.text()) > width:
        kept.pop()
        line = ResultLine(view.short_text, view.stale, tuple(kept))
    return line


def fit_identity(form: ModeloWorkForm, language: OutputLanguage, deadline: DeadlineView | None, width: int) -> str:
    """The declaration's name at ``width``: with the modelo's title when it fits beside the deadline."""
    full = identity_text(form, language, short=False)
    beside = cell_len(deadline.text) + len(_PART_GAP) if deadline is not None else 0
    if cell_len(full) + beside <= width:
        return full
    return identity_text(form, language, short=True)


def result_line_text(form: ModeloWorkForm, language: OutputLanguage, *, staged: int, recorded: bool) -> str:
    """The header's result line as one string, for a dialog that covers the header to repeat."""
    view = result_view(form, language, staged=staged, recorded=recorded)
    chips = attention_chips(form, recorded=recorded)
    if view is None:
        return _PART_GAP.join(chip.text for chip in chips)
    return ResultLine(view.text, view.stale, chips).text()


__all__ = [
    "AttentionChip",
    "ChipLevel",
    "DeadlineTone",
    "DeadlineView",
    "ResultLine",
    "ResultView",
    "attention_chips",
    "deadline_help",
    "deadline_view",
    "fit_identity",
    "fit_result_line",
    "identity_text",
    "is_result_field",
    "result_line_text",
    "result_view",
]
