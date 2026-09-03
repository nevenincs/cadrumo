"""Focused public-contract tests for the host-neutral AEAT Sync TUI."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

import pytest
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from .....application.aeat_sync.workspace import (
    AeatSyncAeatObservationState,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncDocumentCustodyState,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncNotificationCategory,
    AeatSyncNotificationReadState,
    AeatSyncOverviewArea,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCensusRowV1,
    AeatSyncWorkspaceEvidenceComparisonRowV1,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceFiledDeclarationRowV1,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionV1,
    AeatSyncWorkspaceReconciliationRowV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceSourceObservationV1,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    aeat_sync_workspace_sources,
    project_aeat_sync_workspace,
)
from .....application.operations.models import OperationDefinitionId
from .....application.operations.registry import OperationPublicContractSetV1
from .....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogue, ActionCatalogueEntry
from .....application.operator_actions.models import ActionReference
from .....application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION,
    build_censal_operation_registration,
)
from .....core.i18n.render import I18N_STRICT_MISSING_KEYS, tr
from .....core.identity import BucketId
from .....core.period import Period
from .....domain.modelos.codes import ModeloCode
from ...components.host import ScreenHostApp
from ...navigation import TuiScreenContextV1
from ..controller import AeatSyncWorkspaceController
from ..models import (
    AeatSyncNotificationDocumentHandoffV1,
    AeatSyncOperationHandoffV1,
    AeatSyncOperationRequestV1,
)
from ..routes import AEAT_SYNC_ROUTES, declared_aeat_sync_destination_ids, resolve_aeat_sync_screen
from ..screens import AeatSyncNotificationsScreen, AeatSyncOverviewScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_T1 = datetime(2026, 1, 3, 10, tzinfo=UTC)
_T2 = datetime(2026, 1, 4, 11, tzinfo=UTC)
_BUCKET_ID = cast(BucketId, "11111111-1111-4111-8111-111111111111")
_SUBJECT_KEY = "private-subject"


def _source(
    source: AeatSyncWorkspaceSource, availability: AeatSyncWorkspaceAvailability
) -> AeatSyncWorkspaceSourceObservationV1:
    visible = availability in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}
    return AeatSyncWorkspaceSourceObservationV1(
        source=source,
        availability=availability,
        observed_at=_T2 if visible else None,
        refusal=None if availability is AeatSyncWorkspaceAvailability.AVAILABLE else "aeat.sync.source.refused",
        item_count=1 if visible else None,
    )


def _projection(
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
    *,
    unread: bool = False,
    unknown_pair: bool = False,
    notification_specs: tuple[tuple[str, date], ...] | None = None,
) -> AeatSyncWorkspaceProjectionV1:
    """Build through the public projector from local scoped facts."""
    observations = tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            sources=tuple(_source(source, availability) for source in aeat_sync_workspace_sources(zone)),
        )
        for zone in AeatSyncWorkspaceZone
    )
    if availability not in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}:
        return project_aeat_sync_workspace(
            bucket_id=_BUCKET_ID,
            subject_key=_SUBJECT_KEY,
            zone_observations=observations,
            action_catalogue=OPERATOR_ACTION_CATALOGUE,
            operation_contracts=_contracts(),
        )
    action = ActionReference(action_id="operator.live.notifications.list" if unknown_pair else "operator.profile.edit")
    overview_area = AeatSyncOverviewArea.NOTIFICATIONS if unknown_pair else AeatSyncOverviewArea.CENSUS
    overview = AeatSyncWorkspaceOverviewRowV1(
        area=overview_area,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=_T1,
        aeat_observed_at=_T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        supported_actions=(action,),
        supported_operations=() if unknown_pair else ("user-profile.censo-review",),
    )
    period = Period.from_year_and_code(2026, "1T")
    return project_aeat_sync_workspace(
        bucket_id=_BUCKET_ID,
        subject_key=_SUBJECT_KEY,
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=_contracts(),
        overview=(AeatSyncWorkspaceFactV1(_BUCKET_ID, _SUBJECT_KEY, overview),),
        census=(
            AeatSyncWorkspaceFactV1(
                _BUCKET_ID,
                _SUBJECT_KEY,
                AeatSyncWorkspaceCensusRowV1(
                    path="tax address", category=AeatSyncCensusCategory.ADDRESS, status=AeatSyncCensusStatus.CONFLICT
                ),
            ),
        ),
        filed_declarations=(
            AeatSyncWorkspaceFactV1(
                _BUCKET_ID,
                _SUBJECT_KEY,
                AeatSyncWorkspaceFiledDeclarationRowV1(
                    modelo=ModeloCode("130"),
                    filing_year=2026,
                    period=period,
                    local_filing_state=AeatSyncLocalFilingState.FILED,
                    local_filed_at=_T1,
                    aeat_observation_state=AeatSyncAeatObservationState.ACCEPTED,
                    aeat_observed_at=_T2,
                    justificante_state=AeatSyncJustificanteState.VERIFIED,
                    justificante_observed_at=_T2,
                ),
            ),
        ),
        notifications=tuple(
            AeatSyncWorkspaceFactV1(
                _BUCKET_ID,
                _SUBJECT_KEY,
                AeatSyncWorkspaceNotificationRowV1(
                    issued_on=issued_on,
                    read_on=None if unread else issued_on,
                    read_state=AeatSyncNotificationReadState.UNREAD if unread else AeatSyncNotificationReadState.READ,
                    category=AeatSyncNotificationCategory.FORMAL,
                    document_custody_state=(
                        AeatSyncDocumentCustodyState.NOT_CAPTURED if unread else AeatSyncDocumentCustodyState.HELD
                    ),
                    document_custody_observed_at=None if unread else _T2,
                ),
                private_identity=private_identity,
            )
            for private_identity, issued_on in (notification_specs or (("notification-private", date(2026, 1, 2)),))
        ),
        evidence_comparison=(
            AeatSyncWorkspaceFactV1(
                _BUCKET_ID,
                _SUBJECT_KEY,
                AeatSyncWorkspaceEvidenceComparisonRowV1(
                    modelo=ModeloCode("130"),
                    filing_year=2026,
                    period=period,
                    local_state=AeatSyncSourceState.PRESENT,
                    aeat_state=AeatSyncSourceState.ABSENT,
                    local_observed_at=_T1,
                    aeat_observed_at=_T2,
                    discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
                ),
            ),
        ),
        reconciliation=(
            AeatSyncWorkspaceFactV1(
                _BUCKET_ID,
                _SUBJECT_KEY,
                AeatSyncWorkspaceReconciliationRowV1(
                    modelo=ModeloCode("130"),
                    filing_year=2026,
                    period=period,
                    local_state=AeatSyncSourceState.PRESENT,
                    aeat_state=AeatSyncSourceState.ABSENT,
                    local_observed_at=_T1,
                    aeat_observed_at=_T2,
                    discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
                    reconciliation_state=AeatSyncReconciliationState.KEEP_LOCAL,
                ),
            ),
        ),
    )


def _contracts(action_id: str = "operator.profile.edit") -> OperationPublicContractSetV1:
    """Build a public contract whose operation/action join is explicit."""
    definition = CENSAL_OPERATION_DEFINITION.model_copy(
        update={"action_reference": ActionReference(action_id=action_id)}
    )
    return OperationPublicContractSetV1.build((build_censal_operation_registration(definition).contract,))


def _controller(
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
    *,
    operation_handoff: AeatSyncOperationHandoffV1 | None = None,
    notification_document_handoff: AeatSyncNotificationDocumentHandoffV1 | None = None,
) -> AeatSyncWorkspaceController:
    return AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        _projection(availability),
        operation_contracts=_contracts(),
        operation_handoff=operation_handoff,
        notification_document_handoff=notification_document_handoff,
    )


def test_six_routes_are_total_and_locked_projection_refuses_body() -> None:
    controller = _controller()
    assert tuple(route.zone for route in AEAT_SYNC_ROUTES) == tuple(AeatSyncWorkspaceZone)
    assert {route.destination for route in AEAT_SYNC_ROUTES} == declared_aeat_sync_destination_ids()
    assert isinstance(
        resolve_aeat_sync_screen(controller, controller.target(AeatSyncWorkspaceZone.OVERVIEW)),
        AeatSyncOverviewScreen,
    )
    locked = _controller(AeatSyncWorkspaceAvailability.LOCKED)
    assert not locked.can_open(AeatSyncWorkspaceZone.CENSUS)
    with pytest.raises(ValueError, match="not observable"):
        resolve_aeat_sync_screen(locked, locked.target(AeatSyncWorkspaceZone.CENSUS))


@pytest.mark.asyncio
async def test_all_six_routes_mount_redacted_without_mount_time_callbacks() -> None:
    calls: list[object] = []

    async def operation(request: AeatSyncOperationRequestV1) -> None:
        calls.append(request)

    async def document(row: AeatSyncWorkspaceNotificationRowV1) -> None:
        calls.append(row)

    controller = _controller(operation_handoff=operation, notification_document_handoff=document)
    for zone in AeatSyncWorkspaceZone:
        screen = resolve_aeat_sync_screen(controller, controller.target(zone))
        async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert screen.query_one("#aeat-sync-navigation", DataTable).row_count == 6
            assert screen.query_one("#aeat-sync-rows", DataTable).row_count == 1
            rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
            assert "private-subject" not in rendered
            assert "12345678Z" not in rendered
    assert calls == []


@pytest.mark.asyncio
async def test_explicit_overview_operation_invokes_host_once_and_missing_host_refuses() -> None:
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> None:
        calls.append(request)

    screen = AeatSyncOverviewScreen(_controller(operation_handoff=handoff))
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.click("#aeat-sync-operation-0")
        await pilot.click("#aeat-sync-operation-0")
    assert calls == [
        AeatSyncOperationRequestV1(
            action=ActionReference(action_id="operator.profile.edit"),
            operation="user-profile.censo-review",
        )
    ]
    refused = AeatSyncOverviewScreen(_controller())
    async with ScreenHostApp[None](refused).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.click("#aeat-sync-operation-0")
        assert tr("tui.aeat_sync.refusal.operation_handoff") in str(
            refused.query_one("#aeat-sync-status", Static).render()
        )


@pytest.mark.asyncio
async def test_unknown_pair_is_visible_refusal_and_unread_notification_never_calls_document_door() -> None:
    unknown = AeatSyncOverviewScreen(
        AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            _projection(unknown_pair=True),
            operation_contracts=_contracts(),
        )
    )
    async with ScreenHostApp[None](unknown).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert not tuple(unknown.query(Button).results())
        assert str(unknown.query_one("#aeat-sync-status", Static).render())

    calls: list[AeatSyncWorkspaceNotificationRowV1] = []

    async def document(row: AeatSyncWorkspaceNotificationRowV1) -> None:
        calls.append(row)

    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        _projection(unread=True),
        notification_document_handoff=document,
        operation_contracts=_contracts(),
    )
    screen = AeatSyncNotificationsScreen(controller)
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        table = screen.query_one("#aeat-sync-rows", DataTable)
        table.focus()
        await pilot.press("enter")
        assert "documentos" in str(screen.query_one("#aeat-sync-status", Static).render()).lower()
    assert calls == []


def test_controller_admits_only_exact_singleton_pairs() -> None:
    controller = _controller()
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
    forged_contract = _controller()
    forged_contract.operation_contracts = _contracts("operator.live.filed.pull")
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
        _projection(),
        action_catalogue=forged_catalogue,
        operation_contracts=_contracts(),
    )
    assert canonical_guard.admitted_operation((action,), (operation,)) is None


@pytest.mark.asyncio
async def test_notification_focus_restores_by_projected_identity_across_refresh_resize_and_child_return() -> None:
    first = _projection(
        notification_specs=(
            ("notification-alpha", date(2026, 1, 1)),
            ("notification-beta", date(2026, 1, 2)),
            ("notification-gamma", date(2026, 1, 3)),
        )
    )
    reordered = _projection(
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
            operation_contracts=_contracts(),
        )
    )
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(80, 18)) as pilot:
        await pilot.pause()
        table = screen.query_one("#aeat-sync-rows", DataTable)
        table.focus()
        table.move_cursor(row=1)
        await pilot.pause()
        chosen = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        assert chosen == first.notifications[1].selection_key

        screen.refresh_projection(reordered)
        await pilot.pause()
        assert app.focused is table
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen
        assert table.scroll_y <= table.cursor_row < table.scroll_y + table.size.height

        await pilot.resize_terminal(100, 22)
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen
        assert table.scroll_y <= table.cursor_row < table.scroll_y + table.size.height

        child = Screen[None]()
        app.push_screen(child)
        await pilot.pause()
        child.dismiss(None)
        await pilot.pause()
        assert app.focused is table
        assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == chosen


def test_aeat_sync_status_keys_are_present_in_every_supported_locale() -> None:
    """Status/refusal copy must never fall back to a key in a shipped locale."""
    keys = (
        "tui.aeat_sync.operation.in_flight",
        "tui.aeat_sync.operation.already_handled",
        "tui.aeat_sync.notification.already_handled",
        "tui.aeat_sync.notification.document_handed_off",
        "tui.aeat_sync.refusal.notification_handoff",
        "tui.aeat_sync.refusal.unread_notification",
    )
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        for locale in ("en", "es", "ca", "hu"):
            for key in keys:
                rendered = tr(key, locale=locale)
                assert rendered != key
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)
