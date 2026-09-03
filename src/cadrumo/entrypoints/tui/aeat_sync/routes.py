"""Closed AEAT Sync route catalogue and injected root factory."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, get_args

from textual.screen import Screen

from ....application.aeat_sync.workspace import AeatSyncWorkspaceProjectionV1, AeatSyncWorkspaceZone
from ....application.operations.registry import OperationPublicContractSetV1
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from .controller import AeatSyncWorkspaceController
from .models import (
    AeatSyncDestinationIdV1,
    AeatSyncNotificationDocumentHandoffV1,
    AeatSyncOperationHandoffV1,
    AeatSyncRouteTargetV1,
)
from .screens import (
    AeatSyncCensusScreen,
    AeatSyncEvidenceComparisonScreen,
    AeatSyncFiledDeclarationsScreen,
    AeatSyncNotificationsScreen,
    AeatSyncOverviewScreen,
    AeatSyncReconciliationScreen,
    AeatSyncWorkspaceScreen,
)

type AeatSyncInternalScreenFactoryV1 = Callable[[AeatSyncWorkspaceController], AeatSyncWorkspaceScreen]


@dataclass(frozen=True, slots=True)
class AeatSyncRouteV1:
    """One total internal route over one public projection zone."""

    destination: AeatSyncDestinationIdV1
    zone: AeatSyncWorkspaceZone
    factory: AeatSyncInternalScreenFactoryV1


AEAT_SYNC_ROUTES: Final = (
    AeatSyncRouteV1("aeat_sync.overview", AeatSyncWorkspaceZone.OVERVIEW, AeatSyncOverviewScreen),
    AeatSyncRouteV1("aeat_sync.census", AeatSyncWorkspaceZone.CENSUS, AeatSyncCensusScreen),
    AeatSyncRouteV1(
        "aeat_sync.filed_declarations", AeatSyncWorkspaceZone.FILED_DECLARATIONS, AeatSyncFiledDeclarationsScreen
    ),
    AeatSyncRouteV1("aeat_sync.notifications", AeatSyncWorkspaceZone.NOTIFICATIONS, AeatSyncNotificationsScreen),
    AeatSyncRouteV1(
        "aeat_sync.evidence_comparison", AeatSyncWorkspaceZone.EVIDENCE_COMPARISON, AeatSyncEvidenceComparisonScreen
    ),
    AeatSyncRouteV1("aeat_sync.reconciliation", AeatSyncWorkspaceZone.RECONCILIATION, AeatSyncReconciliationScreen),
)
_ROUTES_BY_ID: Final = {route.destination: route for route in AEAT_SYNC_ROUTES}


def declared_aeat_sync_destination_ids() -> frozenset[str]:
    """Read the closed internal destination catalogue from its literal type."""
    return frozenset(item for item in get_args(AeatSyncDestinationIdV1.__value__) if isinstance(item, str))


if frozenset(_ROUTES_BY_ID) != declared_aeat_sync_destination_ids() or tuple(
    route.zone for route in AEAT_SYNC_ROUTES
) != tuple(AeatSyncWorkspaceZone):
    raise ValueError("AEAT Sync routes must cover the closed zone catalogue exactly once and in order")


def resolve_aeat_sync_screen(controller: AeatSyncWorkspaceController, target: AeatSyncRouteTargetV1) -> Screen[None]:
    """Resolve an observable internal body without application reads or network I/O."""
    route = _ROUTES_BY_ID[target.destination]
    if route.zone is not target.zone:
        raise ValueError("AEAT Sync target destination and zone disagree")
    if not controller.can_open(route.zone):
        raise ValueError("AEAT Sync source is not observable")
    return route.factory(controller)


def aeat_sync_screen_factory(
    projection: AeatSyncWorkspaceProjectionV1,
    *,
    operation_handoff: AeatSyncOperationHandoffV1 | None = None,
    notification_document_handoff: AeatSyncNotificationDocumentHandoffV1 | None = None,
    operation_contracts: OperationPublicContractSetV1 | None = None,
) -> TuiScreenFactoryV1:
    """Bind only a preloaded safe projection and an optional typed host handoff."""

    def create(context: TuiScreenContextV1) -> Screen[None]:
        controller = AeatSyncWorkspaceController(
            context,
            projection,
            operation_handoff=operation_handoff,
            notification_document_handoff=notification_document_handoff,
            operation_contracts=operation_contracts,
        )
        return resolve_aeat_sync_screen(controller, controller.target(AeatSyncWorkspaceZone.OVERVIEW))

    return create


__all__ = [
    "AEAT_SYNC_ROUTES",
    "AeatSyncRouteV1",
    "aeat_sync_screen_factory",
    "declared_aeat_sync_destination_ids",
    "resolve_aeat_sync_screen",
]
