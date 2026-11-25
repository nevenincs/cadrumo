"""Focused public-contract tests for the host-neutral AEAT Sync TUI."""

from __future__ import annotations

from datetime import UTC, date, datetime
from threading import get_ident
from types import SimpleNamespace
from typing import cast

import pytest
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from .....application.aeat_sync.workspace import (
    AeatSyncOverviewArea,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceZone,
)
from .....application.live.notifications_read_operation import (
    NOTIFICATIONS_LIST_DEFINITION_ID,
    NotificationsListPublicResultV1,
    NotificationsSnapshotSummaryPublicV1,
)
from .....application.operations.models import OperationDefinitionId
from .....application.operator_actions.catalogue import (
    ActionCatalogue,
    ActionCatalogueEntry,
)
from .....application.operator_actions.models import ActionReference
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....core.operations import OperationTerminalCondition
from ...components.host import ScreenHostApp
from ...destination_alias import closed_destination_ids
from ...navigation import TuiScreenContextV1
from ...operations.controller_port import OperationControllerPort
from ...operations.modal import OperationModal, OperationModalSettledOutcomeV1
from ...tests.settling import settle
from ..controller import AeatSyncWorkspaceController
from ..models import (
    AeatSyncDestinationIdV1,
    AeatSyncOperationRequestV1,
)
from ..notifications_screen import AeatSyncNotificationsScreen
from ..overview_screen import AeatSyncOverviewScreen
from ..routes import AEAT_SYNC_ROUTES, resolve_aeat_sync_screen
from .aeat_sync_workspace_support import (
    AEAT_SYNC_INTENTIONAL_IDENTICAL_HU,
    BUCKET_ID,
    SUBJECT_KEY,
    aeat_sync_catalogue,
    aeat_sync_workspace_contracts,
    aeat_sync_workspace_controller,
    aeat_sync_workspace_projection,
    referenced_aeat_sync_keys,
    started_operation_controller,
    table_text,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("readiness_unavailable", (False, True))
async def test_stored_notifications_remain_readable_without_aeat_credentials(
    readiness_unavailable: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ...profile.tests.test_aeat_auth_setup import AeatAuthSetupDoor

    requests: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1, /) -> OperationControllerPort:
        requests.append(request)
        return started_operation_controller()

    door = AeatAuthSetupDoor()
    door.fail_read = readiness_unavailable
    controller = aeat_sync_workspace_controller(
        operation_handoff=handoff,
        overview_area=AeatSyncOverviewArea.NOTIFICATIONS,
        action_id="operator.live.notifications.list",
        operation_id=NOTIFICATIONS_LIST_DEFINITION_ID,
    )
    controller.aeat_auth_setup = door
    screen = AeatSyncOverviewScreen(controller)
    monkeypatch.setattr(screen, "_show_operation_modal", lambda _controller: None)
    async with ScreenHostApp(screen).run_test(size=(120, 65)) as pilot:
        await settle(pilot)
        button = screen.query_one(".aeat-sync-operation", Button)
        assert not button.disabled
        screen._set_operation_buttons_disabled(True)
        assert button.disabled
        screen._set_operation_buttons_disabled(False)
        assert not button.disabled
        button.scroll_visible(immediate=True)
        await settle(pilot)
        assert await pilot.click(button)
        await settle(pilot)
        assert [request.operation for request in requests] == [NOTIFICATIONS_LIST_DEFINITION_ID]
        assert button.disabled


@pytest.mark.asyncio
async def test_sync_screen_exposes_same_auth_editor_and_reloads_saved_readiness() -> None:
    from ...profile.aeat_auth_setup import AeatAuthSetupScreen
    from ...profile.tests.test_aeat_auth_setup import AeatAuthSetupDoor

    requests: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1, /) -> OperationControllerPort:
        requests.append(request)
        raise AssertionError("editing authentication never starts a remote read")

    door = AeatAuthSetupDoor()
    controller = aeat_sync_workspace_controller(operation_handoff=handoff)
    controller.aeat_auth_setup = door
    screen = AeatSyncOverviewScreen(controller)
    async with ScreenHostApp(screen).run_test(size=(120, 65)) as pilot:
        await settle(pilot)
        buttons = tuple(screen.query(".aeat-sync-operation"))
        assert buttons and all(button.disabled for button in buttons)
        assert tr("tui.aeat_auth.blocked") in str(screen.query_one("#aeat-sync-auth-readiness", Static).render())
        assert await pilot.click("#aeat-sync-auth-edit")
        await settle(pilot)
        assert isinstance(screen.app.screen, AeatAuthSetupScreen)
        editor = screen.app.screen
        from textual.widgets import Input, Select

        editor.query_one("#aeat-auth-method", Select).value = "clave_movil"
        editor.query_one("#aeat-auth-field-0", Input).value = "12345678Z"
        await editor._save()
        editor.action_close()
        await settle(pilot)
        assert controller.auth_readiness is not None and controller.auth_readiness.ready
        assert all(not button.disabled for button in screen.query(".aeat-sync-operation"))
        assert not requests
        door.fail_read = True
        await screen._refresh_auth()
        assert all(button.disabled for button in screen.query(".aeat-sync-operation"))


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_aeat_sync_namespace_matches_all_locales_and_hu_has_only_explicit_invariants(locale: str) -> None:
    """Keep the whole namespace translated, with a tiny HU allowlist.

    The count this once asserted (112, and 111 in the docstring before that) is
    replaced by the invariant it was standing in for. A frozen number cannot
    tell a key that was ADDED from one that was LOST -- it fails identically
    for both, and its only repair is to edit the number, which is why adding
    two section headings broke it while translating nothing. It also never
    checked the thing that matters: that the keys the code asks for exist.
    """
    english = aeat_sync_catalogue("en")
    translated = aeat_sync_catalogue(locale)
    assert english, "the English aeat_sync namespace is empty"
    assert set(translated) == set(english)

    referenced = referenced_aeat_sync_keys()
    assert referenced, "no literal aeat_sync keys were found; the scan is broken"
    missing = sorted(key for key in referenced if key not in translated)
    assert not missing, f"{locale} is missing keys the code asks for: {missing}"
    if locale == "hu":
        identical = {key for key, value in translated.items() if value == english[key]}
        assert identical == AEAT_SYNC_INTENTIONAL_IDENTICAL_HU


def test_six_routes_are_total_and_locked_projection_refuses_body() -> None:
    controller = aeat_sync_workspace_controller()
    assert tuple(route.zone for route in AEAT_SYNC_ROUTES) == tuple(AeatSyncWorkspaceZone)
    assert {route.destination for route in AEAT_SYNC_ROUTES} == closed_destination_ids(AeatSyncDestinationIdV1)
    assert isinstance(
        resolve_aeat_sync_screen(controller, controller.target(AeatSyncWorkspaceZone.OVERVIEW)),
        AeatSyncOverviewScreen,
    )
    locked = aeat_sync_workspace_controller(AeatSyncWorkspaceAvailability.LOCKED)
    assert not locked.can_open(AeatSyncWorkspaceZone.CENSUS)
    with pytest.raises(ValueError, match="not observable"):
        resolve_aeat_sync_screen(locked, locked.target(AeatSyncWorkspaceZone.CENSUS))


@pytest.mark.parametrize(
    "availability",
    (AeatSyncWorkspaceAvailability.NEVER_CAPTURED, AeatSyncWorkspaceAvailability.UNAVAILABLE),
)
def test_overview_remains_reachable_when_sources_are_unobservable(
    availability: AeatSyncWorkspaceAvailability,
) -> None:
    controller = aeat_sync_workspace_controller(availability)
    assert isinstance(
        resolve_aeat_sync_screen(controller, controller.target(AeatSyncWorkspaceZone.OVERVIEW)),
        AeatSyncOverviewScreen,
    )
    assert controller.state_for(AeatSyncWorkspaceZone.OVERVIEW).availability is availability
    assert not controller.can_open(AeatSyncWorkspaceZone.CENSUS)


@pytest.mark.asyncio
async def test_all_six_routes_mount_without_firing_a_host_handoff_or_leaking_scope() -> None:
    """Mounting a route is not an operator action, and never prints a coordinate.

    Two properties, and neither is about hiding the operator's own data from
    them -- that policy is retired, and the values these screens carry are the
    operator's to read.

    The first is that mounting fires no host handoff. A screen that pulled from
    the AEAT, or opened a document, merely because it was navigated to would
    take an action the operator never asked for.

    The second is a BACKSTOP, and is recorded as one rather than claimed as a
    proof: the subject key does not reach the frame. Trying to break it showed
    why it cannot currently fail -- the projector strips the coordinate, so no
    screen can reach one to print, and an attempt to leak it does not compile
    against the controller. The property is genuinely proven upstream, in
    test_output_physically_omits_protected_scope_payload_and_identity, which
    holds real sentinels and does fail when they survive. This line stays as
    cheap cover for the day a coordinate is plumbed through.

    An assertion that the operator's own NIF stays out of the frame stood here
    too. It was REMOVED rather than reworded: no fixture in this test carried
    that value, so it could never have failed, and a check that cannot fail
    reads as a safety property while providing none. The gates that do prove it
    -- against an exception message and against a status line, where the value
    is genuinely injected -- are further down this module and stay required.
    """
    calls: list[object] = []

    async def operation(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        return started_operation_controller()

    async def document(row: AeatSyncWorkspaceNotificationRowV1) -> None:
        calls.append(row)

    controller = aeat_sync_workspace_controller(operation_handoff=operation, notification_document_handoff=document)
    for zone in AeatSyncWorkspaceZone:
        screen = resolve_aeat_sync_screen(controller, controller.target(zone))
        async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            assert screen.query_one("#aeat-sync-navigation", DataTable).row_count == 6
            assert screen.query_one("#aeat-sync-rows", DataTable).row_count == 1
            rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
            assert SUBJECT_KEY not in rendered
    assert calls == []


@pytest.mark.asyncio
async def test_explicit_overview_operation_invokes_host_once_and_missing_host_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[AeatSyncOperationRequestV1] = []

    controllers: list[OperationControllerPort] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        controller = started_operation_controller()
        controllers.append(controller)
        return controller

    screen = AeatSyncOverviewScreen(aeat_sync_workspace_controller(operation_handoff=handoff))
    presented: list[OperationControllerPort] = []
    monkeypatch.setattr(screen, "_show_operation_modal", presented.append)
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        await pilot.click("#aeat-sync-operation-0")
        await settle(pilot)
        # The one-shot guard is the disabled control itself; nothing can hand off twice.
        assert screen.query_one("#aeat-sync-operation-0", Button).disabled
    assert calls == [
        AeatSyncOperationRequestV1(
            action=ActionReference(action_id="operator.profile.edit"),
            operation="user-profile.censo-review",
        )
    ]
    assert presented == controllers
    refused = AeatSyncOverviewScreen(aeat_sync_workspace_controller())
    async with ScreenHostApp[None](refused).run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        # Without a host door no control is offered; the refusal is stated instead.
        assert not refused.query("#aeat-sync-operation-0")
        assert tr("tui.aeat_sync.refusal.operation_handoff") in str(
            refused.query_one("#aeat-sync-status", Static).render()
        )


@pytest.mark.asyncio
async def test_language_repaint_preserves_tables_focus_and_consumed_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        return started_operation_controller()

    with override_settings(cadrumo_output_language="en"):
        screen = AeatSyncOverviewScreen(aeat_sync_workspace_controller(operation_handoff=handoff))
        monkeypatch.setattr(screen, "_show_operation_modal", lambda _controller: None)
        async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            navigation = screen.query_one("#aeat-sync-navigation", DataTable)
            rows = screen.query_one("#aeat-sync-rows", DataTable)
            navigation_keys = tuple(item.key.value for item in navigation.ordered_rows)
            row_keys = tuple(item.key.value for item in rows.ordered_rows)
            assert tr("tui.aeat_sync.column.area", locale="en") in table_text(navigation)
            button = screen.query_one("#aeat-sync-operation-0", Button)
            assert await pilot.click(button)
            await settle(pilot)
            assert button.disabled and len(calls) == 1
            rows.focus()
            await settle(pilot)
            assert screen.app.focused is rows
            with override_settings(cadrumo_output_language="es"):
                await screen.refresh_language()
                await settle(pilot)
                assert screen.query_one("#aeat-sync-navigation", DataTable) is navigation
                assert screen.query_one("#aeat-sync-rows", DataTable) is rows
                assert tuple(item.key.value for item in navigation.ordered_rows) == navigation_keys
                assert tuple(item.key.value for item in rows.ordered_rows) == row_keys
                assert tr("tui.aeat_sync.column.area", locale="es") in table_text(navigation)
                assert tr("tui.aeat_sync.availability.available", locale="es") in table_text(navigation)
                assert screen.app.focused is rows
                assert screen.query_one("#aeat-sync-operation-0", Button) is button
                assert button.disabled and len(calls) == 1


@pytest.mark.asyncio
async def test_language_repaint_restates_missing_operation_handoff_refusal() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = AeatSyncOverviewScreen(aeat_sync_workspace_controller())
        async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
            await settle(pilot)
            status = screen.query_one("#aeat-sync-status", Static)
            assert tr("tui.aeat_sync.refusal.operation_handoff", locale="en") in str(status.render())
            with override_settings(cadrumo_output_language="es"):
                await screen.refresh_language()
                await settle(pilot)
                assert tr("tui.aeat_sync.refusal.operation_handoff", locale="es") in str(status.render())
                assert not screen.query(".aeat-sync-operation")


@pytest.mark.asyncio
async def test_started_filed_pull_handoff_pushes_the_canonical_operation_modal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_controller = started_operation_controller()

    async def handoff(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        return started_controller

    screen = AeatSyncOverviewScreen(
        aeat_sync_workspace_controller(
            operation_handoff=handoff,
            overview_area=AeatSyncOverviewArea.FILED_DECLARATIONS,
            action_id="operator.live.filed.pull_all",
            operation_id="live.filed-history.pull",
        )
    )
    presented: list[tuple[OperationModal, object]] = []
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        monkeypatch.setattr(screen.app, "push_screen", lambda modal, callback: presented.append((modal, callback)))
        await pilot.click("#aeat-sync-operation-0")
        await settle(pilot)

    assert len(presented) == 1
    assert isinstance(presented[0][0], OperationModal)
    assert presented[0][0]._controller is started_controller
    assert presented[0][1] == screen._on_operation_settled


@pytest.mark.asyncio
async def test_missing_session_contract_is_visible_refusal_and_unread_notification_never_calls_document_door() -> None:
    unknown = AeatSyncOverviewScreen(
        AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            aeat_sync_workspace_projection(),
        )
    )
    async with ScreenHostApp[None](unknown).run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        assert not tuple(unknown.query(Button).results())
        assert str(unknown.query_one("#aeat-sync-status", Static).render())

    calls: list[AeatSyncWorkspaceNotificationRowV1] = []

    async def document(row: AeatSyncWorkspaceNotificationRowV1) -> None:
        calls.append(row)

    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        aeat_sync_workspace_projection(unread=True),
        notification_document_handoff=document,
        operation_contracts=aeat_sync_workspace_contracts(),
    )
    screen = AeatSyncNotificationsScreen(controller)
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        table = screen.query_one("#aeat-sync-rows", DataTable)
        table.focus()
        await pilot.press("enter")
        assert "documentos" in str(screen.query_one("#aeat-sync-status", Static).render()).lower()
    assert calls == []


def test_controller_admits_only_exact_singleton_pairs() -> None:
    controller = aeat_sync_workspace_controller()
    action = ActionReference(action_id="operator.profile.edit")
    operation: OperationDefinitionId = "user-profile.censo-review"
    assert controller.admitted_operation((action,), (operation,)) == AeatSyncOperationRequestV1(
        action=action, operation=operation
    )
    assert (
        controller.admitted_operation((ActionReference(action_id="operator.overview.explain"),), (operation,)) is None
    )


def test_controller_refuses_forged_contract_join_and_catalogue_command() -> None:
    """An operation ID alone cannot authorize a different action or command."""
    action = ActionReference(action_id="operator.profile.edit")
    operation: OperationDefinitionId = "user-profile.censo-review"
    forged_contract = aeat_sync_workspace_controller()
    forged_contract.operation_contracts = aeat_sync_workspace_contracts("operator.live.filed.pull")
    assert forged_contract.admitted_operation((action,), (operation,)) is None

    forged_catalogue = ActionCatalogue(
        entries=(
            ActionCatalogueEntry(
                action_id="operator.profile.edit",
                target_command_key="forged.command",
            ),
        )
    )
    canonical_guard = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        aeat_sync_workspace_projection(),
        action_catalogue=forged_catalogue,
        operation_contracts=aeat_sync_workspace_contracts(),
    )
    assert canonical_guard.admitted_operation((action,), (operation,)) is None


@pytest.mark.asyncio
async def test_successful_operation_refreshes_aeat_sync_off_ui_loop_and_rearms_button() -> None:
    filed_projection = aeat_sync_workspace_projection(
        overview_area=AeatSyncOverviewArea.FILED_DECLARATIONS,
        action_id="operator.live.filed.pull_all",
        operation_id="live.filed-history.pull",
    )
    refreshed = filed_projection.model_copy(deep=True)
    reads: list[int] = []

    def refresh() -> AeatSyncWorkspaceProjectionV1:
        reads.append(get_ident())
        return refreshed

    async def handoff(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        raise AssertionError("refresh cannot submit a second operation")

    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        filed_projection,
        operation_handoff=handoff,
        refresh_snapshot=refresh,
        operation_contracts=aeat_sync_workspace_contracts("operator.live.filed.pull_all", "live.filed-history.pull"),
    )
    screen = AeatSyncOverviewScreen(controller)
    succeeded = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(projection=SimpleNamespace(terminal_condition=OperationTerminalCondition.SUCCEEDED))
    )
    refused = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(projection=SimpleNamespace(terminal_condition=OperationTerminalCondition.REFUSED))
    )
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        screen._consumed_request_ids.add("aeat-sync-operation-0")
        ui_thread = get_ident()
        screen._on_operation_settled(refused)
        await settle(pilot)
        assert reads == []
        screen._on_operation_settled(succeeded)
        await settle(pilot)
        assert reads and reads[0] != ui_thread
        assert controller.projection is refreshed
        assert screen._consumed_request_ids == set()
        assert not screen.query_one("#aeat-sync-operation-1-0", Button).disabled


@pytest.mark.asyncio
async def test_successful_notification_list_projects_capture_times_and_row_counts() -> None:
    """The TUI renders only the registered public summary fields after settlement."""
    captured_at = datetime(2026, 9, 28, 12, 30, tzinfo=UTC)
    result = NotificationsListPublicResultV1(
        bucket_id=BUCKET_ID,
        count=2,
        rows=(
            NotificationsSnapshotSummaryPublicV1(
                snapshot_id="1" * 64,
                captured_at=captured_at,
                row_count=7,
            ),
            NotificationsSnapshotSummaryPublicV1(
                snapshot_id="2" * 64,
                captured_at=captured_at.replace(day=27),
                row_count=0,
            ),
        ),
    )
    projected: list[object] = []

    class _NotificationsListResultReader:
        async def read_notifications_list_result(self, projection: object) -> NotificationsListPublicResultV1:
            projected.append(projection)
            return result

    result_reader = _NotificationsListResultReader()

    async def handoff(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        return cast(OperationControllerPort, result_reader)

    request = AeatSyncOperationRequestV1(
        action=ActionReference(action_id="operator.live.notifications.list"),
        operation=NOTIFICATIONS_LIST_DEFINITION_ID,
    )
    screen = AeatSyncOverviewScreen(
        aeat_sync_workspace_controller(
            operation_handoff=handoff,
            overview_area=AeatSyncOverviewArea.NOTIFICATIONS,
            action_id="operator.live.notifications.list",
            operation_id=NOTIFICATIONS_LIST_DEFINITION_ID,
        )
    )
    operation_projection = SimpleNamespace(terminal_condition=OperationTerminalCondition.SUCCEEDED)
    settled = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(projection=operation_projection)
    )
    screen._active_operation_request = request
    screen._active_operation_controller = cast(OperationControllerPort, result_reader)

    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await settle(pilot)
        screen._on_operation_settled(settled)
        await settle(pilot)
        status = str(screen.query_one("#aeat-sync-status", Static).render())

    assert projected == [operation_projection]
    assert "2026-09-28T12:30:00+00:00" in status
    assert "2026-09-27T12:30:00+00:00" in status
    assert tr("tui.aeat_sync.status.items", count=2) in status
    assert tr("tui.aeat_sync.status.items", count=7) in status
    assert tr("tui.aeat_sync.status.items", count=0) in status
    assert "1" * 64 not in status and "2" * 64 not in status


@pytest.mark.asyncio
async def test_notification_focus_restores_by_projected_identity_across_refresh_resize_and_child_return() -> None:
    first = aeat_sync_workspace_projection(
        notification_specs=(
            ("notification-alpha", date(2026, 1, 1)),
            ("notification-beta", date(2026, 1, 2)),
            ("notification-gamma", date(2026, 1, 3)),
        )
    )
    reordered = aeat_sync_workspace_projection(
        notification_specs=(
            ("notification-gamma", date(2026, 1, 1)),
            ("notification-alpha", date(2026, 1, 2)),
            ("notification-beta", date(2026, 1, 3)),
        )
    )
    screen = AeatSyncNotificationsScreen(
        AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            first,
            operation_contracts=aeat_sync_workspace_contracts(),
        )
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 18)) as pilot:
        await settle(pilot)
        table = screen.query_one("#aeat-sync-rows", DataTable)
        table.focus()
        table.move_cursor(row=1)
        await settle(pilot)
        chosen = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        assert chosen == first.notifications[1].selection_key

        screen.refresh_projection(reordered)
        await settle(pilot)
        assert app.focused is table
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen
        assert table.scroll_y <= table.cursor_row < table.scroll_y + table.size.height

        await pilot.resize_terminal(100, 22)
        await settle(pilot)
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen
        assert table.scroll_y <= table.cursor_row < table.scroll_y + table.size.height

        child = Screen[None]()
        app.push_screen(child)
        await settle(pilot)
        child.dismiss(None)
        await settle(pilot)
        assert app.focused is table
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen
