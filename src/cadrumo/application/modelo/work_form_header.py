"""What a declaration's header says: what needs the filer, the result, the deadline and the latest file.

Every frontend shows the same answers to a filer's first questions about a
declaration, so they are decided here, once, from the form and its lifecycle:

* the attention counts, one per level with anything in it, counted with the
  same functions as the next step, so a count and the next action never
  disagree;
* the result: the box that stands as it (the declared settlement box, else
  the first result box in form order under the plain word "Result"), its
  direction in words from the box's declared disposition and never from the
  sign, the amount, and whether it is not calculated yet, could not be
  calculated or waits on the filer's refund election;
* the deadline in words, with how urgently it reads and why a weekend or
  holiday moved it;
* the latest file for the AEAT, and whether it no longer matches the
  declaration;
* why the file for the AEAT is withheld, if it is.

A declaration recorded as filed shows its result and nothing else: no
deadline, no counts, no file and no hold, since nothing is left to do on it.

Every sentence is rendered in the language given and names no key or button:
a frontend that offers a way to act adds it beside the words.

Changes a frontend holds unapplied make the result out of date; only that
frontend knows them, so it adds that mark itself, as it offers
:attr:`~.work_form_next_step.ModeloFormNextAction.APPLY` itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from .value_presentation import format_casilla_value
from .work_form_findings import ModeloFormAttention
from .work_form_models import ModeloFormField, ModeloFormOrigin, ModeloFormResultDirection, ModeloWorkForm
from .work_form_next_step import blocking_count, check_count, confirm_count, missing_count, result_fields
from .work_form_wording import date_text, day_text, field_value_text, origin_words

SOON_DAYS: Final[int] = 7
"""A deadline this many days away or fewer reads as soon."""
URGENT_DAYS: Final[int] = 3
"""A deadline this many days away or fewer reads as urgent, as does one that closes today or passed."""

_MONEY: Final[str] = "money"
_WORD_GAP: Final[str] = "  "
_OWN_CALCULATION_LOCALE_KEY: Final[str] = "workspace.modelo.header.own_calculation"
_CHOICE_PENDING_LOCALE_KEY: Final[str] = "workspace.modelo.header.result.choice_pending"
_CHOICE_PENDING_SHORT_LOCALE_KEY: Final[str] = "workspace.modelo.header.result.choice_pending_short"
_SIGN_HELP_LOCALE_KEY: Final[str] = "workspace.modelo.header.result.sign_help"
_NOT_APPLICABLE_VALUE_LOCALE_KEY: Final[str] = "workspace.modelo.value.not_applicable"

_DIRECTION_LOCALE_KEYS: Final[Mapping[ModeloFormResultDirection, str]] = MappingProxyType(
    {
        ModeloFormResultDirection.TO_PAY: "workspace.modelo.header.result.to_pay",
        ModeloFormResultDirection.TO_REFUND: "workspace.modelo.header.result.to_refund",
        ModeloFormResultDirection.TO_CARRY_FORWARD: "workspace.modelo.header.result.to_carry_forward",
        ModeloFormResultDirection.TO_DEDUCT_LATER: "workspace.modelo.header.result.negative_carried",
        ModeloFormResultDirection.NEGATIVE: "workspace.modelo.header.result.negative",
        ModeloFormResultDirection.NIL: "workspace.modelo.header.result.zero",
        ModeloFormResultDirection.UNKNOWN: "workspace.modelo.header.result.unknown",
    }
)
"""The words for each direction the read model states; total over the directions."""

_COUNTED_LEVEL_LOCALE_KEYS: Final[Mapping[ModeloFormAttention, str]] = MappingProxyType(
    {
        ModeloFormAttention.BLOCKS: "workspace.modelo.header.chip.blocks",
        ModeloFormAttention.MISSING: "workspace.modelo.header.chip.missing",
        ModeloFormAttention.CONFIRM: "workspace.modelo.header.chip.confirm",
        ModeloFormAttention.CHECK: "workspace.modelo.header.chip.check",
    }
)
"""The attention levels the header counts, most urgent first, with the words for each count."""


class ModeloFormAttentionCount(BaseModel):
    """One attention level with something in it, counted as the next step counts it."""

    model_config = STRICT_FROZEN_CONFIG

    level: ModeloFormAttention
    count: int = Field(gt=0)
    #: The count in words, such as "blocking: 2".
    words: str = Field(min_length=1)


class ModeloFormResultState(StrEnum):
    """What the result can say yet."""

    #: The result's figure is known and said with its direction.
    STATED = "stated"
    #: The figure is known, but the filer's refund election still decides how it settles.
    CHOICE_PENDING = "choice_pending"
    #: Nothing has been calculated for the result box yet.
    NOT_CALCULATED = "not_calculated"
    #: The last calculation could not produce the result box.
    FAILED = "failed"


_RESULT_LOCALE_KEYS: Final[Mapping[ModeloFormResultState, str]] = MappingProxyType(
    {
        ModeloFormResultState.NOT_CALCULATED: "workspace.modelo.header.result.not_calculated",
        ModeloFormResultState.FAILED: "workspace.modelo.header.result.failed",
    }
)
"""The sentence for a result with no figure: it waits on a calculation, or the last one could not produce it."""
_RECALCULATE_LOCALE_KEY: Final[str] = "workspace.modelo.header.stale.recalculate"


class ModeloFormResultView(BaseModel):
    """The declaration's result as the header states it.

    ``text`` names the box, ``short_text`` drops it and ``brief_text`` is the
    fewest words that still state the result; a result with no figure says why
    in all three. ``words`` and ``amount_text`` are the direction and the
    amount it carries, set together where the result states both.
    """

    model_config = STRICT_FROZEN_CONFIG

    state: ModeloFormResultState
    #: The box that stands as the result.
    casilla_id: CasillaId
    box: str | None
    #: Whether the registry names this box as the one that settles the declaration.
    settles: bool
    direction: ModeloFormResultDirection
    words: str | None = None
    amount_text: str | None = None
    text: str = Field(min_length=1)
    short_text: str = Field(min_length=1)
    brief_text: str = Field(min_length=1)
    #: What the header's help says about the result, first that it is Cadrumo's own calculation.
    help: tuple[str, ...] = ()
    #: That the filer's records changed after the calculation, so it must be calculated again.
    out_of_date_words: str | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _direction_with_its_amount(self) -> Self:
        if (self.words is None) != (self.amount_text is None):
            raise ValueError("a result's direction words and its amount are set together")
        return self


class ModeloFormDeadlineTone(StrEnum):
    """How urgently the deadline reads; colour only reinforces the words."""

    NORMAL = "normal"
    SOON = "soon"
    URGENT = "urgent"
    #: No deadline is on record for the declaration.
    MUTED = "muted"


class ModeloFormDeadlineView(BaseModel):
    """The deadline in words, how urgently it reads, and why it moved."""

    model_config = STRICT_FROZEN_CONFIG

    text: str = Field(min_length=1)
    #: Fewer words, for a line too narrow for ``text``; the same as ``text`` when it has none fewer.
    short_text: str = Field(min_length=1)
    tone: ModeloFormDeadlineTone
    #: Why a weekend or holiday moved the deadline, naming the usual date; ``None`` when it did not move.
    help: str | None = None


class ModeloFormFileView(BaseModel):
    """The latest file for the AEAT, and whether it no longer matches the declaration.

    ``words`` say when it was created or, for a file made from an earlier
    calculation, that it is out of date and is to be created again.
    """

    model_config = STRICT_FROZEN_CONFIG

    exported_at: datetime
    #: The day the file was created, in the filer's language.
    created_on: str = Field(min_length=1)
    current: bool
    words: str = Field(min_length=1)


class ModeloFormExportHoldReason(StrEnum):
    """Why the file for the AEAT is withheld, most pressing first."""

    #: Something blocks filing, found by the check or by the calculation.
    BLOCKS = "blocks"
    #: An assumed value waits for the filer to confirm it.
    CONFIRM = "confirm"
    #: The current calculation has not been checked, or there is none.
    VERIFY = "verify"


_HOLD_LOCALE_KEYS: Final[Mapping[ModeloFormExportHoldReason, str]] = MappingProxyType(
    {
        ModeloFormExportHoldReason.BLOCKS: "workspace.modelo.export.resolve_first",
        ModeloFormExportHoldReason.CONFIRM: "workspace.modelo.export.confirm_first",
        ModeloFormExportHoldReason.VERIFY: "workspace.modelo.export.verify_first",
    }
)


class ModeloFormExportHold(BaseModel):
    """Why the file for the AEAT, and recording the filing, are withheld, with what the reason counts."""

    model_config = STRICT_FROZEN_CONFIG

    reason: ModeloFormExportHoldReason
    #: What blocks or waits to be confirmed, as the attention counts count it; zero for a check still to run.
    count: int = Field(ge=0)
    #: Why, in the filer's language.
    words: str = Field(min_length=1)


class ModeloFormHeader(BaseModel):
    """Everything a declaration's header states, decided once for every frontend."""

    model_config = STRICT_FROZEN_CONFIG

    attention: tuple[ModeloFormAttentionCount, ...] = ()
    #: ``None`` when the form names no result box at all.
    result: ModeloFormResultView | None = None
    #: ``None`` once the declaration is recorded as filed.
    deadline: ModeloFormDeadlineView | None = None
    #: ``None`` when no file was ever created, or once the declaration is recorded as filed.
    file: ModeloFormFileView | None = None
    #: ``None`` when nothing withholds the file, or once the declaration is recorded as filed.
    export_hold: ModeloFormExportHold | None = None


def form_recorded(form: ModeloWorkForm, *, filed: bool) -> bool:
    """Whether the declaration is recorded as filed, by its lifecycle or by the form's own filing record."""
    return filed or form.filing is not None


def attention_counts(
    form: ModeloWorkForm, language: OutputLanguage, *, recorded: bool
) -> tuple[ModeloFormAttentionCount, ...]:
    """One count per attention level with anything in it, most urgent first; none once recorded.

    What blocks is counted by :func:`~.work_form_next_step.blocking_count`.
    What is missing or assumed on a page that does not apply this period is
    not counted: nothing there is asked of the filer.
    """
    if recorded:
        return ()
    counts = {
        ModeloFormAttention.BLOCKS: blocking_count(form),
        ModeloFormAttention.MISSING: missing_count(form),
        ModeloFormAttention.CONFIRM: confirm_count(form),
        ModeloFormAttention.CHECK: check_count(form),
    }
    return tuple(
        ModeloFormAttentionCount(
            level=level, count=count, words=tr(_COUNTED_LEVEL_LOCALE_KEYS[level], count=count, locale=language.value)
        )
        for level, count in counts.items()
        if count
    )


def deadline_tone(days_remaining: int | None, days_overdue: int | None) -> ModeloFormDeadlineTone:
    """How urgently a deadline reads from the days left or overdue; muted when neither is known."""
    if days_overdue is not None:
        return ModeloFormDeadlineTone.URGENT
    if days_remaining is None:
        return ModeloFormDeadlineTone.MUTED
    if days_remaining <= URGENT_DAYS:
        return ModeloFormDeadlineTone.URGENT
    if days_remaining <= SOON_DAYS:
        return ModeloFormDeadlineTone.SOON
    return ModeloFormDeadlineTone.NORMAL


def deadline_words(
    closes_on: date, days_remaining: int | None, days_overdue: int | None, language: OutputLanguage
) -> str:
    """The deadline in words: its date with the days left, "today", or that it passed."""
    locale = language.value
    closes = date_text(closes_on, language)
    if days_overdue is not None:
        return tr("workspace.modelo.header.deadline_passed", date=closes, locale=locale)
    days = days_remaining or 0
    if days == 0:
        return tr("workspace.modelo.header.deadline_today", date=closes, locale=locale)
    return tr("workspace.modelo.header.deadline", date=closes, days=days, locale=locale)


def deadline_view(form: ModeloWorkForm, language: OutputLanguage, *, recorded: bool) -> ModeloFormDeadlineView | None:
    """Say when the filing window closes, or ``None`` once the declaration is recorded as filed.

    The date is the effective one, after any weekend or holiday shift; the days
    are the read model's own count, so the header and the calendar agree.
    """
    if recorded:
        return None
    locale = language.value
    deadline = form.deadline
    if deadline is None:
        return ModeloFormDeadlineView(
            text=tr("workspace.modelo.header.no_deadline", locale=locale),
            short_text=tr("workspace.modelo.header.no_deadline_short", locale=locale),
            tone=ModeloFormDeadlineTone.MUTED,
        )
    closes = date_text(deadline.closes_on, language)
    days = deadline.days_remaining or 0
    text = deadline_words(deadline.closes_on, deadline.days_remaining, deadline.days_overdue, language)
    shifted = (
        None
        if deadline.closes_on == deadline.nominal_closes_on
        else tr(
            "workspace.modelo.header.deadline_shifted_help",
            nominal=date_text(deadline.nominal_closes_on, language),
            date=closes,
            locale=locale,
        )
    )
    return ModeloFormDeadlineView(
        text=text,
        short_text=text,
        tone=deadline_tone(days, deadline.days_overdue),
        help=shifted,
    )


def file_view(form: ModeloWorkForm, language: OutputLanguage, *, recorded: bool) -> ModeloFormFileView | None:
    """Say when the latest file for the AEAT was created, or that it is out of date; ``None`` when there is none.

    Nothing is said once the declaration is recorded as filed.
    """
    export = form.last_export
    if export is None or recorded:
        return None
    day = day_text(export.exported_at, language)
    key = "workspace.modelo.header.file_created" if export.current else "workspace.modelo.header.file_out_of_date"
    return ModeloFormFileView(
        exported_at=export.exported_at,
        created_on=day,
        current=export.current,
        words=tr(key, date=day, locale=language.value),
    )


def export_hold(
    form: ModeloWorkForm, language: OutputLanguage, *, verified: bool, recorded: bool
) -> ModeloFormExportHold | None:
    """Why the file for the AEAT is withheld, or ``None`` when nothing withholds it.

    Something that blocks filing comes first, then an assumed value, then a
    calculation still to check. A declaration recorded as filed holds nothing
    back: there is nothing left to create.
    """
    if recorded:
        return None
    blocking = blocking_count(form)
    if blocking:
        return _hold(ModeloFormExportHoldReason.BLOCKS, blocking, language)
    assumed = confirm_count(form)
    if assumed:
        return _hold(ModeloFormExportHoldReason.CONFIRM, assumed, language)
    if not verified or form.calculation_revision_id is None:
        return _hold(ModeloFormExportHoldReason.VERIFY, 0, language)
    return None


def _hold(reason: ModeloFormExportHoldReason, count: int, language: OutputLanguage) -> ModeloFormExportHold:
    words = tr(_HOLD_LOCALE_KEYS[reason], count=count, locale=language.value)
    return ModeloFormExportHold(reason=reason, count=count, words=words)


@dataclass(frozen=True, slots=True)
class _SelectedResult:
    settling: str
    fields: Mapping[str, ModeloFormField]
    field: ModeloFormField | None
    casilla_id: CasillaId
    box: str | None
    value: Decimal | None
    direction: ModeloFormResultDirection
    settles: bool
    election_may_change: bool


@dataclass(frozen=True, slots=True)
class _Presentation:
    text: str
    short_text: str
    words: str | None = None
    amount_text: str | None = None
    brief_text: str | None = None


def _money(value: Decimal, language: OutputLanguage) -> str:
    """A settlement amount, as money whatever type its box declares: a result is always an amount to pay or get."""
    return format_casilla_value(value, data_type=_MONEY, language=language)


def _boxed(parts: list[str], box: str | None) -> tuple[str, str]:
    short = _WORD_GAP.join(parts)
    return (f"{short}{_WORD_GAP}[{box}]" if (box is not None and box) else short), short


def _selected_result(form: ModeloWorkForm) -> _SelectedResult | None:
    fields = result_fields(form)
    result = form.result
    if result is not None:
        casilla_id = result.casilla_id
    elif form.result_addresses:
        casilla_id = form.result_addresses[0]
    else:
        return None
    settling = str(casilla_id)
    field = fields.get(settling)
    return _SelectedResult(
        settling=settling,
        fields=fields,
        field=field,
        casilla_id=casilla_id,
        box=(result.box if result is not None else None) or (field.box if field is not None else None),
        value=result.value if result is not None else _field_amount(field),
        direction=result.direction if result is not None else ModeloFormResultDirection.UNKNOWN,
        settles=result is not None,
        election_may_change=result is not None and result.election_may_change,
    )


def _field_amount(field: ModeloFormField | None) -> Decimal | None:
    if field is None or isinstance(field.value, bool) or not isinstance(field.value, Decimal | int):
        return None
    return Decimal(field.value)


def _figure(field: ModeloFormField, language: OutputLanguage) -> str:
    """What another result box shows: its figure, else the words for where its value stands."""
    if field.origin is ModeloFormOrigin.NOT_APPLICABLE:
        return tr(_NOT_APPLICABLE_VALUE_LOCALE_KEY, locale=language.value)
    figure = field_value_text(field, language)
    return figure if figure is not None else origin_words(field, language=language)


def _other_boxes_help(selected: _SelectedResult, form: ModeloWorkForm, language: OutputLanguage) -> str | None:
    others = [
        selected.fields[str(casilla_id)]
        for casilla_id in form.result_addresses
        if str(casilla_id) != selected.settling and str(casilla_id) in selected.fields
    ]
    if not others:
        return None
    named = ", ".join(
        f"[{field.box}] {_figure(field, language)}" if (field.box is not None and field.box) else field.label.text
        for field in others
    )
    return tr("workspace.modelo.header.result.other_boxes", boxes=named, locale=language.value)


def _choice_presentation(
    value: Decimal, box: str | None, language: OutputLanguage, help_lines: list[str]
) -> _Presentation:
    locale = language.value
    words = tr(_CHOICE_PENDING_LOCALE_KEY, locale=locale)
    amount = _money(abs(value), language)
    full, short = _boxed([words, amount], box)
    help_lines.append(words)
    brief = _WORD_GAP.join((tr(_CHOICE_PENDING_SHORT_LOCALE_KEY, locale=locale), amount))
    return _Presentation(full, short, words, amount, brief)


def _directional_presentation(
    direction: ModeloFormResultDirection,
    value: Decimal,
    box: str | None,
    language: OutputLanguage,
    help_lines: list[str],
) -> _Presentation:
    locale = language.value
    key = _DIRECTION_LOCALE_KEYS[direction]
    if direction is ModeloFormResultDirection.TO_DEDUCT_LATER:
        full, short = _boxed([tr(key, amount=_money(abs(value), language), locale=locale)], box)
        if box is not None and box:
            help_lines.append(tr(_SIGN_HELP_LOCALE_KEY, box=box, value=_money(value, language), locale=locale))
        return _Presentation(full, short)
    if direction in {ModeloFormResultDirection.NEGATIVE, ModeloFormResultDirection.NIL}:
        full, short = _boxed([tr(key, locale=locale)], box)
        return _Presentation(full, short)
    if direction is ModeloFormResultDirection.UNKNOWN:
        words, amount = tr(key, locale=locale), _money(value, language)
        full, short = _boxed([words, amount], box)
        help_lines.append(tr("workspace.modelo.header.result.direction_unknown_help", locale=locale))
        return _Presentation(full, short, words, amount)
    words, amount = tr(key, locale=locale), _money(abs(value), language)
    full, short = _boxed([words, amount], box)
    return _Presentation(full, short, words, amount)


def _show_sign_help(selected: _SelectedResult, value: Decimal, presentation: _Presentation) -> bool:
    return (
        value < 0
        and presentation.words is not None
        and selected.direction is not ModeloFormResultDirection.UNKNOWN
        and bool(selected.box)
    )


def _stated(
    selected: _SelectedResult, form: ModeloWorkForm, language: OutputLanguage, out_of_date: str | None
) -> ModeloFormResultView:
    value = selected.value
    if value is None:
        raise ValueError("a stated result must have a value")
    help_lines = [tr(_OWN_CALCULATION_LOCALE_KEY, locale=language.value)]
    if selected.election_may_change:
        presentation = _choice_presentation(value, selected.box, language, help_lines)
    else:
        presentation = _directional_presentation(selected.direction, value, selected.box, language, help_lines)
    if _show_sign_help(selected, value, presentation):
        help_lines.append(
            tr(_SIGN_HELP_LOCALE_KEY, box=selected.box, value=_money(value, language), locale=language.value)
        )
    other = _other_boxes_help(selected, form, language)
    if other is not None:
        help_lines.append(other)
    return _view(
        selected,
        ModeloFormResultState.CHOICE_PENDING if selected.election_may_change else ModeloFormResultState.STATED,
        words=presentation.words,
        amount_text=presentation.amount_text,
        text=presentation.text,
        short_text=presentation.short_text,
        brief_text=presentation.brief_text if presentation.brief_text is not None else presentation.short_text,
        help=tuple(help_lines),
        out_of_date_words=out_of_date,
    )


def _view(selected: _SelectedResult, state: ModeloFormResultState, **words: object) -> ModeloFormResultView:
    return ModeloFormResultView.model_validate(
        {
            "state": state,
            "casilla_id": selected.casilla_id,
            "box": selected.box,
            "settles": selected.settles,
            "direction": selected.direction,
            **words,
        }
    )


def _unstated(
    selected: _SelectedResult, state: ModeloFormResultState, language: OutputLanguage, **words: object
) -> ModeloFormResultView:
    said = tr(_RESULT_LOCALE_KEYS[state], locale=language.value)
    return _view(selected, state, text=said, short_text=said, brief_text=said, **words)


def result_view(form: ModeloWorkForm, language: OutputLanguage, *, recorded: bool) -> ModeloFormResultView | None:
    """The result as the header states it, or ``None`` when the form names no result box at all.

    Without a declared settlement box the first result box in form order
    stands, under the plain word "Result". A calculation the filer's records
    changed under is out of date until it is calculated again, except once the
    declaration is recorded as filed.
    """
    selected = _selected_result(form)
    if selected is None:
        return None
    locale = language.value
    out_of_date = tr(_RECALCULATE_LOCALE_KEY, locale=locale) if form.calculation_out_of_date and not recorded else None
    origin = selected.field.origin if selected.field is not None else None
    if origin is ModeloFormOrigin.CALCULATION_FAILED:
        own = (tr(_OWN_CALCULATION_LOCALE_KEY, locale=locale),)
        return _unstated(selected, ModeloFormResultState.FAILED, language, help=own, out_of_date_words=out_of_date)
    if form.calculation_revision_id is None or origin is ModeloFormOrigin.NOT_CALCULATED_YET or selected.value is None:
        return _unstated(selected, ModeloFormResultState.NOT_CALCULATED, language, out_of_date_words=out_of_date)
    return _stated(selected, form, language, out_of_date)


def form_header(form: ModeloWorkForm, language: OutputLanguage, *, verified: bool, filed: bool) -> ModeloFormHeader:
    """Everything the header states about the declaration, in ``language``, from its form and lifecycle."""
    recorded = form_recorded(form, filed=filed)
    return ModeloFormHeader(
        attention=attention_counts(form, language, recorded=recorded),
        result=result_view(form, language, recorded=recorded),
        deadline=deadline_view(form, language, recorded=recorded),
        file=file_view(form, language, recorded=recorded),
        export_hold=export_hold(form, language, verified=verified, recorded=recorded),
    )


__all__ = [
    "SOON_DAYS",
    "URGENT_DAYS",
    "ModeloFormAttentionCount",
    "ModeloFormDeadlineTone",
    "ModeloFormDeadlineView",
    "ModeloFormExportHold",
    "ModeloFormExportHoldReason",
    "ModeloFormFileView",
    "ModeloFormHeader",
    "ModeloFormResultState",
    "ModeloFormResultView",
    "attention_counts",
    "deadline_tone",
    "deadline_view",
    "deadline_words",
    "export_hold",
    "file_view",
    "form_header",
    "form_recorded",
    "result_view",
]
