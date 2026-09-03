"""Projection-only AEAT Sync controller with a closed operation handoff."""

from __future__ import annotations

from typing import Final, cast

from ....application.aeat_sync.workspace import (
    AEAT_SYNC_WORKSPACE_CONTRACT_VERSION,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneStateV1,
)
from ....application.operations.models import OperationDefinitionId
from ....application.operator_actions.models import ActionReference
from ..navigation import TuiScreenContextV1
from .models import (
    AeatSyncDestinationIdV1,
    AeatSyncOperationHandoffV1,
    AeatSyncOperationRequestV1,
    AeatSyncRouteTargetV1,
)

_DESTINATION_BY_ZONE: Final = {
    AeatSyncWorkspaceZone.OVERVIEW: "aeat_sync.overview",
    AeatSyncWorkspaceZone.CENSUS: "aeat_sync.census",
    AeatSyncWorkspaceZone.FILED_DECLARATIONS: "aeat_sync.filed_declarations",
    AeatSyncWorkspaceZone.NOTIFICATIONS: "aeat_sync.notifications",
    AeatSyncWorkspaceZone.EVIDENCE_COMPARISON: "aeat_sync.evidence_comparison",
    AeatSyncWorkspaceZone.RECONCILIATION: "aeat_sync.reconciliation",
}
_MUTATION_PAIRS: Final = frozenset(
    {
        ("operator.profile.edit", "user-profile.censo-review"),
        ("operator.live.filed.pull", "live.filed-history.pull"),
        ("operator.live.filed.pull_all", "live.filed-history.pull"),
    }
)


class AeatSyncWorkspaceController:
    """Custody of one preloaded workspace and explicitly admitted host handoff."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: AeatSyncWorkspaceProjectionV1,
        *,
        operation_handoff: AeatSyncOperationHandoffV1 | None = None,
    ) -> None:
        """Validate the outer context and retain only injected public facts."""
        if context.destination != "workbench.aeat_sync":
            raise ValueError("AEAT Sync requires the workbench.aeat_sync context")
        if projection.contract_version != AEAT_SYNC_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported AEAT Sync workspace projection contract")
        self.context = context
        self.projection = projection
        self.operation_handoff = operation_handoff
        self._states = {state.zone: state for state in projection.zones}

    def state_for(self, zone: AeatSyncWorkspaceZone) -> AeatSyncWorkspaceZoneStateV1:
        """Return the application-owned state without recategorising it."""
        return self._states[zone]

    def target(self, zone: AeatSyncWorkspaceZone) -> AeatSyncRouteTargetV1:
        """Build a semantic internal target without resolving I/O or a screen."""
        return AeatSyncRouteTargetV1(destination=cast("AeatSyncDestinationIdV1", _DESTINATION_BY_ZONE[zone]), zone=zone)

    def admitted_operation(
        self, actions: tuple[ActionReference, ...], operations: tuple[OperationDefinitionId, ...]
    ) -> AeatSyncOperationRequestV1 | None:
        """Expose only one of the three explicitly registered mutation pairings.

        The S397 projection admits action and operation axes independently.  This
        TUI layer deliberately does not infer a generic pairing: it can hand off
        only a singleton pair in the closed operator vocabulary above.
        """
        if len(actions) != 1 or len(operations) != 1:
            return None
        action, operation = actions[0], operations[0]
        if (str(action.action_id), str(operation)) not in _MUTATION_PAIRS:
            return None
        return AeatSyncOperationRequestV1(action=action, operation=operation)

    def can_open(self, zone: AeatSyncWorkspaceZone) -> bool:
        """Allow only observed current or stale projection zones to render bodies."""
        return self.state_for(zone).availability in {
            AeatSyncWorkspaceAvailability.AVAILABLE,
            AeatSyncWorkspaceAvailability.STALE,
        }


__all__ = ["AeatSyncWorkspaceController"]
