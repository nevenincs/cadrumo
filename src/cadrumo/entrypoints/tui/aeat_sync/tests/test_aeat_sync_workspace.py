"""Focused public-contract tests for the host-neutral AEAT Sync TUI."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from datetime import UTC, date, datetime

import pytest
import yaml
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
from .....core.config import override_settings
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
from ..screens import (
    AeatSyncCensusScreen,
    AeatSyncEvidenceComparisonScreen,
    AeatSyncFiledDeclarationsScreen,
    AeatSyncNotificationsScreen,
    AeatSyncOverviewScreen,
    AeatSyncReconciliationScreen,
    AeatSyncWorkspaceScreen,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_T1 = datetime(2026, 1, 3, 10, tzinfo=UTC)
_T2 = datetime(2026, 1, 4, 11, tzinfo=UTC)
_BUCKET_ID = cast(BucketId, "11111111-1111-4111-8111-111111111111")
_SUBJECT_KEY = "private-subject"
_LOCALES_ROOT = Path(__file__).parents[4] / "locales"
_AEAT_SYNC_INTENTIONAL_IDENTICAL_HU = frozenset(
    {
        "column.aeat",
        "sources.entry",
        "sources.joined",
        "value.none",
    }
)


def _flatten_locale(node: object, prefix: str = "") -> dict[str, str]:
    """Flatten a locale tree while ignoring non-scalar structural nodes."""
    if isinstance(node, dict):
        values: dict[str, str] = {}
        for key, child in node.items():
            values.update(_flatten_locale(child, f"{prefix}.{key}" if prefix else str(key)))
        return values
    return {prefix: node} if isinstance(node, str) else {}


def _aeat_sync_catalogue(locale: str) -> dict[str, str]:
    """Load the exact shared-file AEAT Sync namespace for one locale."""
    raw = yaml.safe_load((_LOCALES_ROOT / locale / "common.yml").read_text(encoding="utf-8"))
    prefix = "tui.aeat_sync."
    return {
        key.removeprefix(prefix): value
        for key, value in _flatten_locale(raw).items()
        if key.startswith(prefix)
    }


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


_SCREEN_CASES: tuple[tuple[type[AeatSyncWorkspaceScreen], str, dict[str, str], tuple[str, ...]], ...] = (
    (
        AeatSyncOverviewScreen,
        "tui.aeat_sync.overview.title",
        {
            "en": "AEAT Sync overview",
            "es": "Resumen de sincronización AEAT",
            "ca": "Resum de sincronització de l'AEAT",
            "hu": "Az AEAT-szinkron áttekintése",
        },
        ("overview:census",),
    ),
    (
        AeatSyncCensusScreen,
        "tui.aeat_sync.census.title",
        {
            "en": "AEAT Sync census",
            "es": "Censo de sincronización AEAT",
            "ca": "Cens de sincronització de l'AEAT",
            "hu": "AEAT-szinkronizálási nyilvántartás",
        },
        ("census:tax address",),
    ),
    (
        AeatSyncFiledDeclarationsScreen,
        "tui.aeat_sync.filed_declarations.title",
        {
            "en": "AEAT Sync filed declarations",
            "es": "Declaraciones presentadas en sincronización AEAT",
            "ca": "Declaracions presentades a l'AEAT",
            "hu": "Az AEAT-szinkron benyújtott bevallásai",
        },
        ("filed:130|2026|1T",),
    ),
    (
        AeatSyncNotificationsScreen,
        "tui.aeat_sync.notifications.title",
        {
            "en": "AEAT Sync notifications",
            "es": "Notificaciones de sincronización AEAT",
            "ca": "Notificacions de l'AEAT",
            "hu": "Az AEAT-szinkron értesítései",
        },
        (),
    ),
    (
        AeatSyncEvidenceComparisonScreen,
        "tui.aeat_sync.evidence_comparison.title",
        {
            "en": "AEAT Sync evidence comparison",
            "es": "Comparación de evidencias de sincronización AEAT",
            "ca": "Comparació d'evidències de l'AEAT",
            "hu": "Az AEAT-szinkron bizonyítékainak összehasonlítása",
        },
        ("comparison:130|2026|1T",),
    ),
    (
        AeatSyncReconciliationScreen,
        "tui.aeat_sync.reconciliation.title",
        {
            "en": "AEAT Sync reconciliation",
            "es": "Conciliación de sincronización AEAT",
            "ca": "Conciliació de l'AEAT",
            "hu": "Az AEAT-szinkron egyeztetése",
        },
        ("reconciliation:130|2026|1T",),
    ),
)


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_aeat_sync_namespace_matches_all_locales_and_hu_has_only_explicit_invariants(locale: str) -> None:
    """Keep the complete 111-key surface translated, with a tiny HU allowlist."""
    english = _aeat_sync_catalogue("en")
    translated = _aeat_sync_catalogue(locale)
    assert len(english) == 111
    assert set(translated) == set(english)
    if locale == "hu":
        identical = {key for key, value in translated.items() if value == english[key]}
        assert identical == _AEAT_SYNC_INTENTIONAL_IDENTICAL_HU


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


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
@pytest.mark.parametrize("screen_type, heading_key, headings, expected_keys", _SCREEN_CASES)
async def test_every_aeat_sync_screen_is_localized_and_keeps_route_and_row_identities(
    locale: str,
    screen_type: type[AeatSyncWorkspaceScreen],
    heading_key: str,
    headings: dict[str, str],
    expected_keys: tuple[str, ...],
) -> None:
    """Mount all six routes in all four locales without identity drift."""
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            screen = screen_type(_controller())
            async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                rendered = "\n".join(str(widget.render()) for widget in screen.query(Static))
                assert headings[locale] in rendered
                assert headings[locale] == tr(heading_key, locale=locale)
                if locale != "en":
                    assert headings[locale] != headings["en"]
                table = screen.query_one("#aeat-sync-rows", DataTable)
                keys = tuple(str(item.key.value) for item in table.ordered_rows)
                if screen_type is AeatSyncNotificationsScreen:
                    assert keys == (str(screen.controller.projection.notifications[0].selection_key),)
                else:
                    assert keys == expected_keys
                assert screen.id == f"aeat-sync-{screen.zone.value.replace('_', '-')}-screen"
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("locale", "failure_copy", "refusal_copy"),
    (
        (
            "en",
            "Operation could not be started.",
            "Operation handoff is unavailable.",
        ),
        (
            "es",
            "No se pudo iniciar la operación.",
            "La entrega de la operación no está disponible.",
        ),
        (
            "ca",
            "No s'ha pogut iniciar l'operació.",
            "El lliurament de l'operació no està disponible.",
        ),
        (
            "hu",
            "A műveletet nem sikerült elindítani.",
            "A művelet átadása nem érhető el.",
        ),
    ),
)
async def test_operation_failure_and_refusal_copy_is_localized(
    locale: str,
    failure_copy: str,
    refusal_copy: str,
) -> None:
    """Host failure and absent-door refusal are both translated operator states."""

    async def fail(_request: AeatSyncOperationRequestV1) -> None:
        raise RuntimeError("sentinel host failure")

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            failed = AeatSyncOverviewScreen(_controller(operation_handoff=fail))
            async with ScreenHostApp[None](failed).run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.click("#aeat-sync-operation-0")
                await pilot.pause()
                assert failure_copy in str(failed.query_one("#aeat-sync-status", Static).render())

            refused = AeatSyncOverviewScreen(_controller())
            async with ScreenHostApp[None](refused).run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.click("#aeat-sync-operation-0")
                assert refusal_copy in str(refused.query_one("#aeat-sync-status", Static).render())
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)
