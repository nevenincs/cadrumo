"""Projection-only AEAT Sync controller with a closed operation handoff."""

from __future__ import annotations

from ....application.aeat_sync.workspace import (
    AEAT_SYNC_WORKSPACE_CONTRACT_VERSION,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneStateV1,
)
from ....application.operations.models import OperationDefinitionId
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
)
from ....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogue
from ....application.operator_actions.models import ActionReference
from ..navigation import TuiScreenContextV1
from .models import (
    AEAT_SYNC_DESTINATION_BY_ZONE,
    AeatSyncNotificationDocumentHandoffV1,
    AeatSyncOperationHandoffV1,
    AeatSyncOperationRequestV1,
    AeatSyncRouteTargetV1,
)


def _singleton_operation_pair(
    actions: tuple[ActionReference, ...], operations: tuple[OperationDefinitionId, ...]
) -> tuple[ActionReference, OperationDefinitionId] | None:
    """Return the only candidate pair, refusing an under- or over-specified row."""
    if len(actions) != 1 or len(operations) != 1:
        return None
    return actions[0], operations[0]


def _is_canonical_action_admission(action_catalogue: ActionCatalogue, action_id: str) -> bool:
    """Require the injected action declaration to equal the canonical declaration."""
    try:
        canonical = OPERATOR_ACTION_CATALOGUE.lookup(action_id)
        admitted = action_catalogue.lookup(action_id)
    except KeyError:
        return False
    return admitted == canonical


def _operation_contract_for(
    operation_contracts: OperationPublicContractSetV1 | None,
    operation_id: str,
) -> OperationPublicDefinitionContractV1 | None:
    """Resolve one operation from the injected public contract set."""
    if operation_contracts is None:
        return None
    return next(
        (item for item in operation_contracts.definitions if str(item.definition_id) == operation_id),
        None,
    )


def _contract_admits_tui_action(
    contract: OperationPublicDefinitionContractV1 | None,
    action: ActionReference,
) -> bool:
    """Require the contract's exact action join and TUI frontend capability."""
    if contract is None or contract.action_reference != action:
        return False
    return OperationFrontendProjection.TUI in contract.permitted_frontends


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
        # No cast: the shared pairing is typed as the destination literal, so
        # the value arrives already narrowed. The local copy this replaced held
        # plain strings, and the cast that fixed up was the same one that would
        # have silently accepted a destination the routes do not declare.
        return AeatSyncRouteTargetV1(destination=AEAT_SYNC_DESTINATION_BY_ZONE[zone], zone=zone)

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
        only a singleton pair whose exact join is declared by the injected
        public operation contract.
        """
        pair = _singleton_operation_pair(actions, operations)
        if pair is None:
            return None
        action, operation = pair
        action_id = str(action.action_id)
        if not _is_canonical_action_admission(self.action_catalogue, action_id):
            return None
        contract = _operation_contract_for(self.operation_contracts, str(operation))
        if not _contract_admits_tui_action(contract, action):
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
