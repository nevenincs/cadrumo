"""Focused public-contract tests for the host-neutral AEAT Sync TUI."""

from __future__ import annotations

import pytest

from .....application.aeat_sync.workspace import (
    AEAT_SYNC_WORKSPACE_CONTRACT_VERSION,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneStateV1,
)
from .....application.operations.models import OperationDefinitionId
from .....application.operator_actions.models import ActionReference
from ...navigation import TuiScreenContextV1
from ..controller import AeatSyncWorkspaceController
from ..models import AeatSyncOperationRequestV1
from ..routes import AEAT_SYNC_ROUTES, declared_aeat_sync_destination_ids, resolve_aeat_sync_screen
from ..screens import AeatSyncOverviewScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _projection(
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
) -> AeatSyncWorkspaceProjectionV1:
    """Construct a safe empty snapshot for TUI contract tests without I/O."""
    return AeatSyncWorkspaceProjectionV1.model_construct(
        contract_version=AEAT_SYNC_WORKSPACE_CONTRACT_VERSION,
        zones=tuple(
            AeatSyncWorkspaceZoneStateV1.model_construct(
                zone=zone,
                availability=availability,
                sources=(),
                item_count=0
                if availability in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}
                else None,
            )
            for zone in AeatSyncWorkspaceZone
        ),
        overview=(),
        census=(),
        filed_declarations=(),
        notifications=(),
        evidence_comparison=(),
        reconciliation=(),
    )


def _controller(
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
) -> AeatSyncWorkspaceController:
    """Bind one honest outer AEAT Sync context to the public empty snapshot."""
    return AeatSyncWorkspaceController(TuiScreenContextV1(destination="workbench.aeat_sync"), _projection(availability))


def test_six_routes_are_total_ordered_and_resolve_an_active_projection_body() -> None:
    """Every S397 zone has one stable screen and no inactive zone is mounted."""
    controller = _controller()
    assert tuple(route.zone for route in AEAT_SYNC_ROUTES) == tuple(AeatSyncWorkspaceZone)
    assert {route.destination for route in AEAT_SYNC_ROUTES} == declared_aeat_sync_destination_ids()
    screen = resolve_aeat_sync_screen(controller, controller.target(AeatSyncWorkspaceZone.OVERVIEW))
    assert isinstance(screen, AeatSyncOverviewScreen)
    assert screen.controller is controller


def test_unobservable_zone_is_refused_instead_of_masquerading_as_empty() -> None:
    """Locked and never-captured sources cannot be routed as empty bodies."""
    controller = _controller(AeatSyncWorkspaceAvailability.LOCKED)
    assert not controller.can_open(AeatSyncWorkspaceZone.CENSUS)
    with pytest.raises(ValueError, match="not observable"):
        resolve_aeat_sync_screen(controller, controller.target(AeatSyncWorkspaceZone.CENSUS))


@pytest.mark.parametrize(
    ("action_id", "operation_id"),
    [
        ("operator.profile.edit", "user-profile.censo-review"),
        ("operator.live.filed.pull", "live.filed-history.pull"),
        ("operator.live.filed.pull_all", "live.filed-history.pull"),
    ],
)
def test_only_registered_explicit_pairs_become_host_operation_requests(action_id: str, operation_id: str) -> None:
    """No row action can become a generic network or write invocation."""
    action = ActionReference(action_id=action_id)
    operation = operation_id
    request = _controller().admitted_operation((action,), (operation,))
    assert request == AeatSyncOperationRequestV1(action=action, operation=operation)


def test_read_or_ambiguous_axes_are_not_inferred_into_mutation_requests() -> None:
    """Read actions and arbitrary Cartesian products remain presentation-only."""
    controller = _controller()
    read = ActionReference(action_id="operator.overview.explain")
    pull = ActionReference(action_id="operator.live.filed.pull")
    operation: OperationDefinitionId = "live.filed-history.pull"
    assert controller.admitted_operation((read,), (operation,)) is None
    assert controller.admitted_operation((pull, read), (operation,)) is None
    assert controller.admitted_operation((pull,), ()) is None


def test_controller_refuses_another_outer_destination() -> None:
    """The workspace cannot be constructed outside its admitted root destination."""
    with pytest.raises(ValueError, match=r"workbench\.aeat_sync"):
        AeatSyncWorkspaceController(TuiScreenContextV1(destination="workbench.home"), _projection())
