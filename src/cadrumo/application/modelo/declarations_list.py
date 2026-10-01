"""Join portfolio summaries and legal calendar facts for one grouped filing list."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ...core.period import Period
from ...core.time.clock import today_madrid
from ..overview.calendar_models import OverviewAeatSubmissionState, OverviewLocalFilingState
from ..overview.coverage import CoverageAdviceReason
from .declaration_summary import DeclarationSummaryState
from .declarations_calendar import DeclarationsCalendarEntryRefV1, DeclarationsCalendarProjectionV1
from .declarations_workspace import DeclarationsWorkspaceDeclarationRefV1, DeclarationsWorkspaceProjectionV1


class DeclarationListGroup(StrEnum):
    """The work order a filer sees in the portfolio."""

    ATTENTION = "attention"
    IN_PROGRESS = "in_progress"
    READY = "ready"
    NOT_STARTED = "not_started"
    RECORDED = "recorded"
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
        rows.append(
            DeclarationListRow(
                str(declaration.work_unit_id),
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
        )
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
                    DeclarationListGroup.RECORDED,
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
    if calendar is not None:
        rows.extend(
            DeclarationListRow(
                f"advice:{item.modelo}", item.modelo, None, "maybe", DeclarationListGroup.MAYBE, advice=item.reason
            )
            for item in calendar.coverage.advised
        )
    return tuple(rows)
