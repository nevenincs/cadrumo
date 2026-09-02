"""Pure composition of the frontend-neutral Home projection.

The composer accepts results that have already been read by the application
composition root.  It does not resolve repositories, contact AEAT, or import a
frontend.  Zone availability is supplied alongside those results so absence is
never silently presented as a known empty collection or zero count.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.identity import WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...domain.calculations.registry.ids import ModeloId, RevisionId
from ..operator_actions.models import DeclaredNextAction
from .agenda import OverviewAgenda
from .calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewLocalFilingState,
    OverviewPeriodState,
)


class HomeAvailability(StrEnum):
    """Whether one Home zone can make an authoritative claim."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class HomeSessionPosture(StrEnum):
    """Local profile-custody posture for the current TUI session."""

    NO_PROFILE = "no_profile"
    LOCKED = "locked"
    ACTIVE = "active"
    EXPIRED = "expired"


class HomeDeclarationState(StrEnum):
    """Closed operator-facing lifecycle for a resumable declaration."""

    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    FILED = "filed"
    DISCARDED = "discarded"


class HomeZoneState(BaseModel):
    """Authority and freshness state shared by every Home zone."""

    model_config = _STRICT_FROZEN

    availability: HomeAvailability
    observed_at: datetime | None = None
    reason_code: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def _require_honest_availability_evidence(self) -> Self:
        if self.availability is HomeAvailability.AVAILABLE and self.reason_code is not None:
            raise ValueError("an available Home zone cannot carry an unavailability reason")
        if self.availability is not HomeAvailability.AVAILABLE and self.reason_code is None:
            raise ValueError("a non-available Home zone requires a reason code")
        if self.availability is HomeAvailability.NEVER_CAPTURED and self.observed_at is not None:
            raise ValueError("a never-captured Home zone cannot carry an observation time")
        if self.availability is HomeAvailability.STALE and self.observed_at is None:
            raise ValueError("a stale Home zone requires its last observation time")
        return self


class HomeAccountSession(BaseModel):
    """Non-secret account identity and local custody posture for the header."""

    model_config = _STRICT_FROZEN

    posture: HomeSessionPosture
    profile_label: str | None = Field(default=None, min_length=1, max_length=200)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _enforce_posture_shape(self) -> Self:
        if self.posture is HomeSessionPosture.NO_PROFILE and self.profile_label is not None:
            raise ValueError("a no-profile session cannot carry a profile label")
        if self.posture is not HomeSessionPosture.NO_PROFILE and self.profile_label is None:
            raise ValueError("a selected-profile session requires a profile label")
        if self.posture is not HomeSessionPosture.ACTIVE and self.expires_at is not None:
            raise ValueError("only an active session may carry an expiry")
        return self


class HomeNextAction(BaseModel):
    """Application-ranked action shown without frontend-owned urgency logic."""

    model_config = _STRICT_FROZEN

    rank: NonNegativeInt
    action: DeclaredNextAction
    reason_code: str = Field(min_length=1, max_length=128)
    modelo: ModeloId | None = None
    filing_year: FilingYear | None = None
    period: Period | None = None

    @model_validator(mode="after")
    def _enforce_complete_natural_address(self) -> Self:
        address = (self.modelo, self.filing_year, self.period)
        if any(value is not None for value in address) and not all(value is not None for value in address):
            raise ValueError("a next-action declaration address must be complete or absent")
        if self.period is not None and self.filing_year != self.period.filing_year:
            raise ValueError("next-action filing_year must match its period year")
        return self


class HomeDeclarationResume(BaseModel):
    """Natural declaration address and current revision state for resumption."""

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    modelo: ModeloId
    filing_year: FilingYear
    period: Period
    name: str = Field(min_length=1, max_length=200)
    state: HomeDeclarationState
    revision_id: RevisionId | None = None

    @model_validator(mode="after")
    def _enforce_period_year(self) -> Self:
        if self.filing_year != self.period.filing_year:
            raise ValueError("declaration filing_year must match its period year")
        return self


class HomeLedgerReadiness(BaseModel):
    """Ledger quality counts; zone availability decides whether zero is known."""

    model_config = _STRICT_FROZEN

    entries: NonNegativeInt
    requiring_review: NonNegativeInt
    unclassified: NonNegativeInt
    missing_evidence: NonNegativeInt

    @model_validator(mode="after")
    def _enforce_subsets(self) -> Self:
        if any(value > self.entries for value in (self.requiring_review, self.unclassified, self.missing_evidence)):
            raise ValueError("Ledger issue counts cannot exceed the entry count")
        return self


class HomeAgendaEntry(BaseModel):
    """One legal filing date with independent local and observed-AEAT axes."""

    model_config = _STRICT_FROZEN

    modelo: ModeloId
    filing_year: FilingYear
    period: Period
    due_on: date
    period_state: OverviewPeriodState
    local_filing_state: OverviewLocalFilingState
    aeat_submission_state: OverviewAeatSubmissionState


class HomeProjectionV1(BaseModel):
    """Complete immutable input rendered by Home; it performs no reads itself."""

    model_config = _STRICT_FROZEN

    generated_at: datetime
    account: HomeAccountSession
    actions_state: HomeZoneState
    actions: tuple[HomeNextAction, ...] = ()
    declarations_state: HomeZoneState
    declarations: tuple[HomeDeclarationResume, ...] = ()
    ledger_state: HomeZoneState
    ledger: HomeLedgerReadiness | None = None
    agenda_state: HomeZoneState
    agenda_evidence_state: HomeZoneState
    agenda: tuple[HomeAgendaEntry, ...] = ()
    messages_state: HomeZoneState
    messages_requiring_attention: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _prevent_unavailable_zones_from_claiming_empty_or_zero(self) -> Self:
        pairs = (
            (self.actions_state, self.actions, "actions"),
            (self.declarations_state, self.declarations, "declarations"),
            (self.agenda_state, self.agenda, "agenda"),
        )
        for state, rows, name in pairs:
            if state.availability is not HomeAvailability.AVAILABLE and rows:
                raise ValueError(f"a non-available {name} zone cannot carry rows")
        if self.ledger_state.availability is HomeAvailability.AVAILABLE:
            if self.ledger is None:
                raise ValueError("an available Ledger zone requires readiness counts")
        elif self.ledger is not None:
            raise ValueError("a non-available Ledger zone cannot claim readiness counts")
        if self.messages_state.availability is HomeAvailability.AVAILABLE:
            if self.messages_requiring_attention is None:
                raise ValueError("an available Messages zone requires an attention count")
        elif self.messages_requiring_attention is not None:
            raise ValueError("a non-available Messages zone cannot claim an attention count")
        if len(self.actions) > 3:
            raise ValueError("Home may preview at most three next actions")
        ranks = tuple(item.rank for item in self.actions)
        if ranks != tuple(range(len(self.actions))):
            raise ValueError("Home next actions require unique contiguous ranks in display order")
        if len(self.agenda) > 3:
            raise ValueError("Home may preview at most three agenda entries")
        due_dates = tuple(item.due_on for item in self.agenda)
        if due_dates != tuple(sorted(due_dates)):
            raise ValueError("Home agenda entries must be chronological")
        evidence_unobserved = self.agenda_evidence_state.availability in {
            HomeAvailability.LOCKED,
            HomeAvailability.NEVER_CAPTURED,
            HomeAvailability.UNAVAILABLE,
        }
        if evidence_unobserved and any(
            item.aeat_submission_state is not OverviewAeatSubmissionState.NOT_OBSERVED for item in self.agenda
        ):
            raise ValueError("agenda entries cannot claim AEAT submission when AEAT evidence is not observable")
        return self


class HomeProjectionInput(BaseModel):
    """Already-local reader results and explicit authority state for Home."""

    model_config = _STRICT_FROZEN

    generated_at: datetime
    account: HomeAccountSession
    actions_state: HomeZoneState
    actions: tuple[HomeNextAction, ...] = ()
    declarations_state: HomeZoneState
    declarations: tuple[HomeDeclarationResume, ...] = ()
    ledger_state: HomeZoneState
    ledger_readiness: HomeLedgerReadiness | None = None
    agenda_state: HomeZoneState
    agenda_evidence_state: HomeZoneState
    overview_agenda: OverviewAgenda | None = None
    messages_state: HomeZoneState
    messages_requiring_attention: int | None = None

    @model_validator(mode="after")
    def _reject_duplicate_reader_identities(self) -> Self:
        declaration_ids = tuple(item.work_unit_id for item in self.declarations)
        if len(set(declaration_ids)) != len(declaration_ids):
            raise ValueError("Home declarations require unique work_unit_id values")
        action_keys = tuple(_action_semantic_key(item) for item in self.actions)
        if len(set(action_keys)) != len(action_keys):
            raise ValueError("Home actions require unique semantic identities")
        return self


def compose_home_projection(source: HomeProjectionInput) -> HomeProjectionV1:
    """Compose one immutable Home snapshot from canonical local read models."""
    return HomeProjectionV1(
        generated_at=source.generated_at,
        account=source.account,
        actions_state=source.actions_state,
        actions=_rank_actions(source.actions),
        declarations_state=source.declarations_state,
        declarations=_project_declarations(source.declarations),
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
        key=lambda item: (item.rank, _action_semantic_key(item)),
    )[:3]
    return tuple(item.model_copy(update={"rank": rank}) for rank, item in enumerate(ordered))


def _action_semantic_key(item: HomeNextAction) -> str:
    """Canonical ordering identity covering the complete declared action."""
    return item.model_dump_json(exclude={"rank"}, exclude_none=False)


def _project_declarations(declarations: tuple[HomeDeclarationResume, ...]) -> tuple[HomeDeclarationResume, ...]:
    return tuple(
        sorted(
            declarations,
            key=lambda unit: (
                str(unit.modelo),
                unit.filing_year,
                unit.period.registry_token,
                unit.work_unit_id,
            ),
        )
    )


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
