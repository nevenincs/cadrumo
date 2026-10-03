"""Focused public-contract tests for the host-neutral AEAT Sync TUI."""

from __future__ import annotations

import ast
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from typing import cast

import pytest
import yaml
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.entrypoints.adapter_composition import build_censal_fetch_port

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
from .....application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from .....application.live.notification_ports import NotificationsPorts
from .....application.live.notifications_read_operation import (
    NOTIFICATIONS_LIST_DEFINITION_ID,
    NotificationsListPublicResultV1,
    NotificationsSnapshotSummaryPublicV1,
    build_notifications_list_definition,
    build_notifications_list_registration,
)
from .....application.operations.models import OperationDefinitionId
from .....application.operations.registry import OperationPublicContractSetV1
from .....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogue, ActionCatalogueEntry
from .....application.operator_actions.models import ActionReference
from .....application.user_profile.censal_operation import (
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from .....core.config import override_settings
from .....core.i18n.render import I18N_STRICT_MISSING_KEYS, tr
from .....core.identity.bucket import BucketId
from .....core.operations import OperationTerminalCondition
from .....core.period import Period
from .....domain.modelos.codes import ModeloCode
from ...components.host import ScreenHostApp
from ...destination_alias import closed_destination_ids
from ...navigation import TuiScreenContextV1
from ...operations.controller_port import OperationControllerPort
from ...operations.modal import OperationModal, OperationModalSettledOutcomeV1
from ..controller import AeatSyncWorkspaceController
from ..models import (
    AeatSyncDestinationIdV1,
    AeatSyncNotificationDocumentHandoffV1,
    AeatSyncOperationHandoffV1,
    AeatSyncOperationRequestV1,
)
from ..routes import AEAT_SYNC_ROUTES, resolve_aeat_sync_screen
from ..screens import (
    AeatSyncCensusScreen,
    AeatSyncEvidenceComparisonScreen,
    AeatSyncFiledDeclarationsScreen,
    AeatSyncNotificationsScreen,
    AeatSyncOverviewScreen,
    AeatSyncReconciliationScreen,
    AeatSyncWorkspaceScreen,
)

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

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
        "address.declaration",
    }
)


class _StartedOperationController:
    """Minimal controller identity; these screen tests replace modal mounting."""

    operation_id = "a" * 64


def _started_operation_controller() -> OperationControllerPort:
    return cast(OperationControllerPort, _StartedOperationController())


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
    return {key.removeprefix(prefix): value for key, value in _flatten_locale(raw).items() if key.startswith(prefix)}


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
    census_status: AeatSyncCensusStatus = AeatSyncCensusStatus.CONFLICT,
    notification_specs: tuple[tuple[str, date], ...] | None = None,
    overview_area: AeatSyncOverviewArea | None = None,
    action_id: str | None = None,
    operation_id: OperationDefinitionId = "user-profile.censo-review",
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
    resolved_action_id = action_id or "operator.profile.edit"
    action = ActionReference(action_id=resolved_action_id)
    resolved_area = overview_area or AeatSyncOverviewArea.CENSUS
    overview = AeatSyncWorkspaceOverviewRowV1(
        area=resolved_area,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=_T1,
        aeat_observed_at=_T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        supported_actions=(action,),
        supported_operations=(operation_id,),
    )
    period = Period.from_year_and_code(2026, "1T")
    return project_aeat_sync_workspace(
        bucket_id=_BUCKET_ID,
        subject_key=_SUBJECT_KEY,
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=_contracts(resolved_action_id, operation_id),
        overview=(AeatSyncWorkspaceFactV1(_BUCKET_ID, _SUBJECT_KEY, overview),),
        census=(
            AeatSyncWorkspaceFactV1(
                _BUCKET_ID,
                _SUBJECT_KEY,
                AeatSyncWorkspaceCensusRowV1(
                    path="tax address",
                    category=AeatSyncCensusCategory.ADDRESS,
                    status=census_status,
                    # Both sides, because a CONFLICT row now has to carry the
                    # values it claims differ. Supplied for every status so the
                    # fixture stays parametrisable.
                    local_value="Calle Local 1",
                    aeat_value="Calle AEAT 2",
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


def _empty_projection(availability: AeatSyncWorkspaceAvailability) -> AeatSyncWorkspaceProjectionV1:
    """Build one valid six-zone empty/unknown source-state snapshot."""
    observed = availability in {
        AeatSyncWorkspaceAvailability.AVAILABLE,
        AeatSyncWorkspaceAvailability.STALE,
    }
    observations = tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            sources=tuple(
                AeatSyncWorkspaceSourceObservationV1(
                    source=source,
                    availability=availability,
                    observed_at=_T2 if observed else None,
                    refusal=(
                        None if availability is AeatSyncWorkspaceAvailability.AVAILABLE else "aeat.sync.source.refused"
                    ),
                    item_count=0 if observed else None,
                )
                for source in aeat_sync_workspace_sources(zone)
            ),
        )
        for zone in AeatSyncWorkspaceZone
    )
    return project_aeat_sync_workspace(
        bucket_id=_BUCKET_ID,
        subject_key=_SUBJECT_KEY,
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=_contracts(),
    )


def _contracts(
    action_id: str = "operator.profile.edit",
    operation_id: OperationDefinitionId = "user-profile.censo-review",
) -> OperationPublicContractSetV1:
    """Build a public contract whose operation/action join is explicit."""
    if action_id == "operator.live.notifications.list" and operation_id == NOTIFICATIONS_LIST_DEFINITION_ID:

        def unused_notification_ports() -> NotificationsPorts:
            raise AssertionError("public contract projection must not open notification ports")

        definition = build_notifications_list_definition(unused_notification_ports)
        return OperationPublicContractSetV1.build((build_notifications_list_registration(definition).contract,))
    definition = build_censal_operation_definition(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        censal_fetch_port=build_censal_fetch_port(),
        provider_preflight=lambda _profile_id, _operation: None,
    ).model_copy(
        update={
            "action_reference": ActionReference(action_id=action_id),
            "definition_id": operation_id,
        }
    )
    return OperationPublicContractSetV1.build((build_censal_operation_registration(definition).contract,))


def _controller(
    availability: AeatSyncWorkspaceAvailability = AeatSyncWorkspaceAvailability.AVAILABLE,
    *,
    operation_handoff: AeatSyncOperationHandoffV1 | None = None,
    notification_document_handoff: AeatSyncNotificationDocumentHandoffV1 | None = None,
    overview_area: AeatSyncOverviewArea | None = None,
    action_id: str | None = None,
    operation_id: OperationDefinitionId = "user-profile.censo-review",
) -> AeatSyncWorkspaceController:
    resolved_action_id = action_id or "operator.profile.edit"
    return AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        _projection(
            availability,
            overview_area=overview_area,
            action_id=resolved_action_id,
            operation_id=operation_id,
        ),
        operation_contracts=_contracts(resolved_action_id, operation_id),
        operation_handoff=operation_handoff,
        notification_document_handoff=notification_document_handoff,
    )


type _ScreenFactory = Callable[[AeatSyncWorkspaceController], AeatSyncWorkspaceScreen]


_SCREEN_CASES: tuple[tuple[_ScreenFactory, str, dict[str, str], tuple[str, ...]], ...] = (
    (
        AeatSyncOverviewScreen,
        "tui.aeat_sync.overview.title",
        {
            "en": "AEAT Sync overview",
            "es": "Resumen de Sincronización AEAT",
            "ca": "Resum de Sincronització AEAT",
            "hu": "Az AEAT-szinkron áttekintése",
        },
        ("overview:census",),
    ),
    (
        AeatSyncCensusScreen,
        "tui.aeat_sync.census.title",
        {
            "en": "AEAT Sync census",
            "es": "Censo de Sincronización AEAT",
            "ca": "Cens de Sincronització AEAT",
            "hu": "AEAT-szinkron: törzsadatok",
        },
        ("census:tax address",),
    ),
    (
        AeatSyncFiledDeclarationsScreen,
        "tui.aeat_sync.filed_declarations.title",
        {
            "en": "AEAT Sync filed declarations",
            "es": "Declaraciones presentadas en Sincronización AEAT",
            "ca": "Declaracions presentades a Sincronització AEAT",
            "hu": "Az AEAT-szinkron benyújtott bevallásai",
        },
        ("filed:130|2026|1T",),
    ),
    (
        AeatSyncNotificationsScreen,
        "tui.aeat_sync.notifications.title",
        {
            "en": "AEAT Sync notifications",
            "es": "Notificaciones de Sincronización AEAT",
            "ca": "Notificacions de Sincronització AEAT",
            "hu": "Az AEAT-szinkron értesítései",
        },
        (),
    ),
    (
        AeatSyncEvidenceComparisonScreen,
        "tui.aeat_sync.evidence_comparison.title",
        {
            "en": "AEAT Sync: comparison with AEAT",
            "es": "Sincronización AEAT: comparación con la AEAT",
            "ca": "Sincronització AEAT: comparació amb l'AEAT",
            "hu": "AEAT-szinkron: összehasonlítás az AEAT-tal",
        },
        ("comparison:130|2026|1T",),
    ),
    (
        AeatSyncReconciliationScreen,
        "tui.aeat_sync.reconciliation.title",
        {
            "en": "AEAT Sync reconciliation",
            "es": "Conciliación de Sincronización AEAT",
            "ca": "Conciliació de Sincronització AEAT",
            "hu": "Az AEAT-szinkron egyeztetése",
        },
        ("reconciliation:130|2026|1T",),
    ),
)

_REPRESENTATIVE_KEYS: dict[_ScreenFactory, tuple[str, ...]] = {
    AeatSyncOverviewScreen: (
        "tui.aeat_sync.area.census",
        "tui.aeat_sync.source_state.present",
        "tui.aeat_sync.discrepancy.none",
    ),
    AeatSyncCensusScreen: (
        "tui.aeat_sync.census_category.address",
        "tui.aeat_sync.census_status.conflict",
    ),
    AeatSyncFiledDeclarationsScreen: (
        "tui.aeat_sync.local_filing_state.filed",
        "tui.aeat_sync.aeat_observation_state.accepted",
        "tui.aeat_sync.justificante_state.verified",
    ),
    AeatSyncNotificationsScreen: (
        "tui.aeat_sync.notification_read_state.read",
        "tui.aeat_sync.notification_category.formal",
        "tui.aeat_sync.document_custody_state.held",
    ),
    AeatSyncEvidenceComparisonScreen: (
        "tui.aeat_sync.source_state.present",
        "tui.aeat_sync.source_state.absent",
        "tui.aeat_sync.discrepancy.local_only",
    ),
    AeatSyncReconciliationScreen: (
        "tui.aeat_sync.source_state.present",
        "tui.aeat_sync.source_state.absent",
        "tui.aeat_sync.reconciliation_state.keep_local",
    ),
}


def _table_text(table: DataTable[str]) -> str:
    """Collect actual compositor table labels and cells, not proxy DTO values."""
    labels = [str(column.label) for column in table.columns.values()]
    cells = [str(cell) for index in range(table.row_count) for cell in table.get_row_at(index)]
    return "\n".join((*labels, *cells))


def _referenced_aeat_sync_keys() -> frozenset[str]:
    """Every literal `tui.aeat_sync.*` key the shipped package asks for.

    Literals only. Keys assembled at runtime from an enum value cannot be read
    statically, so this is deliberately a SUBSET of what the surface uses and
    the locale set-equality above carries the rest.
    """
    package = Path(__file__).resolve().parent.parent
    found: set[str] = set()
    for source in package.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if not node.value.startswith("tui.aeat_sync."):
                continue
            key = node.value.removeprefix("tui.aeat_sync.")
            # A single segment is a NAMESPACE prefix that the code completes at
            # runtime from an enum value ("tui.aeat_sync.area." + area.value),
            # not a leaf anyone can look up. Only leaves are assertable here.
            if "." in key:
                found.add(key)
    return frozenset(found)


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
    english = _aeat_sync_catalogue("en")
    translated = _aeat_sync_catalogue(locale)
    assert english, "the English aeat_sync namespace is empty"
    assert set(translated) == set(english)

    referenced = _referenced_aeat_sync_keys()
    assert referenced, "no literal aeat_sync keys were found; the scan is broken"
    missing = sorted(key for key in referenced if key not in translated)
    assert not missing, f"{locale} is missing keys the code asks for: {missing}"
    if locale == "hu":
        identical = {key for key, value in translated.items() if value == english[key]}
        assert identical == _AEAT_SYNC_INTENTIONAL_IDENTICAL_HU


def test_six_routes_are_total_and_locked_projection_refuses_body() -> None:
    controller = _controller()
    assert tuple(route.zone for route in AEAT_SYNC_ROUTES) == tuple(AeatSyncWorkspaceZone)
    assert {route.destination for route in AEAT_SYNC_ROUTES} == closed_destination_ids(AeatSyncDestinationIdV1)
    assert isinstance(
        resolve_aeat_sync_screen(controller, controller.target(AeatSyncWorkspaceZone.OVERVIEW)),
        AeatSyncOverviewScreen,
    )
    locked = _controller(AeatSyncWorkspaceAvailability.LOCKED)
    assert not locked.can_open(AeatSyncWorkspaceZone.CENSUS)
    with pytest.raises(ValueError, match="not observable"):
        resolve_aeat_sync_screen(locked, locked.target(AeatSyncWorkspaceZone.CENSUS))


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
        return _started_operation_controller()

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
            assert _SUBJECT_KEY not in rendered
    assert calls == []


@pytest.mark.asyncio
async def test_explicit_overview_operation_invokes_host_once_and_missing_host_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[AeatSyncOperationRequestV1] = []

    controllers: list[OperationControllerPort] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        controller = _started_operation_controller()
        controllers.append(controller)
        return controller

    screen = AeatSyncOverviewScreen(_controller(operation_handoff=handoff))
    presented: list[OperationControllerPort] = []
    monkeypatch.setattr(screen, "_show_operation_modal", presented.append)
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.click("#aeat-sync-operation-0")
        await pilot.pause()
        # The one-shot guard is the disabled control itself; nothing can hand off twice.
        assert screen.query_one("#aeat-sync-operation-0", Button).disabled
    assert calls == [
        AeatSyncOperationRequestV1(
            action=ActionReference(action_id="operator.profile.edit"),
            operation="user-profile.censo-review",
        )
    ]
    assert presented == controllers
    refused = AeatSyncOverviewScreen(_controller())
    async with ScreenHostApp[None](refused).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Without a host door no control is offered; the refusal is stated instead.
        assert not refused.query("#aeat-sync-operation-0")
        assert tr("tui.aeat_sync.refusal.operation_handoff") in str(
            refused.query_one("#aeat-sync-status", Static).render()
        )


@pytest.mark.asyncio
async def test_started_filed_pull_handoff_pushes_the_canonical_operation_modal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_controller = _started_operation_controller()

    async def handoff(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        return started_controller

    screen = AeatSyncOverviewScreen(
        _controller(
            operation_handoff=handoff,
            overview_area=AeatSyncOverviewArea.FILED_DECLARATIONS,
            action_id="operator.live.filed.pull_all",
            operation_id="live.filed-history.pull",
        )
    )
    presented: list[tuple[OperationModal, object]] = []
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(screen.app, "push_screen", lambda modal, callback: presented.append((modal, callback)))
        await pilot.click("#aeat-sync-operation-0")
        await pilot.pause()

    assert len(presented) == 1
    assert isinstance(presented[0][0], OperationModal)
    assert presented[0][0]._controller is started_controller
    assert presented[0][1] == screen._on_operation_settled


@pytest.mark.asyncio
async def test_missing_session_contract_is_visible_refusal_and_unread_notification_never_calls_document_door() -> None:
    unknown = AeatSyncOverviewScreen(
        AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            _projection(),
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
async def test_successful_operation_refreshes_aeat_sync_off_ui_loop_and_rearms_button() -> None:
    filed_projection = _projection(
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
        operation_contracts=_contracts("operator.live.filed.pull_all", "live.filed-history.pull"),
    )
    screen = AeatSyncOverviewScreen(controller)
    succeeded = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(projection=SimpleNamespace(terminal_condition=OperationTerminalCondition.SUCCEEDED))
    )
    refused = OperationModalSettledOutcomeV1.model_construct(
        view_model=SimpleNamespace(projection=SimpleNamespace(terminal_condition=OperationTerminalCondition.REFUSED))
    )
    async with ScreenHostApp[None](screen).run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        screen._consumed_request_ids.add("aeat-sync-operation-0")
        ui_thread = get_ident()
        screen._on_operation_settled(refused)
        await pilot.pause()
        assert reads == []
        screen._on_operation_settled(succeeded)
        await pilot.pause()
        assert reads and reads[0] != ui_thread
        assert controller.projection is refreshed
        assert screen._consumed_request_ids == set()
        assert not screen.query_one("#aeat-sync-operation-1-0", Button).disabled


@pytest.mark.asyncio
async def test_successful_notification_list_projects_capture_times_and_row_counts() -> None:
    """The TUI renders only the registered public summary fields after settlement."""
    captured_at = datetime(2026, 9, 28, 12, 30, tzinfo=UTC)
    result = NotificationsListPublicResultV1(
        bucket_id=_BUCKET_ID,
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
        _controller(
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
        await pilot.pause()
        screen._on_operation_settled(settled)
        await pilot.pause()
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
    screen_type: _ScreenFactory,
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
                navigation = screen.query_one("#aeat-sync-navigation", DataTable)
                visible = "\n".join((rendered, _table_text(navigation), _table_text(table)))
                assert tr("tui.aeat_sync.column.area", locale=locale) in visible
                assert tr("tui.aeat_sync.availability.available", locale=locale) in visible
                for key in _REPRESENTATIVE_KEYS[screen_type]:
                    translated = tr(key, locale=locale)
                    assert translated != key
                    assert translated in visible
                assert "tui.aeat_sync." not in visible
                assert "AeatSync" not in visible
                for raw_token in ("filed_declarations", "evidence_comparison", "never_captured"):
                    assert raw_token not in visible
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
            "AEAT operations can't be started from this session.",
        ),
        (
            "es",
            "No se pudo iniciar la operación.",
            "Las operaciones con la AEAT no se pueden iniciar desde esta sesión.",
        ),
        (
            "ca",
            "No s'ha pogut iniciar l'operació.",
            "Les operacions amb l'AEAT no es poden iniciar des d'aquesta sessió.",
        ),
        (
            "hu",
            "A műveletet nem sikerült elindítani.",
            "AEAT-műveletek ebből a munkamenetből nem indíthatók.",
        ),
    ),
)
async def test_operation_failure_and_refusal_copy_is_localized(
    locale: str,
    failure_copy: str,
    refusal_copy: str,
) -> None:
    """Host failure and absent-door refusal are both translated operator states."""

    async def fail(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        raise RuntimeError("sentinel host failure C:\\protected\\taxpayer.txt 12345678Z")

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            failed = AeatSyncOverviewScreen(_controller(operation_handoff=fail))
            async with ScreenHostApp[None](failed).run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                await pilot.click("#aeat-sync-operation-0")
                await pilot.pause()
                rendered = str(failed.query_one("#aeat-sync-status", Static).render())
                assert failure_copy in rendered
                assert "protected" not in rendered
                assert "12345678Z" not in rendered

            refused = AeatSyncOverviewScreen(_controller())
            async with ScreenHostApp[None](refused).run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                assert not refused.query("#aeat-sync-operation-0")
                assert refusal_copy in str(refused.query_one("#aeat-sync-status", Static).render())
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("availability", tuple(AeatSyncWorkspaceAvailability))
async def test_every_zone_renders_truthful_empty_or_unobservable_source_state(
    availability: AeatSyncWorkspaceAvailability,
) -> None:
    """Known-empty and unknown source states remain visibly distinct in all zones."""
    projection = _empty_projection(availability)
    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_contracts=_contracts(),
    )
    expected_count = (
        0 if availability in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE} else None
    )
    for screen_factory, _heading, _translations, _keys in _SCREEN_CASES:
        screen = screen_factory(controller)
        async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            state = controller.state_for(screen.zone)
            assert state.item_count == expected_count
            assert screen.query_one("#aeat-sync-rows", DataTable).row_count == 0
            rendered_status = str(screen.query_one("#aeat-sync-status", Static).render())
            assert tr(f"tui.aeat_sync.availability.{availability.value}") in rendered_status
            if expected_count == 0:
                assert "0" in rendered_status
            else:
                assert tr("tui.aeat_sync.value.none") in rendered_status


@pytest.mark.asyncio
@pytest.mark.parametrize("width", (80, 100, 120))
async def test_all_routes_have_one_scroll_owner_no_horizontal_overflow_and_reachable_actions(width: int) -> None:
    """The supported widths expose every action through keyboard focus."""
    for screen_factory, _heading, _translations, _keys in _SCREEN_CASES:
        screen = screen_factory(_controller())
        async with ScreenHostApp[None](screen).run_test(size=(width, 24)) as pilot:
            await pilot.pause()
            overflowing = tuple(
                (table.id, table.max_scroll_x, table.virtual_size, table.container_size)
                for table in screen.query(DataTable)
                if table.max_scroll_x
            )
            assert not overflowing, (screen_factory, width, overflowing)
            owners = tuple(screen.query(VerticalScroll))
            assert len(owners) == 1
            assert owners[0].id == "aeat-sync-page"
            assert not any(table.show_vertical_scrollbar for table in screen.query(DataTable))
            buttons = tuple(screen.query(Button))
            for button in buttons:
                reached = False
                for _ in range(8):
                    await pilot.press("tab")
                    if screen.app.focused is button:
                        reached = True
                        break
                assert reached
            nav_text = _table_text(screen.query_one("#aeat-sync-navigation", DataTable))
            assert tr("tui.aeat_sync.availability.available") in nav_text


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
async def test_census_adoption_is_local_wording_and_no_remote_push_control(locale: str) -> None:
    """Census comparison is local review state, never an invented remote push UI."""
    with override_settings(cadrumo_output_language=locale):
        projection = _projection(census_status=AeatSyncCensusStatus.ADOPTED)
        controller = AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            projection,
            operation_contracts=_contracts(),
        )
        census = AeatSyncCensusScreen(controller)
        async with ScreenHostApp[None](census).run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            visible = _table_text(census.query_one("#aeat-sync-rows", DataTable))
            assert tr("tui.aeat_sync.census_status.adopted", locale=locale) in visible
            assert not tuple(census.query(Button))


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
async def test_filed_pull_all_uses_action_specific_copy_and_exact_one_shot_handoff(
    locale: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filed history pull comes from the overview declaration, never a filed DTO."""
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        return _started_operation_controller()

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            controller = _controller(
                operation_handoff=handoff,
                overview_area=AeatSyncOverviewArea.FILED_DECLARATIONS,
                action_id="operator.live.filed.pull_all",
                operation_id="live.filed-history.pull",
            )
            for screen in (AeatSyncOverviewScreen(controller), AeatSyncFiledDeclarationsScreen(controller)):
                monkeypatch.setattr(screen, "_show_operation_modal", lambda _controller: None)
                async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
                    await pilot.pause()
                    button = screen.query_one("#aeat-sync-operation-0", Button)
                    expected = tr("tui.aeat_sync.action.pull_filed_all", locale=locale)
                    assert expected != "tui.aeat_sync.action.pull_filed_all"
                    assert str(button.label) == expected
                    await pilot.click("#aeat-sync-operation-0")
                    await pilot.pause()
                    assert button.disabled
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)

    expected_request = AeatSyncOperationRequestV1(
        action=ActionReference(action_id="operator.live.filed.pull_all"),
        operation="live.filed-history.pull",
    )
    assert calls == [expected_request, expected_request]


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
async def test_overview_actions_use_distinct_localized_census_and_notification_copy(locale: str) -> None:
    """Census review and notification listing retain their own action copy."""

    async def handoff(_request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        return _started_operation_controller()

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=locale):
            census = AeatSyncOverviewScreen(_controller(operation_handoff=handoff))
            async with ScreenHostApp[None](census).run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                label = str(census.query_one("#aeat-sync-operation-0", Button).label)
                assert label == tr("tui.aeat_sync.action.review_census", locale=locale)
                assert label != tr("tui.aeat_sync.action.pull_filed_all", locale=locale)

            notifications = AeatSyncOverviewScreen(
                _controller(
                    operation_handoff=handoff,
                    overview_area=AeatSyncOverviewArea.NOTIFICATIONS,
                    action_id="operator.live.notifications.list",
                    operation_id=NOTIFICATIONS_LIST_DEFINITION_ID,
                )
            )
            async with ScreenHostApp[None](notifications).run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                label = str(notifications.query_one("#aeat-sync-operation-0", Button).label)
                assert label == tr("tui.search.action.list_notifications", locale=locale)
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("first_fails", (False, True))
async def test_completing_one_overview_operation_keeps_the_other_action_reachable(
    first_fails: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global in-flight guard must not become a global consumed-state guard."""
    rows = (
        AeatSyncWorkspaceOverviewRowV1(
            area=AeatSyncOverviewArea.CENSUS,
            local_state=AeatSyncSourceState.PRESENT,
            aeat_state=AeatSyncSourceState.PRESENT,
            local_observed_at=_T1,
            aeat_observed_at=_T2,
            discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
            supported_actions=(ActionReference(action_id="operator.profile.edit"),),
            supported_operations=("user-profile.censo-review",),
        ),
        AeatSyncWorkspaceOverviewRowV1(
            area=AeatSyncOverviewArea.FILED_DECLARATIONS,
            local_state=AeatSyncSourceState.PRESENT,
            aeat_state=AeatSyncSourceState.PRESENT,
            local_observed_at=_T1,
            aeat_observed_at=_T2,
            discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
            supported_actions=(ActionReference(action_id="operator.live.filed.pull_all"),),
            supported_operations=("live.filed-history.pull",),
        ),
    )
    observations = tuple(
        AeatSyncWorkspaceZoneObservationV1(
            zone=zone,
            sources=tuple(
                AeatSyncWorkspaceSourceObservationV1(
                    source=source,
                    availability=AeatSyncWorkspaceAvailability.AVAILABLE,
                    observed_at=_T2,
                    item_count=2 if zone is AeatSyncWorkspaceZone.OVERVIEW else 0,
                )
                for source in aeat_sync_workspace_sources(zone)
            ),
        )
        for zone in AeatSyncWorkspaceZone
    )
    contracts = OperationPublicContractSetV1.build(
        (*_contracts().definitions, *_contracts("operator.live.filed.pull_all", "live.filed-history.pull").definitions)
    )
    projection = project_aeat_sync_workspace(
        bucket_id=_BUCKET_ID,
        subject_key=_SUBJECT_KEY,
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=contracts,
        overview=tuple(AeatSyncWorkspaceFactV1(_BUCKET_ID, _SUBJECT_KEY, row) for row in rows),
    )
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        if first_fails and request.action.action_id == "operator.profile.edit":
            raise RuntimeError("C:\\protected\\taxpayer.txt 12345678Z")
        return _started_operation_controller()

    screen = AeatSyncOverviewScreen(
        AeatSyncWorkspaceController(
            TuiScreenContextV1(destination="workbench.aeat_sync"),
            projection,
            operation_contracts=contracts,
            operation_handoff=handoff,
        )
    )
    mounted_controllers: list[OperationControllerPort] = []
    # Each handoff returns a controller; this test isolates the in-flight and
    # one-shot controls from the modal's independent polling lifecycle.
    monkeypatch.setattr(screen, "_show_operation_modal", mounted_controllers.append)
    async with ScreenHostApp[None](screen).run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        first = screen.query_one("#aeat-sync-operation-0", Button)
        second = screen.query_one("#aeat-sync-operation-1", Button)
        # Scrolled into view before clicking, because `pilot.click` targets
        # SCREEN COORDINATES: a control below the fold is clicked at whatever
        # happens to be painted there instead, the handler never runs, and the
        # failure reads as a broken in-flight guard rather than a missed click.
        # At the 80x24 floor these operation buttons start below the fold --
        # measured at y=16 of 24 once scrolled, and off-screen before that --
        # so this is what an operator does to reach them, not a workaround.
        first.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(first)
        # A click POSTS a message; the handler that disables the button runs on
        # the next pump. Asserting straight after the click races that handler,
        # which is why this passed only when earlier tests had shifted the
        # timing and failed whenever it ran alone.
        await pilot.pause()
        assert first.disabled
        assert not second.disabled
        if first_fails:
            status = str(screen.query_one("#aeat-sync-status", Static).render())
            assert status == tr("tui.aeat_sync.operation.failed")
            assert "protected" not in status
            assert "12345678Z" not in status
        second.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(second)
        await pilot.pause()
    assert tuple(call.action.action_id for call in calls) == (
        "operator.profile.edit",
        "operator.live.filed.pull_all",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120, 200])
async def test_the_census_comparison_shows_both_values_or_neither(width: int) -> None:
    """Half a comparison is worse than none, and the verdict outranks both.

    A lone "Local value" column beside nothing to compare it against reads as a
    value AEAT does not hold, rather than a column the terminal had no room
    for. So the pair is taken whole or dropped whole.

    100 columns is the width that makes this testable, and it was added after
    the first version passed with the pair-splitting defect in place: at 80
    neither value fits and at 120 both do, so neither width can tell an atomic
    pair from a greedy one. Only a width where exactly ONE would fit
    distinguishes them.

    The status column is asserted at EVERY width because it is the verdict: an
    operator who cannot see whether a field is adopted or in conflict has lost
    the thing that tells them to act, and an earlier ordering that ranked the
    raw values above it failed exactly this way.
    """
    controller = _controller()
    screen = AeatSyncCensusScreen(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(width, 40)) as pilot:
        await pilot.pause()
        table = cast("DataTable[str]", screen.query_one("#aeat-sync-rows", DataTable))
        keys = {str(column.key.value) for column in table.columns.values()}
        app.exit(None)

    assert "status" in keys, f"the census verdict is missing at {width} columns"
    assert ("local_value" in keys) == ("aeat_value" in keys), (
        f"at {width} columns the census shows half a comparison: {sorted(keys)}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120, 200])
@pytest.mark.parametrize(
    "screen_type",
    [AeatSyncCensusScreen, AeatSyncEvidenceComparisonScreen, AeatSyncReconciliationScreen],
)
async def test_every_comparison_surface_shows_both_values_or_neither(screen_type: _ScreenFactory, width: int) -> None:
    """One rule, asserted on all three surfaces that compare two sides.

    The column fitter is shared precisely so the rule cannot drift between
    them, and this is what proves the sharing held: a screen that grew its own
    copy and split the pair fails here without touching the others.
    """
    controller = _controller()
    screen = screen_type(controller)
    app = ScreenHostApp[None](screen)
    async with app.run_test(size=(width, 40)) as pilot:
        await pilot.pause()
        table = cast("DataTable[str]", screen.query_one("#aeat-sync-rows", DataTable))
        keys = {str(column.key.value) for column in table.columns.values()}
        app.exit(None)

    assert ("local_value" in keys) == ("aeat_value" in keys), (
        f"{type(screen).__name__} at {width} columns shows half a comparison: {sorted(keys)}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 120])
async def test_complete_census_evidence_survives_reopen_and_selected_value_is_readable(width: int) -> None:
    """Operate the real evidence table after serialized workspace readback."""
    from .....application.user_profile.censal_observation import (
        CensalCell,
        CensalConsultation,
        CensalObservation,
        CensalObservationAddress,
        CensalObservationIdentity,
        CensalRow,
        CensalSection,
    )

    long_value = "Valor censal completo " * 20
    observation = CensalObservation(
        identity=CensalObservationIdentity(nif="00000001R", apellidos_y_nombre="Persona Sintética"),
        domicilio_fiscal=CensalObservationAddress(codigo_postal="28001"),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=_T2,
        source_url="https://sede.agenciatributaria.gob.es/censo",
        consultations=(
            CensalConsultation(
                kind="obligaciones",
                source_url="https://sede.agenciatributaria.gob.es/obligaciones",
                sections=(
                    CensalSection(
                        title="Mis Obligaciones",
                        rows=(
                            CensalRow(
                                label="Obligación sintética",
                                cells=(CensalCell(role="value", column="Nueva columna AEAT", text=long_value),),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    serialized = _projection().model_copy(update={"census_observation": observation}).model_dump_json()
    for _ in range(2):
        restored = AeatSyncWorkspaceProjectionV1.model_validate_json(serialized)
        screen = AeatSyncCensusScreen(
            AeatSyncWorkspaceController(
                TuiScreenContextV1(destination="workbench.aeat_sync"),
                restored,
            )
        )
        async with ScreenHostApp[None](screen).run_test(size=(width, 30)) as pilot:
            await pilot.pause()
            table = screen.query_one("#aeat-sync-census-evidence", DataTable)
            assert table.row_count > 1
            table.focus()
            table.move_cursor(row=table.row_count - 1)
            await pilot.press("enter")
            await pilot.pause()
            detail = str(screen.query_one("#aeat-sync-census-value", Static).render())
            assert long_value in detail
            assert "Nueva columna AEAT" in detail
            assert "Mis Obligaciones" in detail
            assert table.max_scroll_x == 0
            assert restored.census_observation == observation


def test_controller_pairs_the_single_operation_with_its_contract_joined_action() -> None:
    """A row's catalogue-only actions do not hide the operation its contract joins."""
    controller = _controller(
        overview_area=AeatSyncOverviewArea.FILED_DECLARATIONS,
        action_id="operator.live.filed.pull_all",
        operation_id="live.filed-history.pull",
    )
    pull = ActionReference(action_id="operator.live.filed.pull_all")
    listing = ActionReference(action_id="operator.modelo.filing_record.list")
    operation: OperationDefinitionId = "live.filed-history.pull"

    assert controller.admitted_operation((listing, pull), (operation,)) == AeatSyncOperationRequestV1(
        action=pull, operation=operation
    )
    assert controller.admitted_operation((listing,), (operation,)) is None
    assert controller.admitted_operation((listing, pull), (operation, "user-profile.censo-review")) is None


@pytest.mark.asyncio
async def test_reader_projected_filed_history_door_renders_and_hands_off_before_any_local_filing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real overview row pairs the pull with the local filing-record listing.

    A first-run profile holds no local filing, yet both the overview and the
    filed-declarations zone must offer one filed-history door, hand off its
    exact request, and state no refusal beside it.
    """
    from .....application.aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

    contracts = OperationPublicContractSetV1.build(
        (*_contracts().definitions, *_contracts("operator.live.filed.pull_all", "live.filed-history.pull").definitions)
    )
    projection = read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET_ID,
        subject_key=_SUBJECT_KEY,
        observed_at=_T2,
        filings=(),
        operation_contracts=contracts,
        censo_values={},
    )
    filed_row = next(row for row in projection.overview if row.area is AeatSyncOverviewArea.FILED_DECLARATIONS)
    assert {str(action.action_id) for action in filed_row.supported_actions} == {
        "operator.live.filed.pull_all",
        "operator.modelo.filing_record.list",
    }
    calls: list[AeatSyncOperationRequestV1] = []

    async def handoff(request: AeatSyncOperationRequestV1) -> OperationControllerPort:
        calls.append(request)
        return _started_operation_controller()

    controller = AeatSyncWorkspaceController(
        TuiScreenContextV1(destination="workbench.aeat_sync"),
        projection,
        operation_handoff=handoff,
        operation_contracts=contracts,
    )
    pull_label = tr("tui.aeat_sync.action.pull_filed_all")
    for screen in (AeatSyncOverviewScreen(controller), AeatSyncFiledDeclarationsScreen(controller)):
        monkeypatch.setattr(screen, "_show_operation_modal", lambda _controller: None)
        async with ScreenHostApp[None](screen).run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            doors = [button for button in screen.query(Button) if str(button.label) == pull_label]
            assert len(doors) == 1
            status = str(screen.query_one("#aeat-sync-status", Static).render())
            assert tr("tui.aeat_sync.refusal.operation_handoff") not in status
            doors[0].scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click(doors[0])
            await pilot.pause()
            assert doors[0].disabled

    expected = AeatSyncOperationRequestV1(
        action=ActionReference(action_id="operator.live.filed.pull_all"),
        operation="live.filed-history.pull",
    )
    assert calls == [expected, expected]
