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

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ..overview.calendar import holiday_coverage_statement
from ..overview.calendar_models import OverviewAeatSubmissionState, OverviewLocalFilingState
from ..overview.coverage import CoverageAdviceReason
from ..overview.home import HomeAvailability
from .declaration_summary import DeclarationSummaryState
from .declaration_targets import DeclarationTarget
from .declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from .declarations_workspace_contracts import (
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
)
from .value_presentation import format_casilla_value
from .work_form_header import ModeloFormDeadlineTone, deadline_tone, deadline_words
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
    return tr(f"workspace.declarations.list.next.{step.value}", count=blocking_count(row), locale=language.value)


def state_words(row: DeclarationListRow, language: OutputLanguage) -> str:
    """Where the row stands, in the filer's language: its own state, never the AEAT's in its place."""
    locale = language.value
    calendar = row.calendar
    if row.state == "aeat_unlinked" and calendar is not None and calendar.aeat_submitted_at is not None:
        return tr(
            "workspace.declarations.list.state.aeat_unlinked_on",
            date=date_text(calendar.aeat_submitted_at, language),
            locale=locale,
        )
    if row.state == "recorded":
        return tr("workspace.declarations.list.group.recorded", locale=locale)
    if row.state == "discarded":
        return tr("workspace.declarations.work_state.descartado", locale=locale)
    if row.state == "maybe":
        return tr("workspace.declarations.list.maybe.help", locale=locale)
    if is_unlinked_local_draft(row):
        return tr("workspace.declarations.list.state.local_draft", locale=locale)
    return ("▲ " if row.state == "blocked" else "") + tr(
        "workspace.declarations.list.state." + row.state, locale=locale
    )


def _valued_result_words(result: ModeloFormResult, value: Decimal, language: OutputLanguage) -> str:
    """A known amount with the way it settles, keeping the sign only where nothing says the direction."""
    locale = language.value
    shown_value = value if result.direction is ModeloFormResultDirection.UNKNOWN else abs(value)
    amount = format_casilla_value(shown_value, data_type=CasillaDataType.MONEY, language=language)
    key = "workspace.modelo.header.result." + _DIRECTION_WORDS[result.direction]
    if result.election_may_change:
        key = "workspace.modelo.header.result.choice_pending"
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
        "workspace.modelo.origin.not_calculated_yet"
        if not_calculated
        else "workspace.declarations.value.result_unknown"
    )
    return tr(key, locale=language.value)


# -- group words, deadlines and help --------------------------------------------

DECLARATION_GROUP_LOCALE_KEYS: Final[Mapping[DeclarationListGroup, str]] = MappingProxyType(
    {
        DeclarationListGroup.ATTENTION: "workspace.declarations.list.group.attention",
        DeclarationListGroup.IN_PROGRESS: "workspace.declarations.list.group.in_progress",
        DeclarationListGroup.READY: "workspace.declarations.list.group.ready",
        DeclarationListGroup.NOT_STARTED: "workspace.declarations.list.group.not_started",
        DeclarationListGroup.RECORDED: "workspace.declarations.list.group.recorded",
        DeclarationListGroup.AEAT_UNLINKED: "workspace.declarations.list.state.aeat_unlinked",
        DeclarationListGroup.MAYBE: "workspace.declarations.list.group.maybe",
    }
)
"""The heading of each group, total over the groups."""

_HELP_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "aeat_unlinked": "workspace.declarations.list.aeat_unlinked.help.confirmed",
        "unreadable": "workspace.declarations.list.unreadable.help",
        "maybe": "workspace.declarations.list.maybe.help",
        "aeat_needs_check": "workspace.declarations.list.aeat_needs_check.help",
    }
)
"""What a row that opens no local work and starts nothing says when the filer chooses it."""


def group_words(group: DeclarationListGroup, language: OutputLanguage) -> str:
    """The group's heading in the filer's language."""
    return tr(DECLARATION_GROUP_LOCALE_KEYS[group], locale=language.value)


def row_days(row: DeclarationListRow) -> tuple[int | None, int | None]:
    """The days left until the row's deadline and the days it is overdue; ``None`` for what does not apply.

    Counted from the day the calendar was evaluated, so every frontend and the
    calendar agree whatever its own clock says. A declaration recorded,
    replaced or discarded, and a return the AEAT holds with no local work
    linked, have no deadline left to meet.
    """
    calendar = row.calendar
    if calendar is None or row.state == "aeat_unlinked" or row.state in _CLOSED_STATES:
        return None, None
    if calendar.days_overdue is not None and calendar.days_overdue != 0:
        return None, calendar.days_overdue
    return max((calendar.adjusted_closes_on - calendar.evaluated_on).days, 0), None


def opens_aeat_filing(row: DeclarationListRow) -> bool:
    """Whether choosing the row opens the details of a return the AEAT holds, to read; nothing is linked or sent."""
    return row.state == "aeat_unlinked"


_AEAT_FILING_NOTE_LOCALE_KEYS: Final[tuple[str, ...]] = (
    "workspace.declarations.list.aeat_unlinked.help.confirmed",
    "workspace.declarations.list.aeat_unlinked.help.no_refile",
    "workspace.declarations.list.aeat_unlinked.help.unavailable",
)
"""What the details of a return the AEAT holds say, in reading order."""


def aeat_filing_notes(row: DeclarationListRow, language: OutputLanguage) -> tuple[str, ...] | None:
    """What opening a return the AEAT holds says about it, in order; ``None`` for a row that opens none."""
    if not opens_aeat_filing(row):
        return None
    return tuple(tr(key, locale=language.value) for key in _AEAT_FILING_NOTE_LOCALE_KEYS)


class ModeloDeclarationAeatFilingV1(BaseModel):
    """The details a row opens of a return the AEAT holds with no local work linked."""

    model_config = STRICT_FROZEN_CONFIG

    #: That the AEAT confirms the filing, that it need not be filed again, and what cannot be done here yet.
    notes: tuple[str, ...] = Field(min_length=1)


def row_help_words(row: DeclarationListRow, language: OutputLanguage) -> str | None:
    """What choosing a row that opens no local work says, or ``None`` for a row whose step says it all."""
    key = _HELP_LOCALE_KEYS.get(row.state)
    return None if key is None else tr(key, locale=language.value)


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


def worded_list_row(row: DeclarationListRow, language: OutputLanguage) -> ModeloDeclarationListRowV1:
    """Say one row in the filer's language, with its step and the AEAT's facts beside its own."""
    step = next_step(row)
    calendar = row.calendar
    deadline = row.deadline if row.state != "aeat_unlinked" else None
    remaining, overdue = row_days(row)
    due = deadline is not None and (remaining is not None or overdue is not None)
    due_deadline = deadline if due else None
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
        filing_year=None if row.period is None else row.period.filing_year,
        period_code=None if row.period is None else str(row.period.code),
        period_words=None if row.period is None else period_words(row.period, language),
        deadline=deadline,
        deadline_text=None if deadline is None else date_text(deadline, language),
        days_remaining=remaining,
        days_overdue=overdue,
        due_words=deadline_words(due_deadline, remaining, overdue, language) if due_deadline is not None else None,
        due_tone=deadline_tone(remaining, overdue) if due else None,
        state_words=state_words(row, language),
        result_words=result_words(row, language),
        next_step=step,
        next_step_words=None if step is None else next_step_words(row, step, language),
        opens_local_work=step is not None and opens_local_work(step),
        blocking_count=blocking_count(row),
        opens_aeat_filing=opens_aeat_filing(row),
        help_words=row_help_words(row, language),
        aeat_filing=None if notes is None else ModeloDeclarationAeatFilingV1(notes=notes),
        advice=row.advice,
        advice_words=None
        if row.advice is None
        else tr("workspace.declarations.list.advice." + row.advice.value, locale=language.value),
        local_draft=is_unlinked_local_draft(row),
        local_filing_state=None if calendar is None else calendar.local_filing_state,
        aeat_submission_state=None if calendar is None else calendar.aeat_submission_state,
        aeat_submitted_at=None if calendar is None else calendar.aeat_submitted_at,
        aeat_needs_check=calendar is not None and calendar.aeat_needs_check,
        evidence_conflicted=calendar is not None and calendar.evidence_conflicted,
    )


# -- what the list could read, and what the new-declaration dialog offers -------

_OBSERVED_FORMAT: Final[str] = "%d/%m/%Y %H:%M UTC"


def observed_text(moment: datetime) -> str:
    """When a source was read, to the minute and in UTC, so no reader mistakes the zone it was read in."""
    utc = moment.astimezone(UTC) if moment.tzinfo is not None else moment
    return utc.strftime(_OBSERVED_FORMAT)


class ModeloDeclarationsListZoneV1(BaseModel):
    """Whether one area of the local declarations could be read, and when."""

    model_config = STRICT_FROZEN_CONFIG

    zone: DeclarationsWorkspaceZone
    availability: DeclarationsWorkspaceAvailability
    observed_at: datetime | None = None
    #: The availability in the filer's language.
    words: str


class ModeloDeclarationsListSourceV1(BaseModel):
    """Whether one source of the filing calendar could be read, and when, said as the list says it."""

    model_config = STRICT_FROZEN_CONFIG

    source: DeclarationsCalendarSource
    availability: HomeAvailability
    observed_at: datetime | None = None
    #: The source, its availability and when it was read, or that it never was, in the filer's language.
    words: str


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


def zone_states(
    workspace: DeclarationsWorkspaceProjectionV1, language: OutputLanguage
) -> tuple[ModeloDeclarationsListZoneV1, ...]:
    """Every area of the local declarations, with whether it could be read, in canonical order."""
    return tuple(
        ModeloDeclarationsListZoneV1(
            zone=zone.zone,
            availability=zone.availability,
            observed_at=zone.observed_at,
            words=tr("workspace.declarations.availability." + zone.availability.value, locale=language.value),
        )
        for zone in workspace.zones
    )


def _observed_words(source: DeclarationsCalendarSourceStateV1, language: OutputLanguage) -> str:
    locale = language.value
    if source.observed_at is not None:
        return observed_text(source.observed_at)
    if source.availability is HomeAvailability.NEVER_CAPTURED:
        return tr("workspace.declarations.calendar.never_observed", locale=locale)
    if source.availability is HomeAvailability.AVAILABLE:
        return tr("workspace.declarations.calendar.observation.not_recorded", locale=locale)
    return tr("workspace.declarations.calendar.observation.time_not_recorded", locale=locale)


def source_words(source: DeclarationsCalendarSourceStateV1, language: OutputLanguage) -> str:
    """One calendar source, whether it could be read, and when, or why no time is said."""
    locale = language.value
    observed = _observed_words(source, language)
    return tr(
        "workspace.declarations.calendar.detail.source",
        source=tr("workspace.declarations.calendar.source." + source.source.value, locale=locale),
        availability=tr("workspace.declarations.availability." + source.availability.value, locale=locale),
        observed=observed,
        locale=locale,
    )


def calendar_sources(
    calendar: DeclarationsCalendarProjectionV1, language: OutputLanguage
) -> tuple[ModeloDeclarationsListSourceV1, ...]:
    """Every source of the filing calendar, with whether it could be read and when."""
    return tuple(
        ModeloDeclarationsListSourceV1(
            source=source.source,
            availability=source.availability,
            observed_at=source.observed_at,
            words=source_words(source, language),
        )
        for source in calendar.sources
    )


def source_notices(
    workspace: DeclarationsWorkspaceProjectionV1,
    calendar: DeclarationsCalendarProjectionV1 | None,
    language: OutputLanguage,
) -> tuple[str, ...]:
    """What the list says beside its rows about what it could read.

    The AEAT's evidence is named with whether it could be read and when, since
    a return the AEAT holds shows only once it was; an area of the local
    declarations read only in part says so, so the rows are never taken for
    everything there is.
    """
    lines: list[str] = []
    if calendar is not None:
        lines.extend(
            source_words(source, language)
            for source in calendar.sources
            if source.source is DeclarationsCalendarSource.AEAT_EVIDENCE
        )
    if any(zone.availability is DeclarationsWorkspaceAvailability.STALE for zone in workspace.zones):
        lines.append(tr("workspace.declarations.refusal.source", locale=language.value))
    return tuple(lines)


def applicable_modelos(rows: tuple[DeclarationListRow, ...]) -> frozenset[str]:
    """The modelos the list shows the filer as theirs: every one a row names, but those it only advises."""
    return frozenset(row.modelo for row in rows if row.state != "maybe")


def creation_targets(
    rows: tuple[DeclarationListRow, ...], admitted: tuple[DeclarationTarget, ...]
) -> tuple[DeclarationTarget, ...]:
    """The addresses a declaration may be started at: those the authority admits, else the returns due."""
    return admitted or tuple(
        DeclarationTarget(row.modelo, row.period)
        for row in rows
        if row.period is not None and row.state == "not_started"
    )


def preferred_creation_target(rows: tuple[DeclarationListRow, ...]) -> DeclarationTarget | None:
    """The first return due and not started, when it names its period."""
    due = sorted((row for row in rows if row.state == "not_started"), key=lambda row: row.deadline or date.max)
    return DeclarationTarget(due[0].modelo, due[0].period) if due and due[0].period is not None else None


def existing_declaration(
    rows: tuple[DeclarationListRow, ...], target: DeclarationTarget
) -> DeclarationsWorkspaceDeclarationRefV1 | None:
    """The declaration already at exactly the chosen address, if there is one."""
    return next(
        (
            row.declaration
            for row in rows
            if row.declaration is not None and row.modelo == target.modelo and row.period == target.period
        ),
        None,
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
        existing = next(
            (
                row
                for row in rows
                if row.declaration is not None and row.modelo == target.modelo and row.period == target.period
            ),
            None,
        )
        deadline = deadlines.get((target.modelo, target.period))
        worded.append(
            ModeloDeclarationCreationTargetV1(
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
        )
    return tuple(worded)


_UNSETTLED_COVERAGE: Final[frozenset[DeadlineHolidayCoverage]] = frozenset(
    {
        DeadlineHolidayCoverage.NATIONAL_ONLY,
        DeadlineHolidayCoverage.TERRITORY_UNVERIFIED,
        DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
    }
)
"""Holiday coverage that leaves an effective deadline short of final: a regional holiday may still move it."""


def deadline_note_words(rows: tuple[DeclarationListRow, ...], language: OutputLanguage) -> str | None:
    """Say which holidays the listed deadlines leave out, when an open deadline is not final; ``None`` otherwise."""
    for row in rows:
        calendar = row.calendar
        remaining, overdue = row_days(row)
        open_deadline = remaining is not None or overdue is not None
        if calendar is not None and open_deadline and calendar.holiday_coverage in _UNSETTLED_COVERAGE:
            return holiday_coverage_statement(calendar.holiday_coverage, calendar.holiday_territory, language)
    return None


__all__ = [
    "DECLARATION_GROUP_LOCALE_KEYS",
    "DeclarationListGroup",
    "DeclarationListInputs",
    "DeclarationListNextStep",
    "DeclarationListRow",
    "ModeloDeclarationAeatFilingV1",
    "ModeloDeclarationCreationTargetV1",
    "ModeloDeclarationExistingV1",
    "ModeloDeclarationListRowV1",
    "ModeloDeclarationsListSourceV1",
    "ModeloDeclarationsListZoneV1",
    "aeat_filing_notes",
    "applicable_modelos",
    "blocking_count",
    "calendar_sources",
    "creation_targets",
    "deadline_note_words",
    "declaration_list_rows",
    "existing_declaration",
    "group_words",
    "is_unlinked_local_draft",
    "next_step",
    "next_step_words",
    "observed_text",
    "opens_aeat_filing",
    "opens_local_work",
    "preferred_creation_target",
    "result_words",
    "row_days",
    "row_help_words",
    "source_notices",
    "source_words",
    "state_words",
    "worded_creation_targets",
    "worded_list_row",
    "zone_states",
]
