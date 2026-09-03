"""Focused public-contract tests for the host-neutral AEAT Sync TUI."""

from __future__ import annotations

import pytest
from textual.widgets import Button, DataTable, Static

from .....application.aeat_sync.tests.test_workspace import _action, _census, _fact, _projection as project_fixture
from .....application.aeat_sync.workspace import AeatSyncWorkspaceAvailability, AeatSyncWorkspaceProjectionV1, AeatSyncWorkspaceZone
from .....application.operations.models import OperationDefinitionId
from .....application.operator_actions.models import ActionReference
from ...components.host import ScreenHostApp
from ...navigation import TuiScreenContextV1
from ..controller import AeatSyncWorkspaceController
from ..models import AeatSyncOperationRequestV1
from ..routes import AEAT_SYNC_ROUTES, declared_aeat_sync_destination_ids, resolve_aeat_sync_screen
from ..screens import AeatSyncCensusScreen, AeatSyncOverviewScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _projection(
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
) -> AeatSyncWorkspaceProjectionV1:
    """Project real S397 facts; never bypass its validation with model construction."""
    if availability is not AeatSyncWorkspaceAvailability.AVAILABLE:
        return project_fixture(
            zone_observations=tuple(
                item.model_copy(
                    update={
                        "sources": tuple(
                            source.model_copy(
                                update={
                                    "availability": availability,
                                    "observed_at": None,
                                    "item_count": None,
                                    "refusal": "aeat.sync.source.refused",
                                }
                            )
                            for source in item.sources
                        )
                    }
                )
                for item in project_fixture().zones
            )
        )
    return project_fixture(
        census=(
            _fact(
                _census().model_copy(
                    update={
                        "supported_actions": (_action("operator.profile.edit"),),
                        "supported_operations": ("user-profile.censo-review",),
                    }
                )
            ),
        )
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


@pytest.mark.asyncio
async def test_all_six_real_projected_bodies_mount_and_redact_scope_values() -> None:
    """Every concrete route renders validated safe facts, not an empty surrogate."""
    controller = _controller()
    for zone in AeatSyncWorkspaceZone:
        screen = resolve_aeat_sync_screen(controller, controller.target(zone))
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert screen.query_one("#aeat-sync-navigation", DataTable).row_count == 6
            assert screen.query_one("#aeat-sync-rows", DataTable).row_count >= 1
            rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
            assert "private-subject" not in rendered
            assert "notification-private" not in rendered


@pytest.mark.asyncio
async def test_census_button_hands_exact_admitted_request_to_host_once_and_refuses_without_host() -> None:
    """A rendered mutation button uses only the exact S397-admitted pairing."""
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> None:
        calls.append(request)

    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"), _projection(), operation_handoff=handoff
    )
    screen = AeatSyncCensusScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.click("#aeat-sync-operation-0")
        assert calls == [
            AeatSyncOperationRequestV1(
                action=ActionReference(action_id="operator.profile.edit"), operation="user-profile.censo-review"
            )
        ]
        assert "private-subject" not in "\n".join(str(widget.render()) for widget in screen.query(Static))
    refused = AeatSyncCensusScreen(_controller())
    app = ScreenHostApp[None](refused)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.click("#aeat-sync-operation-0")
        assert "Operation handoff is unavailable." in str(refused.query_one("#aeat-sync-status", Static).render())
