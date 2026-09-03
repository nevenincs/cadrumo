"""Typed presentation and handoff contracts for Declarations screens."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel

from ....application.modelo.declarations_workspace import (
    DeclarationsWorkspaceCalculationRevisionRefV1,
    DeclarationsWorkspaceDeclarationRefV1,
    DeclarationsWorkspaceFilingRefV1,
    DeclarationsWorkspaceZone,
)
from ....core.models import STRICT_FROZEN_CONFIG

type DeclarationsDestinationIdV1 = Literal[
    "declarations.overview",
    "declarations.revisions",
    "declarations.filing_history",
    "declarations.modelo_workspace",
]


class DeclarationsRouteTargetV1(BaseModel):
    """One closed internal destination."""

    model_config = STRICT_FROZEN_CONFIG

    destination: DeclarationsDestinationIdV1
    zone: DeclarationsWorkspaceZone | None = None


class DeclarationHandoffV1(Protocol):
    """Injected navigation handoff for an application-projected declaration."""

    def __call__(self, declaration: DeclarationsWorkspaceDeclarationRefV1, /) -> None: ...


class RevisionHandoffV1(Protocol):
    """Injected navigation handoff for one calculation revision identity."""

    def __call__(self, revision: DeclarationsWorkspaceCalculationRevisionRefV1, /) -> None: ...


class FilingHandoffV1(Protocol):
    """Injected navigation handoff for one filing-history identity."""

    def __call__(self, filing: DeclarationsWorkspaceFilingRefV1, /) -> None: ...


__all__ = [
    "DeclarationHandoffV1",
    "DeclarationsDestinationIdV1",
    "DeclarationsRouteTargetV1",
    "FilingHandoffV1",
    "RevisionHandoffV1",
]
