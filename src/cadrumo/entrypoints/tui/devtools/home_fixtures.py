"""Deterministic, non-sensitive Home projections for visual candidates.

These builders use only the application-owned Home records.  They never read
profile state, persistence, or remote services, and every call builds a fresh
frozen projection for an isolated candidate run.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ....application.operator_actions.models import ActionReference, DeclaredNextAction
from ....application.overview.home import (
    HomeAccountSession,
    HomeAgendaEntry,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeLedgerReadiness,
    HomeNextAction,
    HomeProjectionV1,
    HomeSessionPosture,
    HomeZoneState,
)
from ....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ....core.period import Period

_GENERATED_AT: Final[datetime] = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
_DUE_ON: Final[date] = date(2026, 10, 20)
_PROFILE_LABEL: Final[str] = "Fixture profile"


class HomeFixtureScenario(StrEnum):
    """Closed synthetic states used by the Home candidate harness."""

    READY = "ready"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"
    EMPTY = "empty"
    BLOCKED = "blocked"


def _zone(
    availability: HomeAvailability,
    *,
    reason_code: str | None = None,
    observed_at: datetime | None = None,
) -> HomeZoneState:
    """Build one explicit zone state with deterministic evidence."""
    return HomeZoneState(
        availability=availability,
        observed_at=observed_at,
        reason_code=reason_code,
    )


def _available() -> HomeZoneState:
    return _zone(HomeAvailability.AVAILABLE, observed_at=_GENERATED_AT)


def _period() -> Period:
    """Build a fresh typed period coordinate for one nested record."""
    return Period.from_year_and_code(2026, "3T")


def _account(posture: HomeSessionPosture = HomeSessionPosture.ACTIVE) -> HomeAccountSession:
    return HomeAccountSession(
        posture=posture,
        profile_label=None if posture is HomeSessionPosture.NO_PROFILE else _PROFILE_LABEL,
    )


def _action(*, action_id: str, reason_code: str) -> HomeNextAction:
    return HomeNextAction(
        rank=0,
        action=DeclaredNextAction(action=ActionReference(action_id=action_id)),
        reason_code=reason_code,
    )


def _declaration(*, state: HomeDeclarationState = HomeDeclarationState.NEEDS_REVIEW) -> HomeDeclarationResume:
    return HomeDeclarationResume(
        work_unit_id="a" * 64,
        modelo="303",
        filing_year=2026,
        period=_period(),
        name="Fixture declaration",
        state=state,
        revision_id="fixture-revision",
    )


def _ledger(*, requiring_review: int = 1) -> HomeLedgerReadiness:
    return HomeLedgerReadiness(
        entries=4,
        requiring_review=requiring_review,
        unclassified=1,
        missing_evidence=1,
    )


def _agenda(*, aeat_state: OverviewAeatSubmissionState) -> HomeAgendaEntry:
    return HomeAgendaEntry(
        modelo="303",
        filing_year=2026,
        period=_period(),
        due_on=_DUE_ON,
        period_state=OverviewPeriodState.DUE,
        local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
        aeat_submission_state=aeat_state,
    )


def _ready() -> HomeProjectionV1:
    return HomeProjectionV1(
        generated_at=_GENERATED_AT,
        account=_account(),
        actions_state=_available(),
        actions=(_action(action_id="fixture.review", reason_code="fixture.review"),),
        declarations_state=_available(),
        declarations=(_declaration(state=HomeDeclarationState.READY),),
        ledger_state=_available(),
        ledger=_ledger(requiring_review=0),
        agenda_state=_available(),
        agenda_evidence_state=_available(),
        agenda=(_agenda(aeat_state=OverviewAeatSubmissionState.ACCEPTED),),
        messages_state=_available(),
        messages_requiring_attention=0,
    )


def _locked() -> HomeProjectionV1:
    locked = _zone(HomeAvailability.LOCKED, reason_code="fixture.profile_locked")
    return HomeProjectionV1(
        generated_at=_GENERATED_AT,
        account=_account(HomeSessionPosture.LOCKED),
        actions_state=locked,
        declarations_state=locked,
        ledger_state=locked,
        agenda_state=locked,
        agenda_evidence_state=locked,
        messages_state=locked,
    )


def _stale() -> HomeProjectionV1:
    stale = _zone(HomeAvailability.STALE, reason_code="fixture.observation_stale", observed_at=_GENERATED_AT)
    return HomeProjectionV1(
        generated_at=_GENERATED_AT,
        account=_account(),
        actions_state=stale,
        declarations_state=stale,
        ledger_state=stale,
        agenda_state=stale,
        agenda_evidence_state=stale,
        messages_state=stale,
    )


def _never_captured() -> HomeProjectionV1:
    never_captured = _zone(HomeAvailability.NEVER_CAPTURED, reason_code="fixture.never_captured")
    return HomeProjectionV1(
        generated_at=_GENERATED_AT,
        account=_account(HomeSessionPosture.NO_PROFILE),
        actions_state=never_captured,
        declarations_state=never_captured,
        ledger_state=never_captured,
        agenda_state=never_captured,
        agenda_evidence_state=never_captured,
        messages_state=never_captured,
    )


def _unavailable() -> HomeProjectionV1:
    unavailable = _zone(HomeAvailability.UNAVAILABLE, reason_code="fixture.source_unavailable")
    return HomeProjectionV1(
        generated_at=_GENERATED_AT,
        account=_account(),
        actions_state=unavailable,
        declarations_state=unavailable,
        ledger_state=unavailable,
        agenda_state=unavailable,
        agenda_evidence_state=unavailable,
        messages_state=unavailable,
    )


def _empty() -> HomeProjectionV1:
    available = _available()
    return HomeProjectionV1(
        generated_at=_GENERATED_AT,
        account=_account(),
        actions_state=available,
        declarations_state=available,
        ledger_state=available,
        ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
        agenda_state=available,
        agenda_evidence_state=available,
        messages_state=available,
        messages_requiring_attention=0,
    )


def _blocked() -> HomeProjectionV1:
    return HomeProjectionV1(
        generated_at=_GENERATED_AT,
        account=_account(),
        actions_state=_available(),
        actions=(_action(action_id="fixture.resolve_blocker", reason_code="fixture.blocked"),),
        declarations_state=_available(),
        declarations=(_declaration(),),
        ledger_state=_available(),
        ledger=_ledger(requiring_review=3),
        agenda_state=_available(),
        agenda_evidence_state=_available(),
        agenda=(_agenda(aeat_state=OverviewAeatSubmissionState.NOT_OBSERVED),),
        messages_state=_available(),
        messages_requiring_attention=1,
    )


HomeFixtureBuilder = Callable[[], HomeProjectionV1]

HOME_FIXTURE_SCENARIOS: Final[Mapping[HomeFixtureScenario, HomeFixtureBuilder]] = MappingProxyType(
    {
        HomeFixtureScenario.READY: _ready,
        HomeFixtureScenario.LOCKED: _locked,
        HomeFixtureScenario.STALE: _stale,
        HomeFixtureScenario.NEVER_CAPTURED: _never_captured,
        HomeFixtureScenario.UNAVAILABLE: _unavailable,
        HomeFixtureScenario.EMPTY: _empty,
        HomeFixtureScenario.BLOCKED: _blocked,
    }
)
"""Closed scenario-to-fresh-builder mapping for candidate comparisons."""

if frozenset(HOME_FIXTURE_SCENARIOS) != frozenset(HomeFixtureScenario):
    raise ValueError("Home fixture scenario mapping must cover the closed scenario enum exactly")


def build_home_projection_fixture(scenario: HomeFixtureScenario | str) -> HomeProjectionV1:
    """Build a fresh immutable projection for one closed synthetic scenario."""
    try:
        resolved = HomeFixtureScenario(scenario)
    except ValueError as error:
        accepted = ", ".join(item.value for item in HomeFixtureScenario)
        raise ValueError(f"unknown Home fixture scenario {scenario!r}; accepted: {accepted}") from error
    return HOME_FIXTURE_SCENARIOS[resolved]()


__all__ = [
    "HOME_FIXTURE_SCENARIOS",
    "HomeFixtureBuilder",
    "HomeFixtureScenario",
    "build_home_projection_fixture",
]
