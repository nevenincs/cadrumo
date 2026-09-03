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
from ....application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogue
from ....application.operator_actions.models import ActionReference
from ..navigation import TuiScreenContextV1
from .models import (
    AeatSyncDestinationIdV1,
    AeatSyncNotificationDocumentHandoffV1,
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
_EXPECTED_ACTION_COMMANDS: Final = {
    "operator.profile.edit": "config.profile.edit",
    "operator.live.filed.pull": "app.live.filed.pull",
    "operator.live.filed.pull_all": "app.live.filed.pull_all",
}
_CANONICAL_OPERATION_IDS: Final = frozenset({"user-profile.censo-review", "live.filed-history.pull"})


class AeatSyncWorkspaceController:
    """Custody of one preloaded workspace and explicitly admitted host handoff."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: AeatSyncWorkspaceProjectionV1,
        *,
        operation_handoff: AeatSyncOperationHandoffV1 | None = None,
        notification_document_handoff: AeatSyncNotificationDocumentHandoffV1 | None = None,
        action_catalogue: ActionCatalogue = OPERATOR_ACTION_CATALOGUE,
        operation_contracts: OperationPublicContractSetV1 | None = None,
    ) -> None:
        """Validate the outer context and retain only injected public facts."""
        if context.destination != "workbench.aeat_sync":
            raise ValueError("AEAT Sync requires the workbench.aeat_sync context")
        if projection.contract_version != AEAT_SYNC_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported AEAT Sync workspace projection contract")
        self.context = context
        self.projection = projection
        self.operation_handoff = operation_handoff
        self.notification_document_handoff = notification_document_handoff
        self.action_catalogue = action_catalogue
        self.operation_contracts = operation_contracts
        self._states = {state.zone: state for state in projection.zones}

    def state_for(self, zone: AeatSyncWorkspaceZone) -> AeatSyncWorkspaceZoneStateV1:
        """Return the application-owned state without recategorising it."""
        return self._states[zone]

    def target(self, zone: AeatSyncWorkspaceZone) -> AeatSyncRouteTargetV1:
        """Build a semantic internal target without resolving I/O or a screen."""
        return AeatSyncRouteTargetV1(destination=cast("AeatSyncDestinationIdV1", _DESTINATION_BY_ZONE[zone]), zone=zone)

    def replace_projection(self, projection: AeatSyncWorkspaceProjectionV1) -> None:
        """Replace a preloaded snapshot without changing the owning host.

        Refresh is deliberately an explicit application handoff.  This
        controller never loads a repository or starts a network operation.
        """
        if projection.contract_version != AEAT_SYNC_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported AEAT Sync workspace projection contract")
        self.projection = projection
        self._states = {state.zone: state for state in projection.zones}

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
        action_id = str(action.action_id)
        operation_id = str(operation)
        if (action_id, operation_id) not in _MUTATION_PAIRS:
            return None
        try:
            canonical = OPERATOR_ACTION_CATALOGUE.lookup(action_id)
            admitted = self.action_catalogue.lookup(action_id)
        except KeyError:
            return None
        if admitted != canonical or canonical.target_command_key != _EXPECTED_ACTION_COMMANDS[action_id]:
            return None
        if operation_id not in _CANONICAL_OPERATION_IDS:
            return None
        if self.operation_contracts is not None:
            contract = next(
                (item for item in self.operation_contracts.definitions if str(item.definition_id) == operation_id),
                None,
            )
            if contract is None:
                return None
            if OperationFrontendProjection.TUI not in contract.permitted_frontends:
                return None
        return AeatSyncOperationRequestV1(action=action, operation=operation)

    async def retrieve_notification_document(self, row: object) -> bool:
        """Open a notification document only after an explicit read fact.

        ``row`` is accepted as ``object`` at this boundary so a stale event
        cannot smuggle an arbitrary object into the door.  The exact public
        row type is checked before the callback is reached.
        """
        from ....application.aeat_sync.workspace import (
            AeatSyncNotificationReadState,
            AeatSyncWorkspaceNotificationRowV1,
        )

        if not isinstance(row, AeatSyncWorkspaceNotificationRowV1):
            return False
        if row.read_state is not AeatSyncNotificationReadState.READ:
            return False
        handoff = self.notification_document_handoff
        if handoff is None:
            return False
        await handoff(row)
        return True

    def can_open(self, zone: AeatSyncWorkspaceZone) -> bool:
        """Allow only observed current or stale projection zones to render bodies."""
        return self.state_for(zone).availability in {
            AeatSyncWorkspaceAvailability.AVAILABLE,
            AeatSyncWorkspaceAvailability.STALE,
        }


__all__ = ["AeatSyncWorkspaceController"]
