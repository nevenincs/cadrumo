"""Projection, controller and locale fixtures shared by the AEAT Sync workspace tests."""

from __future__ import annotations

import ast
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import yaml
from textual.widgets import DataTable

from .....adapters.outbound.aeat.browser.factory import default_browser_session_factory
from .....adapters.persistence.storage.operator_scope import build_operator_scope_ports
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
    build_notifications_list_definition,
    build_notifications_list_registration,
)
from .....application.operations.models import OperationDefinitionId
from .....application.operations.registry import OperationPublicContractSetV1
from .....application.operator_actions.catalogue import (
    OPERATOR_ACTION_CATALOGUE,
)
from .....application.operator_actions.models import ActionReference
from .....application.user_profile.censal_operation import (
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from .....core.identity.bucket import BucketId
from .....core.period import Period
from .....domain.modelos.codes import ModeloCode
from ....adapter_composition_ports import build_censal_fetch_port
from ...navigation import TuiScreenContextV1
from ...operations.controller_port import OperationControllerPort
from ..census_screen import AeatSyncCensusScreen
from ..controller import AeatSyncWorkspaceController
from ..evidence_comparison_screen import AeatSyncEvidenceComparisonScreen
from ..filed_declarations_screen import AeatSyncFiledDeclarationsScreen
from ..models import (
    AeatSyncNotificationDocumentHandoffV1,
    AeatSyncOperationHandoffV1,
)
from ..notifications_screen import AeatSyncNotificationsScreen
from ..overview_screen import AeatSyncOverviewScreen
from ..reconciliation_screen import AeatSyncReconciliationScreen
from ..screens import AeatSyncWorkspaceScreen

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()
T1 = datetime(2026, 1, 3, 10, tzinfo=UTC)
T2 = datetime(2026, 1, 4, 11, tzinfo=UTC)
BUCKET_ID = cast(BucketId, "11111111-1111-4111-8111-111111111111")
SUBJECT_KEY = "private-subject"
_LOCALES_ROOT = Path(__file__).parents[4] / "locales"
AEAT_SYNC_INTENTIONAL_IDENTICAL_HU = frozenset(
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


def started_operation_controller() -> OperationControllerPort:
    return cast(OperationControllerPort, _StartedOperationController())


def _flatten_locale(node: object, prefix: str = "") -> dict[str, str]:
    """Flatten a locale tree while ignoring non-scalar structural nodes."""
    if isinstance(node, dict):
        values: dict[str, str] = {}
        for key, child in node.items():
            values.update(_flatten_locale(child, f"{prefix}.{key}" if prefix else str(key)))
        return values
    return {prefix: node} if isinstance(node, str) else {}


def aeat_sync_catalogue(locale: str) -> dict[str, str]:
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
        observed_at=T2 if visible else None,
        refusal=None if availability is AeatSyncWorkspaceAvailability.AVAILABLE else "aeat.sync.source.refused",
        item_count=1 if visible else None,
    )


def aeat_sync_workspace_projection(
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
            bucket_id=BUCKET_ID,
            subject_key=SUBJECT_KEY,
            zone_observations=observations,
            action_catalogue=OPERATOR_ACTION_CATALOGUE,
            operation_contracts=aeat_sync_workspace_contracts(),
        )
    resolved_action_id = action_id or "operator.profile.edit"
    action = ActionReference(action_id=resolved_action_id)
    resolved_area = overview_area or AeatSyncOverviewArea.CENSUS
    overview = AeatSyncWorkspaceOverviewRowV1(
        area=resolved_area,
        local_state=AeatSyncSourceState.PRESENT,
        aeat_state=AeatSyncSourceState.PRESENT,
        local_observed_at=T1,
        aeat_observed_at=T2,
        discrepancy_kind=AeatSyncDiscrepancyKind.NONE,
        supported_actions=(action,),
        supported_operations=(operation_id,),
    )
    period = Period.from_year_and_code(2026, "1T")
    return project_aeat_sync_workspace(
        bucket_id=BUCKET_ID,
        subject_key=SUBJECT_KEY,
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=aeat_sync_workspace_contracts(resolved_action_id, operation_id),
        overview=(AeatSyncWorkspaceFactV1(BUCKET_ID, SUBJECT_KEY, overview),),
        census=(
            AeatSyncWorkspaceFactV1(
                BUCKET_ID,
                SUBJECT_KEY,
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
                BUCKET_ID,
                SUBJECT_KEY,
                AeatSyncWorkspaceFiledDeclarationRowV1(
                    modelo=ModeloCode("130"),
                    filing_year=2026,
                    period=period,
                    local_filing_state=AeatSyncLocalFilingState.FILED,
                    local_filed_at=T1,
                    aeat_observation_state=AeatSyncAeatObservationState.ACCEPTED,
                    aeat_observed_at=T2,
                    justificante_state=AeatSyncJustificanteState.VERIFIED,
                    justificante_observed_at=T2,
                ),
            ),
        ),
        notifications=tuple(
            AeatSyncWorkspaceFactV1(
                BUCKET_ID,
                SUBJECT_KEY,
                AeatSyncWorkspaceNotificationRowV1(
                    issued_on=issued_on,
                    read_on=None if unread else issued_on,
                    read_state=AeatSyncNotificationReadState.UNREAD if unread else AeatSyncNotificationReadState.READ,
                    category=AeatSyncNotificationCategory.FORMAL,
                    document_custody_state=(
                        AeatSyncDocumentCustodyState.NOT_CAPTURED if unread else AeatSyncDocumentCustodyState.HELD
                    ),
                    document_custody_observed_at=None if unread else T2,
                ),
                private_identity=private_identity,
            )
            for private_identity, issued_on in (notification_specs or (("notification-private", date(2026, 1, 2)),))
        ),
        evidence_comparison=(
            AeatSyncWorkspaceFactV1(
                BUCKET_ID,
                SUBJECT_KEY,
                AeatSyncWorkspaceEvidenceComparisonRowV1(
                    modelo=ModeloCode("130"),
                    filing_year=2026,
                    period=period,
                    local_state=AeatSyncSourceState.PRESENT,
                    aeat_state=AeatSyncSourceState.ABSENT,
                    local_observed_at=T1,
                    aeat_observed_at=T2,
                    discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
                ),
            ),
        ),
        reconciliation=(
            AeatSyncWorkspaceFactV1(
                BUCKET_ID,
                SUBJECT_KEY,
                AeatSyncWorkspaceReconciliationRowV1(
                    modelo=ModeloCode("130"),
                    filing_year=2026,
                    period=period,
                    local_state=AeatSyncSourceState.PRESENT,
                    aeat_state=AeatSyncSourceState.ABSENT,
                    local_observed_at=T1,
                    aeat_observed_at=T2,
                    discrepancy_kind=AeatSyncDiscrepancyKind.LOCAL_ONLY,
                    reconciliation_state=AeatSyncReconciliationState.KEEP_LOCAL,
                ),
            ),
        ),
    )


def empty_projection(availability: AeatSyncWorkspaceAvailability) -> AeatSyncWorkspaceProjectionV1:
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
                    observed_at=T2 if observed else None,
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
        bucket_id=BUCKET_ID,
        subject_key=SUBJECT_KEY,
        zone_observations=observations,
        action_catalogue=OPERATOR_ACTION_CATALOGUE,
        operation_contracts=aeat_sync_workspace_contracts(),
    )


def aeat_sync_workspace_contracts(
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


def aeat_sync_workspace_controller(
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
        aeat_sync_workspace_projection(
            availability,
            overview_area=overview_area,
            action_id=resolved_action_id,
            operation_id=operation_id,
        ),
        operation_contracts=aeat_sync_workspace_contracts(resolved_action_id, operation_id),
        operation_handoff=operation_handoff,
        notification_document_handoff=notification_document_handoff,
    )


type ScreenFactory = Callable[[AeatSyncWorkspaceController], AeatSyncWorkspaceScreen]


SCREEN_CASES: tuple[tuple[ScreenFactory, str, dict[str, str], tuple[str, ...]], ...] = (
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

REPRESENTATIVE_KEYS: dict[ScreenFactory, tuple[str, ...]] = {
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


def table_text(table: DataTable[str]) -> str:
    """Collect actual compositor table labels and cells, not proxy DTO values."""
    labels = [str(column.label) for column in table.columns.values()]
    cells = [str(cell) for index in range(table.row_count) for cell in table.get_row_at(index)]
    return "\n".join((*labels, *cells))


def referenced_aeat_sync_keys() -> frozenset[str]:
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
