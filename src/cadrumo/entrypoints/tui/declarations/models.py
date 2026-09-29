"""Typed presentation and handoff contracts for Declarations screens."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel
from textual.screen import Screen

from ....application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
)
from ....application.modelo.declarations_workspace import (
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
)
from ....application.operator_actions.models import DeclaredNextAction
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import Period

type DeclarationsDestinationIdV1 = Literal[
    "declarations.overview",
    "declarations.revisions",
    "declarations.filing_history",
    "declarations.calendar",
    "declarations.modelo_workspace",
]


class DeclarationsCalendarScopeV1(StrEnum):
    """Closed, presentation-only calendar scopes."""

    ALL = "all"
    PAST = "past"
    UPCOMING = "upcoming"
    OVERDUE = "overdue"
    FILED = "filed"
    EVIDENCE_UNKNOWN = "evidence_unknown"


class DeclarationsRouteTargetV1(BaseModel):
    """One closed internal destination."""

    model_config = STRICT_FROZEN_CONFIG

    destination: DeclarationsDestinationIdV1
    zone: DeclarationsWorkspaceZone | None = None


class ModeloWorkspaceScreenFactoryV1(Protocol):
    """Injected factory for the existing host-neutral Modelo workspace."""

    def __call__(self, declaration: DeclarationsWorkspaceDeclarationRefV1, /) -> Screen[None]:
        """Build the child screen for exactly the selected declaration."""
        ...


@dataclass(frozen=True, slots=True)
class DeclarationsRefreshSnapshotV1:
    """Latest already-captured safe facts for the same declarations route."""

    projection: DeclarationsWorkspaceProjectionV1
    modelo_workspace_factory: ModeloWorkspaceScreenFactoryV1 | None
    calendar_projection: DeclarationsCalendarProjectionV1 | None


class RevisionHandoffV1(Protocol):
    """Injected navigation handoff for one calculation revision identity."""

    def __call__(self, revision: DeclarationsWorkspaceCalculationRevisionRefV1, /) -> None:
        """Open the selected calculation revision."""
        ...


class FilingHandoffV1(Protocol):
    """Injected navigation handoff for one filing-history identity."""

    def __call__(self, filing: DeclarationsWorkspaceFilingRefV1, /) -> None:
        """Open the selected filing-history entry."""
        ...


class CalendarEntryHandoffV1(Protocol):
    """Injected navigation handoff for one natural legal address."""

    def __call__(self, entry: DeclarationsCalendarEntryRefV1, /) -> None:
        """Open the selected safe calendar address."""
        ...


class CalendarRecoveryHandoffV1(Protocol):
    """Injected executor for the canonical excluded recovery action."""

    def __call__(self, action: DeclaredNextAction, entry: DeclarationsCalendarEntryRefV1, /) -> None:
        """Submit the exact pre-admitted recovery action for this address."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloWorkCreateResultV1:
    """The persisted outcome of one explicitly selected declaration address."""

    reused: bool
    advisory_keys: tuple[str, ...] = ()


class ModeloWorkCreateHandoffV1(Protocol):
    """Create or reopen work through the shared Modelo lifecycle command."""

    def __call__(self, modelo: str, filing_year: int, period: Period, /) -> ModeloWorkCreateResultV1:
        """Persist the selected work and report whether it already existed."""
        ...


__all__ = [
    "CalendarEntryHandoffV1",
    "CalendarRecoveryHandoffV1",
    "DeclarationsCalendarScopeV1",
    "DeclarationsDestinationIdV1",
    "DeclarationsRefreshSnapshotV1",
    "DeclarationsRouteTargetV1",
    "FilingHandoffV1",
    "ModeloWorkCreateHandoffV1",
    "ModeloWorkCreateResultV1",
    "ModeloWorkspaceScreenFactoryV1",
    "RevisionHandoffV1",
]
