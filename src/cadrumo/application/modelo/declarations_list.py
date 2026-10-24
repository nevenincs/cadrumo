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

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.schema_base import CasillaDataType
from ..overview.calendar_models import OverviewAeatSubmissionState, OverviewLocalFilingState
from ..overview.coverage import CoverageAdviceReason
from .declaration_summary import DeclarationSummaryState
from .declarations_calendar import DeclarationsCalendarEntryRefV1, DeclarationsCalendarProjectionV1
from .declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1, DeclarationsWorkspaceProjectionV1
from .value_presentation import format_casilla_value
from .work_form_models import ModeloFormResult, ModeloFormResultDirection
from .work_form_wording import date_text, modelo_number, modelo_title, period_words


class DeclarationListGroup(StrEnum):
    """The work order a filer sees in the portfolio."""

    ATTENTION = "attention"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    NOT_STARTED = "not_started"
    RECORDED = "recorded"
    AEAT_UNLINKED = "aeat_unlinked"
    MAYBE = "maybe"


@dataclass(frozen=True, slots=True)
class DeclarationListRow:
    """A single row keeps local work and external completion separate."""

    key: str
    modelo: str
    period: Period | None
    state: str
    group: DeclarationListGroup
    declaration: DeclarationsWorkspaceDeclarationRefV1 | None = None
    calendar: DeclarationsCalendarEntryRefV1 | None = None
    advice: CoverageAdviceReason | None = None

    @property
    def deadline(self) -> date | None:
        """The registry's effective closing date, when known."""
        return None if self.calendar is None else self.calendar.adjusted_closes_on


def _external_completion(calendar: DeclarationsCalendarEntryRefV1) -> bool:
    return (
        calendar.aeat_submission_state is not None
        and calendar.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED
        and not calendar.evidence_conflicted
        and not calendar.aeat_needs_check
    )


def _local_group(
    state: str, calendar: DeclarationsCalendarEntryRefV1 | None, today: date, *, is_correction: bool = False
) -> DeclarationListGroup:
    if state in {"recorded", "superseded", "discarded"}:
        return DeclarationListGroup.RECORDED
    if state in {"blocked", "unreadable"}:
        return DeclarationListGroup.ATTENTION
    if (
        calendar is not None
        and (is_correction or not _external_completion(calendar))
        and (calendar.adjusted_closes_on - today).days <= 7
    ):
        return DeclarationListGroup.ATTENTION
    return DeclarationListGroup.READY if state == "checked" else DeclarationListGroup.IN_PROGRESS


@dataclass(frozen=True, slots=True)
class DeclarationListInputs:
    """What the list joins, captured together: the local declarations and the legal calendar.

    ``workspace`` is ``None`` when the local declarations could not be read;
    the list is then unavailable, never shown as a profile holding nothing.
    """

    workspace: DeclarationsWorkspaceProjectionV1 | None
    calendar: DeclarationsCalendarProjectionV1


def declaration_list_rows(
    workspace: DeclarationsWorkspaceProjectionV1,
    calendar: DeclarationsCalendarProjectionV1 | None,
) -> tuple[DeclarationListRow, ...]:
    """Project every local row plus due, externally completed and advised obligations."""
    dates = {} if calendar is None else {item.semantic_key(): item for item in calendar.entries}
    today = today_madrid() if calendar is None else calendar.as_of
    local_addresses: set[tuple[str, int, str]] = set()
    rows: list[DeclarationListRow] = []
    for declaration in workspace.declarations:
        key = (str(declaration.modelo), declaration.filing_year, declaration.period.registry_token)
        local_addresses.add(key)
        deadline = dates.get(key)
        rows.append(_local_declaration_row(declaration, deadline, today))
    rows.extend(_calendar_declaration_rows(dates, local_addresses, today))
    if calendar is not None:
        rows.extend(
            DeclarationListRow(
                f"advice:{item.modelo}", item.modelo, None, "maybe", DeclarationListGroup.MAYBE, advice=item.reason
            )
            for item in calendar.coverage.advised
        )
    return tuple(rows)


def _local_declaration_row(
    declaration: DeclarationsWorkspaceDeclarationRefV1, deadline: DeclarationsCalendarEntryRefV1 | None, today: date
) -> DeclarationListRow:
    """Keep local work status and correction urgency separate from external filing."""
    state = (
        declaration.summary.state.value
        if declaration.summary is not None
        else (
            DeclarationSummaryState.RECORDED.value
            if declaration.has_current_filing
            else DeclarationSummaryState.CALCULATED.value
            if declaration.has_current_calculation
            else DeclarationSummaryState.DRAFT.value
        )
    )
    return DeclarationListRow(
        declaration.work_unit_id,
        str(declaration.modelo),
        declaration.period,
        state,
        _local_group(
            state,
            deadline,
            today,
            is_correction=declaration.summary is not None and declaration.summary.is_correction,
        ),
        declaration=declaration,
        calendar=deadline,
    )


def _calendar_declaration_rows(
    dates: dict[tuple[str, int, str], DeclarationsCalendarEntryRefV1],
    local_addresses: set[tuple[str, int, str]],
    today: date,
) -> list[DeclarationListRow]:
    """Append external unlinked returns and uncovered obligations in calendar order."""
    rows: list[DeclarationListRow] = []
    for key, item in dates.items():
        external = _external_completion(item)
        if external and item.local_filing_state is OverviewLocalFilingState.NOT_READY_TO_FILE:
            # A local draft remains local work; its result never becomes the
            # amount of an externally filed return.
            rows.append(
                DeclarationListRow(
                    f"aeat:{key}",
                    str(item.modelo),
                    item.period,
                    "aeat_unlinked",
                    DeclarationListGroup.AEAT_UNLINKED,
                    calendar=item,
                )
            )
        elif key not in local_addresses:
            state = "aeat_needs_check" if item.evidence_conflicted or item.aeat_needs_check else "not_started"
            group = (
                DeclarationListGroup.ATTENTION
                if state == "aeat_needs_check" or (item.adjusted_closes_on - today).days <= 7
                else DeclarationListGroup.NOT_STARTED
            )
            rows.append(DeclarationListRow(f"due:{key}", str(item.modelo), item.period, state, group, calendar=item))
    return rows


# -- what each row offers and says ---------------------------------------------


class DeclarationListNextStep(StrEnum):
    """The one step a row offers, before any frontend's admission to open or start it."""

    FIX = "fix"
    START = "start"
    OPEN_LOCAL_DRAFT = "open_local_draft"
    CREATE_FILE = "create_file"
    CONTINUE = "continue"
    NONE = "none"


_LOCAL_STEPS: Final[frozenset[DeclarationListNextStep]] = frozenset(
    {
        DeclarationListNextStep.OPEN_LOCAL_DRAFT,
        DeclarationListNextStep.CREATE_FILE,
        DeclarationListNextStep.CONTINUE,
        DeclarationListNextStep.NONE,
    }
)
"""The steps that open the row's own local work."""
_DIRECTION_WORDS: Final = MappingProxyType(
    {
        ModeloFormResultDirection.TO_PAY: "to_pay",
        ModeloFormResultDirection.TO_REFUND: "to_refund",
        ModeloFormResultDirection.TO_CARRY_FORWARD: "to_carry_forward",
        ModeloFormResultDirection.TO_DEDUCT_LATER: "negative_carried",
        ModeloFormResultDirection.NIL: "zero",
        ModeloFormResultDirection.NEGATIVE: "negative",
        ModeloFormResultDirection.UNKNOWN: "unknown",
    }
)
_NO_RESULT_STATES: Final[frozenset[str]] = frozenset({"not_started", "maybe", "aeat_unlinked"})
_CLOSED_STATES: Final[frozenset[str]] = frozenset({"recorded", "superseded", "discarded"})
_OPEN_WORK_STATES: Final[frozenset[str]] = frozenset({"draft", "calculated", "checked"})


def is_unlinked_local_draft(row: DeclarationListRow) -> bool:
    """Whether the row is original local work beside a return the AEAT already holds."""
    calendar = row.calendar
    return (
        row.declaration is not None
        and calendar is not None
        and calendar.aeat_submission_state is not None
        and calendar.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED
        and not calendar.evidence_conflicted
        and not calendar.aeat_needs_check
        and row.state in _OPEN_WORK_STATES
        and (row.declaration.summary is None or not row.declaration.summary.is_correction)
    )


def _local_step(row: DeclarationListRow) -> DeclarationListNextStep:
    if is_unlinked_local_draft(row):
        return DeclarationListNextStep.OPEN_LOCAL_DRAFT
    if row.state == "checked":
        return DeclarationListNextStep.CREATE_FILE
    if row.state in _CLOSED_STATES:
        return DeclarationListNextStep.NONE
    return DeclarationListNextStep.CONTINUE


def next_step(row: DeclarationListRow) -> DeclarationListNextStep | None:
    """The step the row offers: fixing what blocks it, starting a due return, or opening its local work."""
    if row.state == "blocked":
        return DeclarationListNextStep.FIX
    if row.state == "not_started":
        return DeclarationListNextStep.START
    if row.declaration is not None and row.state != "unreadable":
        return _local_step(row)
    return None


def opens_local_work(step: DeclarationListNextStep) -> bool:
    """Whether ``step`` opens the row's own local work, so needs a frontend's admission to open it."""
    return step in _LOCAL_STEPS


def blocking_count(row: DeclarationListRow) -> int:
    """How many things block filing the row's declaration; zero when its summary does not say."""
    summary = None if row.declaration is None else row.declaration.summary
    return 0 if summary is None else summary.blocking_count or 0


def next_step_words(row: DeclarationListRow, step: DeclarationListNextStep, language: OutputLanguage) -> str:
    """The step in the filer's language."""
    return tr(f"tui.declarations.list.next.{step.value}", count=blocking_count(row), locale=language.value)


def state_words(row: DeclarationListRow, language: OutputLanguage) -> str:
    """Where the row stands, in the filer's language: its own state, never the AEAT's in its place."""
    locale = language.value
    calendar = row.calendar
    if row.state == "aeat_unlinked" and calendar is not None and calendar.aeat_submitted_at is not None:
        return tr(
            "tui.declarations.list.state.aeat_unlinked_on",
            date=date_text(calendar.aeat_submitted_at, language),
            locale=locale,
        )
    if row.state == "recorded":
        return tr("tui.declarations.list.group.recorded", locale=locale)
    if row.state == "discarded":
        return tr("tui.declarations.work_state.descartado", locale=locale)
    if row.state == "maybe":
        return tr("tui.declarations.list.maybe.help", locale=locale)
    if is_unlinked_local_draft(row):
        return tr("tui.declarations.list.state.local_draft", locale=locale)
    return ("▲ " if row.state == "blocked" else "") + tr("tui.declarations.list.state." + row.state, locale=locale)


def _valued_result_words(result: ModeloFormResult, value: Decimal, language: OutputLanguage) -> str:
    """A known amount with the way it settles, keeping the sign only where nothing says the direction."""
    locale = language.value
    shown_value = value if result.direction is ModeloFormResultDirection.UNKNOWN else abs(value)
    amount = format_casilla_value(shown_value, data_type=CasillaDataType.MONEY, language=language)
    key = "tui.modelo.workbench.header.result." + _DIRECTION_WORDS[result.direction]
    if result.election_may_change:
        key = "tui.modelo.workbench.header.result.choice_pending"
    if result.direction is ModeloFormResultDirection.TO_DEDUCT_LATER:
        return tr(key, amount=amount, locale=locale)
    if result.direction in {ModeloFormResultDirection.NIL, ModeloFormResultDirection.NEGATIVE}:
        return tr(key, locale=locale)
    return tr(key, locale=locale) + " · " + amount


def result_words(row: DeclarationListRow, language: OutputLanguage) -> str | None:
    """The declaration's own result in the filer's language; ``None`` for a row with no local result to state."""
    summary = None if row.declaration is None else row.declaration.summary
    result = None if summary is None else summary.result
    if result is not None and result.value is not None:
        return _valued_result_words(result, result.value, language)
    if row.state in _NO_RESULT_STATES:
        return None
    declaration = row.declaration
    not_calculated = (
        row.state == "draft"
        and declaration is not None
        and not declaration.has_current_calculation
        and not declaration.has_current_filing
    )
    key = (
        "tui.modelo.workbench.origin.not_calculated_yet" if not_calculated else "tui.declarations.value.result_unknown"
    )
    return tr(key, locale=language.value)


class ModeloDeclarationListRowV1(BaseModel):
    """One row of the declarations list as every frontend shows it, with the AEAT's facts kept apart."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1, max_length=128)
    group: DeclarationListGroup
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
    state_words: str
    result_words: str | None = None
    next_step: DeclarationListNextStep | None = None
    next_step_words: str | None = None
    #: Whether the step opens the row's own local work, which a frontend offers only where it may open it.
    opens_local_work: bool = False
    blocking_count: int = Field(default=0, ge=0)
    advice: CoverageAdviceReason | None = None
    advice_words: str | None = None
    #: Original local work beside a return the AEAT already holds.
    local_draft: bool = False
    local_filing_state: OverviewLocalFilingState | None = None
    aeat_submission_state: OverviewAeatSubmissionState | None = None
    aeat_submitted_at: datetime | None = None
    aeat_needs_check: bool = False
    evidence_conflicted: bool = False


def worded_declaration_list(
    workspace: DeclarationsWorkspaceProjectionV1,
    calendar: DeclarationsCalendarProjectionV1 | None,
    language: OutputLanguage,
) -> tuple[ModeloDeclarationListRowV1, ...]:
    """Every row of the list, in its order, said in the filer's language."""
    return tuple(worded_list_row(row, language) for row in declaration_list_rows(workspace, calendar))


def worded_list_row(row: DeclarationListRow, language: OutputLanguage) -> ModeloDeclarationListRowV1:
    """Say one row in the filer's language, with its step and the AEAT's facts beside its own."""
    step = next_step(row)
    calendar = row.calendar
    deadline = row.deadline if row.state != "aeat_unlinked" else None
    return ModeloDeclarationListRowV1(
        key=row.key,
        group=row.group,
        state=row.state,
        modelo=row.modelo,
        modelo_title=modelo_title(row.modelo, language),
        modelo_number=modelo_number(row.modelo, language),
        work_unit_id=None if row.declaration is None else str(row.declaration.work_unit_id),
        filing_year=None if row.period is None else row.period.filing_year,
        period_code=None if row.period is None else str(row.period.code),
        period_words=None if row.period is None else period_words(row.period, language),
        deadline=deadline,
        deadline_text=None if deadline is None else date_text(deadline, language),
        state_words=state_words(row, language),
        result_words=result_words(row, language),
        next_step=step,
        next_step_words=None if step is None else next_step_words(row, step, language),
        opens_local_work=step is not None and opens_local_work(step),
        blocking_count=blocking_count(row),
        advice=row.advice,
        advice_words=None
        if row.advice is None
        else tr("tui.declarations.list.advice." + row.advice.value, locale=language.value),
        local_draft=is_unlinked_local_draft(row),
        local_filing_state=None if calendar is None else calendar.local_filing_state,
        aeat_submission_state=None if calendar is None else calendar.aeat_submission_state,
        aeat_submitted_at=None if calendar is None else calendar.aeat_submitted_at,
        aeat_needs_check=calendar is not None and calendar.aeat_needs_check,
        evidence_conflicted=calendar is not None and calendar.evidence_conflicted,
    )


__all__ = [
    "DeclarationListGroup",
    "DeclarationListInputs",
    "DeclarationListNextStep",
    "DeclarationListRow",
    "ModeloDeclarationListRowV1",
    "blocking_count",
    "declaration_list_rows",
    "is_unlinked_local_draft",
    "next_step",
    "next_step_words",
    "opens_local_work",
    "result_words",
    "state_words",
    "worded_declaration_list",
    "worded_list_row",
]
