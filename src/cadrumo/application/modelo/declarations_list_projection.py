"""Join portfolio summaries and legal calendar facts for one grouped filing list, and say each row.

Every frontend lists declarations from these rows: local work, returns due
with no local work, returns the AEAT already holds with no local work linked,
and obligations the coverage only advises. Each row keeps its own result and
local state apart from the AEAT's, and names its next step and its words in
the filer's language, so no frontend classifies a row itself. Whether a
frontend may open or start a row is that frontend's admission to decide; a
step it cannot perform is simply not offered there.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ..overview.calendar_models import OverviewAeatSubmissionState, OverviewLocalFilingState
from ..overview.coverage import CoverageAdviceReason
from .declaration_targets import DeclarationTarget
from .declarations_calendar import DeclarationsCalendarEntryRefV1
from .declarations_list import (
    DeclarationListGroup,
    DeclarationListNextStep,
    DeclarationListRow,
    aeat_filing_notes,
    applicable_modelos,
    blocking_count,
    creation_targets,
    group_words,
    is_unlinked_local_draft,
    next_step,
    next_step_words,
    opens_aeat_filing,
    opens_local_work,
    preferred_creation_target,
    result_words,
    row_days,
    row_help_words,
    state_words,
)
from .work_form_header import ModeloFormDeadlineTone, deadline_tone, deadline_words
from .work_form_wording import date_text, modelo_number, modelo_title, period_words


class ModeloDeclarationAeatFilingV1(BaseModel):
    """The details a row opens of a return the AEAT holds with no local work linked."""

    model_config = STRICT_FROZEN_CONFIG

    #: That the AEAT confirms the filing, that it need not be filed again, and what cannot be done here yet.
    notes: tuple[str, ...] = Field(min_length=1)


class ModeloDeclarationListRowV1(BaseModel):
    """One row of the declarations list as every frontend shows it, with the AEAT's facts kept apart."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1, max_length=128)
    group: DeclarationListGroup
    #: The heading of the row's group, in the filer's language.
    group_words: str
    state: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    modelo_title: str
    modelo_number: str
    #: The declaration's local work, which a form read opens; ``None`` for a row with no local work.
    work_unit_id: str | None = None
    filing_year: int | None = None
    period_code: str | None = None
    period_words: str | None = None
    #: The registry's effective last day to file, when the calendar knows it, and that day in words.
    deadline: date | None = None
    deadline_text: str | None = None
    #: The days left until the deadline, or the days it is overdue, counted from the calendar's own day;
    #: neither once the row is closed or has no deadline left to meet.
    days_remaining: int | None = Field(default=None, ge=0)
    days_overdue: int | None = Field(default=None, gt=0)
    #: The deadline with the days left, "today" or that it passed, as the declaration's header says it.
    due_words: str | None = None
    #: How urgently the deadline reads, at the header's thresholds.
    due_tone: ModeloFormDeadlineTone | None = None
    state_words: str
    result_words: str | None = None
    next_step: DeclarationListNextStep | None = None
    next_step_words: str | None = None
    #: Whether the step opens the row's own local work, which a frontend offers only where it may open it.
    opens_local_work: bool = False
    blocking_count: int = Field(default=0, ge=0)
    #: Whether choosing the row opens the details of a return the AEAT holds, to read; nothing is linked or sent.
    opens_aeat_filing: bool = False
    #: What choosing a row with no step of its own says, such as why it cannot be opened.
    help_words: str | None = None
    #: The details the row opens of a return the AEAT holds; set exactly when ``opens_aeat_filing`` is.
    aeat_filing: ModeloDeclarationAeatFilingV1 | None = None
    advice: CoverageAdviceReason | None = None
    advice_words: str | None = None
    #: Original local work beside a return the AEAT already holds.
    local_draft: bool = False
    local_filing_state: OverviewLocalFilingState | None = None
    aeat_submission_state: OverviewAeatSubmissionState | None = None
    aeat_submitted_at: datetime | None = None
    aeat_needs_check: bool = False
    evidence_conflicted: bool = False


def _calendar_details(
    calendar: DeclarationsCalendarEntryRefV1 | None,
) -> tuple[OverviewLocalFilingState | None, OverviewAeatSubmissionState | None, datetime | None, bool, bool]:
    if calendar is None:
        return None, None, None, False, False
    return (
        calendar.local_filing_state,
        calendar.aeat_submission_state,
        calendar.aeat_submitted_at,
        calendar.aeat_needs_check,
        calendar.evidence_conflicted,
    )


def _period_details(period: Period | None, language: OutputLanguage) -> tuple[int | None, str | None, str | None]:
    if period is None:
        return None, None, None
    return period.filing_year, str(period.code), period_words(period, language)


def _deadline_details(
    deadline: date | None, remaining: int | None, overdue: int | None, language: OutputLanguage
) -> tuple[str | None, str | None, ModeloFormDeadlineTone | None]:
    if deadline is None:
        return None, None, None
    due = remaining is not None or overdue is not None
    return (
        date_text(deadline, language),
        deadline_words(deadline, remaining, overdue, language) if due else None,
        deadline_tone(remaining, overdue) if due else None,
    )


def _step_details(
    row: DeclarationListRow, step: DeclarationListNextStep | None, language: OutputLanguage
) -> tuple[str | None, bool]:
    return (None if step is None else next_step_words(row, step, language), step is not None and opens_local_work(step))


def worded_list_row(row: DeclarationListRow, language: OutputLanguage) -> ModeloDeclarationListRowV1:
    """Say one row in the filer's language, with its step and the AEAT's facts beside its own."""
    step = next_step(row)
    local_state, submission_state, submitted_at, needs_check, conflicted = _calendar_details(row.calendar)
    deadline = row.deadline if row.state != "aeat_unlinked" else None
    remaining, overdue = row_days(row)
    deadline_text, due_words, due_tone = _deadline_details(deadline, remaining, overdue, language)
    filing_year, period_code, period_label = _period_details(row.period, language)
    step_label, open_work = _step_details(row, step, language)
    notes = aeat_filing_notes(row, language)
    return ModeloDeclarationListRowV1(
        key=row.key,
        group=row.group,
        group_words=group_words(row.group, language),
        state=row.state,
        modelo=row.modelo,
        modelo_title=modelo_title(row.modelo, language),
        modelo_number=modelo_number(row.modelo, language),
        work_unit_id=None if row.declaration is None else str(row.declaration.work_unit_id),
        filing_year=filing_year,
        period_code=period_code,
        period_words=period_label,
        deadline=deadline,
        deadline_text=deadline_text,
        days_remaining=remaining,
        days_overdue=overdue,
        due_words=due_words,
        due_tone=due_tone,
        state_words=state_words(row, language),
        result_words=result_words(row, language),
        next_step=step,
        next_step_words=step_label,
        opens_local_work=open_work,
        blocking_count=blocking_count(row),
        opens_aeat_filing=opens_aeat_filing(row),
        help_words=row_help_words(row, language),
        aeat_filing=None if notes is None else ModeloDeclarationAeatFilingV1(notes=notes),
        advice=row.advice,
        advice_words=None
        if row.advice is None
        else tr("workspace.declarations.list.advice." + row.advice.value, locale=language.value),
        local_draft=is_unlinked_local_draft(row),
        local_filing_state=local_state,
        aeat_submission_state=submission_state,
        aeat_submitted_at=submitted_at,
        aeat_needs_check=needs_check,
        evidence_conflicted=conflicted,
    )


class ModeloDeclarationExistingV1(BaseModel):
    """The declaration already at a creation address, which the dialog opens instead of making another."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: str = Field(min_length=1)
    state_words: str


class ModeloDeclarationCreationTargetV1(BaseModel):
    """One modelo and period the new-declaration dialog offers, as the pinned authority admits it."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=16)
    modelo_title: str
    filing_year: int
    period_code: str
    period_words: str
    #: The effective last day to file, when the calendar lists this address.
    deadline: date | None = None
    deadline_text: str | None = None
    #: Whether the list shows the filer this modelo, so the dialog offers it before being asked to show every one.
    expected: bool
    #: The first return due and not started, which the dialog starts on.
    suggested: bool = False
    existing: ModeloDeclarationExistingV1 | None = None


def _worded_creation_target(
    target: DeclarationTarget,
    rows: tuple[DeclarationListRow, ...],
    expected: frozenset[str],
    suggested: DeclarationTarget | None,
    deadlines: dict[tuple[str, Period], date],
    language: OutputLanguage,
) -> ModeloDeclarationCreationTargetV1:
    existing = next(
        (
            row
            for row in rows
            if row.declaration is not None and row.modelo == target.modelo and row.period == target.period
        ),
        None,
    )
    deadline = deadlines.get((target.modelo, target.period))
    return ModeloDeclarationCreationTargetV1(
        modelo=target.modelo,
        modelo_title=modelo_title(target.modelo, language),
        filing_year=target.period.filing_year,
        period_code=str(target.period.code),
        period_words=period_words(target.period, language),
        deadline=deadline,
        deadline_text=None if deadline is None else date_text(deadline, language),
        expected=target.modelo in expected,
        suggested=target == suggested,
        existing=None
        if existing is None or existing.declaration is None
        else ModeloDeclarationExistingV1(
            work_unit_id=str(existing.declaration.work_unit_id), state_words=state_words(existing, language)
        ),
    )


def worded_creation_targets(
    rows: tuple[DeclarationListRow, ...], admitted: tuple[DeclarationTarget, ...], language: OutputLanguage
) -> tuple[ModeloDeclarationCreationTargetV1, ...]:
    """Every address the new-declaration dialog offers, said in the filer's language."""
    expected = applicable_modelos(rows)
    suggested = preferred_creation_target(rows)
    deadlines = {
        (row.modelo, row.period): row.calendar.adjusted_closes_on
        for row in rows
        if row.calendar is not None and row.period is not None
    }
    worded: list[ModeloDeclarationCreationTargetV1] = []
    for target in creation_targets(rows, admitted):
        worded.append(_worded_creation_target(target, rows, expected, suggested, deadlines, language))
    return tuple(worded)
