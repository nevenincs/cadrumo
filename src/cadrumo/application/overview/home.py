"""Pure composition of the frontend-neutral Home projection.

The composer accepts results that have already been read by the application
composition root.  It does not resolve repositories, contact AEAT, or import a
frontend.  Zone availability is supplied alongside those results so absence is
never silently presented as a known empty collection or zero count.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from .agenda import OverviewAgenda
from .calendar_models import OverviewAeatSubmissionState, OverviewCalendarEntry
from .home_projection import (
    HomeAccountSession,
    HomeAgendaEntry,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeLedgerReadiness,
    HomeNextAction,
    HomeProjectionV1,
    HomeZoneState,
)


class HomeProjectionInput(BaseModel):
    """Already-local reader results and explicit authority state for Home."""

    model_config = _STRICT_FROZEN

    generated_at: datetime
    account: HomeAccountSession
    actions_state: HomeZoneState
    actions: tuple[HomeNextAction, ...] = ()
    declarations_state: HomeZoneState
    declarations: tuple[HomeDeclarationResume, ...] = ()
    work_units: tuple[WorkUnit, ...] = ()
    ledger_state: HomeZoneState
    ledger_readiness: HomeLedgerReadiness | None = None
    agenda_state: HomeZoneState
    agenda_evidence_state: HomeZoneState
    overview_agenda: OverviewAgenda | None = None
    messages_state: HomeZoneState
    messages_requiring_attention: int | None = None


def compose_home_projection(source: HomeProjectionInput) -> HomeProjectionV1:
    """Compose one immutable Home snapshot from canonical local read models."""
    return HomeProjectionV1(
        generated_at=source.generated_at,
        account=source.account,
        actions_state=source.actions_state,
        actions=_rank_actions(source.actions),
        declarations_state=source.declarations_state,
        declarations=_project_declarations(source.declarations, source.work_units),
        ledger_state=source.ledger_state,
        ledger=source.ledger_readiness,
        agenda_state=source.agenda_state,
        agenda_evidence_state=source.agenda_evidence_state,
        agenda=_project_agenda(source.overview_agenda, evidence_state=source.agenda_evidence_state),
        messages_state=source.messages_state,
        messages_requiring_attention=source.messages_requiring_attention,
    )


def _rank_actions(actions: tuple[HomeNextAction, ...]) -> tuple[HomeNextAction, ...]:
    ordered = sorted(
        actions,
        key=lambda item: (
            item.rank,
            item.reason_code,
            item.action.action.action_id,
            item.modelo or "",
            item.filing_year or 0,
            item.period.registry_token if item.period is not None else "",
        ),
    )[:3]
    return tuple(item.model_copy(update={"rank": rank}) for rank, item in enumerate(ordered))


def _project_declarations(
    declarations: tuple[HomeDeclarationResume, ...],
    work_units: tuple[WorkUnit, ...],
) -> tuple[HomeDeclarationResume, ...]:
    projected_work_units = tuple(
        HomeDeclarationResume(
            work_unit_id=unit.work_unit_id,
            modelo=str(unit.modelo),
            filing_year=unit.filing_year,
            period=unit.period,
            name=unit.name,
            state=(
                HomeDeclarationState.DISCARDED if unit.state is WorkUnitState.DESCARTADO else HomeDeclarationState.DRAFT
            ),
            revision_id=unit.revision_id,
        )
        for unit in work_units
    )
    # A WorkUnit proves only draft/discarded lifecycle.  Richer READY,
    # NEEDS_REVIEW, and FILED claims arrive as exact declaration-reader output.
    by_id = {item.work_unit_id: item for item in projected_work_units}
    by_id.update({item.work_unit_id: item for item in declarations})
    ordered = sorted(
        by_id.values(),
        key=lambda unit: (
            unit.state is HomeDeclarationState.DISCARDED,
            str(unit.modelo),
            unit.filing_year,
            unit.period.registry_token,
            unit.work_unit_id,
        ),
    )
    return tuple(ordered)


def _project_agenda(
    agenda: OverviewAgenda | None,
    *,
    evidence_state: HomeZoneState,
) -> tuple[HomeAgendaEntry, ...]:
    if agenda is None:
        return ()
    entries_by_address: dict[tuple[str, int, str], OverviewCalendarEntry] = {}
    for entry in (*agenda.overdue, *agenda.due_today, *agenda.due_soon):
        key = (entry.modelo, entry.period.filing_year, entry.period.registry_token)
        entries_by_address[key] = entry
    ordered = sorted(
        entries_by_address.values(),
        key=lambda entry: (
            entry.adjusted_closes_on,
            entry.modelo,
            entry.period.filing_year,
            entry.period.registry_token,
        ),
    )[:3]
    evidence_observable = evidence_state.availability in {
        HomeAvailability.AVAILABLE,
        HomeAvailability.STALE,
    }
    return tuple(_project_agenda_entry(entry, evidence_observable=evidence_observable) for entry in ordered)


def _project_agenda_entry(entry: OverviewCalendarEntry, *, evidence_observable: bool) -> HomeAgendaEntry:
    evidence = entry.filing_evidence
    return HomeAgendaEntry(
        modelo=entry.modelo,
        filing_year=entry.filing_year or entry.period.filing_year,
        period=entry.period,
        due_on=entry.adjusted_closes_on,
        period_state=entry.user_state,
        local_filing_state=evidence.local_filing_state,
        aeat_submission_state=(
            evidence.aeat_submission_state if evidence_observable else OverviewAeatSubmissionState.NOT_OBSERVED
        ),
    )


__all__ = [
    "HomeProjectionInput",
    "compose_home_projection",
]
