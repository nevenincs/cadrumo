"""Registered exact-profile reads for encrypted notification snapshots."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, NonNegativeInt, StringConstraints, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.aeat_certificado import AeatCertificadoId
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import SnapshotId
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..operator_actions.models import ActionReference
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .notification_ports import NotificationsPorts, NotificationTypeValue
from .notifications import NotificationsService, PersistedNotificationsSnapshot

NOTIFICATIONS_LIST_DEFINITION_ID = "live.notifications.list"
NOTIFICATIONS_SHOW_DEFINITION_ID = "live.notifications.show"
NOTIFICATIONS_LATEST_DEFINITION_ID = "live.notifications.latest"
_LIST_PHASES = ("notifications-list.read", "notifications-list.result")
_SHOW_PHASES = ("notifications-show.read", "notifications-show.result")
_LATEST_PHASES = ("notifications-latest.read", "notifications-latest.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
_SnapshotIdPrefix = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[0-9a-f]+$"),
]


class NotificationsListRequest(CredentialFreeOperationRequest):
    """List persisted notification snapshot summaries for one profile."""

    profile_id: UUID


class NotificationsShowRequest(CredentialFreeOperationRequest):
    """Show one persisted notification snapshot by full id or hex prefix."""

    profile_id: UUID
    snapshot_id: _SnapshotIdPrefix


class NotificationsLatestRequest(CredentialFreeOperationRequest):
    """Resolve the newest persisted notification snapshot for one profile."""

    profile_id: UUID


class NotificationsSnapshotSummary(BaseModel):
    """Private summary kept in the operation's encrypted result operand."""

    model_config = _PUBLIC_CONFIG
    snapshot_id: SnapshotId
    captured_at: datetime
    row_count: NonNegativeInt
    source_url: str


class NotificationsListOperationReport(BaseModel):
    """Private complete list report, bound to its source bucket."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    count: NonNegativeInt
    rows: tuple[NotificationsSnapshotSummary, ...]

    @model_validator(mode="after")
    def _count_matches_rows(self) -> NotificationsListOperationReport:
        if self.count != len(self.rows):
            raise ValueError("notification snapshot count does not match its summaries")
        return self


class NotificationsShowOperationReport(BaseModel):
    """Private selected snapshot retained only in encrypted operation custody."""

    model_config = _PUBLIC_CONFIG
    snapshot: PersistedNotificationsSnapshot


class NotificationsLatestOperationReport(BaseModel):
    """Private newest-snapshot summary, or an explicit empty result."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot: NotificationsSnapshotSummary | None


class NotificationRowPublicV1(BaseModel):
    """Closed public projection of every existing notification row field."""

    model_config = _PUBLIC_CONFIG
    certificado_id: AeatCertificadoId
    tipo: NotificationTypeValue
    concepto: str
    titular_nif: str
    titular_nombre: str
    destinatario_nif: str
    destinatario_nombre: str
    fecha_emision: date
    fecha_notificacion: date | None
    modo_notificacion: str | None
    leida: bool | None
    source_url: str
    mode: Literal["read"]


class NotificationsSnapshotSummaryPublicV1(BaseModel):
    """Safe list row without notification details or source URL."""

    model_config = _PUBLIC_CONFIG
    snapshot_id: SnapshotId
    captured_at: datetime
    row_count: NonNegativeInt


class NotificationsListPublicResultV1(BaseModel):
    """Safe snapshot inventory for the exact active profile."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    count: NonNegativeInt
    rows: tuple[NotificationsSnapshotSummaryPublicV1, ...]

    @model_validator(mode="after")
    def _count_matches_rows(self) -> NotificationsListPublicResultV1:
        if self.count != len(self.rows):
            raise ValueError("public notification snapshot count does not match its summaries")
        return self


class NotificationsShowPublicResultV1(BaseModel):
    """Complete public view of a selected encrypted notification snapshot."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    source_url: str
    row_count: NonNegativeInt
    rows: tuple[NotificationRowPublicV1, ...]

    @model_validator(mode="after")
    def _row_count_matches(self) -> NotificationsShowPublicResultV1:
        if self.row_count != len(self.rows):
            raise ValueError("public notification row count does not match its rows")
        return self


class NotificationsLatestPublicResultV1(BaseModel):
    """Safe latest-snapshot summary, with a stable empty representation."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: datetime | None = None
    source_url: str | None = None
    row_count: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _optional_snapshot_fields_agree(self) -> NotificationsLatestPublicResultV1:
        fields_present = (
            self.captured_at is not None,
            self.source_url is not None,
            self.row_count is not None,
        )
        if self.snapshot_id is None and any(fields_present):
            raise ValueError("empty latest notification result cannot carry snapshot fields")
        if self.snapshot_id is not None and not all(fields_present):
            raise ValueError("latest notification result requires every snapshot summary field")
        return self


NotificationsPortsFactory = Callable[[], NotificationsPorts]


def _require_exact_profile(profile_id: UUID, subject_ref: str) -> str:
    """Refuse a request outside the exact profile worker currently active."""
    canonical_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != canonical_id or subject_ref != profile_operation_subject(canonical_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return canonical_id


def _require_snapshot_bucket(snapshot: PersistedNotificationsSnapshot, bucket_id: str) -> None:
    """Fail closed if a persisted row is inconsistent with its exact query bucket."""
    if str(snapshot.bucket_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _summary(snapshot: PersistedNotificationsSnapshot) -> NotificationsSnapshotSummary:
    return NotificationsSnapshotSummary(
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.captured_at,
        row_count=len(snapshot.rows),
        source_url=snapshot.source_url,
    )


class NotificationsListExecutor:
    """Read local snapshot summaries without opening browser or process resources."""

    def __init__(self, ports_factory: NotificationsPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[NotificationsListRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_exact_profile(payload.profile_id, request.subject_ref)
        if (
            request.definition_id != NOTIFICATIONS_LIST_DEFINITION_ID
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_LIST_PHASES[0])

        def read() -> NotificationsListOperationReport:
            snapshots = NotificationsService(ports=self._ports_factory()).list_snapshots(bucket_id=bucket_id)
            for snapshot in snapshots:
                _require_snapshot_bucket(snapshot, bucket_id)
            return NotificationsListOperationReport(
                bucket_id=bucket_id,
                count=len(snapshots),
                rows=tuple(_summary(snapshot) for snapshot in snapshots),
            )

        report = await asyncio.to_thread(read)
        await context.events.phase(_LIST_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="notifications-list-result"
        )


class NotificationsShowExecutor:
    """Read one selected snapshot and keep identity metadata private."""

    def __init__(self, ports_factory: NotificationsPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[NotificationsShowRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_exact_profile(payload.profile_id, request.subject_ref)
        if (
            request.definition_id != NOTIFICATIONS_SHOW_DEFINITION_ID
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_SHOW_PHASES[0])

        def read() -> NotificationsShowOperationReport:
            snapshot = NotificationsService(ports=self._ports_factory()).show(
                bucket_id=bucket_id, snapshot_id=payload.snapshot_id
            )
            _require_snapshot_bucket(snapshot, bucket_id)
            return NotificationsShowOperationReport(snapshot=snapshot)

        report = await asyncio.to_thread(read)
        await context.events.phase(_SHOW_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="notifications-show-result"
        )


class NotificationsLatestExecutor:
    """Read only the latest snapshot summary from local encrypted custody."""

    def __init__(self, ports_factory: NotificationsPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[NotificationsLatestRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        bucket_id = _require_exact_profile(payload.profile_id, request.subject_ref)
        if (
            request.definition_id != NOTIFICATIONS_LATEST_DEFINITION_ID
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(_LATEST_PHASES[0])

        def read() -> NotificationsLatestOperationReport:
            snapshot = NotificationsService(ports=self._ports_factory()).latest(bucket_id=bucket_id)
            if snapshot is None:
                return NotificationsLatestOperationReport(bucket_id=bucket_id, snapshot=None)
            _require_snapshot_bucket(snapshot, bucket_id)
            return NotificationsLatestOperationReport(bucket_id=bucket_id, snapshot=_summary(snapshot))

        report = await asyncio.to_thread(read)
        await context.events.phase(_LATEST_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="notifications-latest-result"
        )


def _capabilities() -> OperationCapabilities:
    """Describe a durable local read with no provider or owned resource."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
        sensitive_input=OperationSensitiveInputPolicy.NONE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def build_notifications_list_definition(ports_factory: NotificationsPortsFactory) -> OperationDefinition:
    """Declare an exact-profile local notifications snapshot inventory."""
    return OperationDefinition(
        definition_id=NOTIFICATIONS_LIST_DEFINITION_ID,
        request_type=NotificationsListRequest,
        result_type=NotificationsListOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=NotificationsListRequest,
            executor_type=NotificationsListExecutor,
            build=lambda: NotificationsListExecutor(ports_factory),
        ),
        phase_codes=_LIST_PHASES,
        interaction_kinds=frozenset(),
        action_reference=ActionReference(
            action_id=OPERATOR_ACTION_CATALOGUE.lookup("operator.live.notifications.list").action_id
        ),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_notifications_show_definition(ports_factory: NotificationsPortsFactory) -> OperationDefinition:
    """Declare an exact-profile local notifications snapshot detail view."""
    return OperationDefinition(
        definition_id=NOTIFICATIONS_SHOW_DEFINITION_ID,
        request_type=NotificationsShowRequest,
        result_type=NotificationsShowOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=NotificationsShowRequest,
            executor_type=NotificationsShowExecutor,
            build=lambda: NotificationsShowExecutor(ports_factory),
        ),
        phase_codes=_SHOW_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_notifications_latest_definition(ports_factory: NotificationsPortsFactory) -> OperationDefinition:
    """Declare an exact-profile local latest-snapshot lookup."""
    return OperationDefinition(
        definition_id=NOTIFICATIONS_LATEST_DEFINITION_ID,
        request_type=NotificationsLatestRequest,
        result_type=NotificationsLatestOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=NotificationsLatestRequest,
            executor_type=NotificationsLatestExecutor,
            build=lambda: NotificationsLatestExecutor(ports_factory),
        ),
        phase_codes=_LATEST_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def _project_list(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = NotificationsListOperationReport.model_validate(result, strict=True)
    _validate_receipt(receipt, definition_id=NOTIFICATIONS_LIST_DEFINITION_ID, profile_id=UUID(report.bucket_id))
    return NotificationsListPublicResultV1(
        bucket_id=report.bucket_id,
        count=report.count,
        rows=tuple(
            NotificationsSnapshotSummaryPublicV1(
                snapshot_id=row.snapshot_id,
                captured_at=row.captured_at,
                row_count=row.row_count,
            )
            for row in report.rows
        ),
    )


def _project_show(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = NotificationsShowOperationReport.model_validate(result, strict=True)
    snapshot = report.snapshot
    _validate_receipt(receipt, definition_id=NOTIFICATIONS_SHOW_DEFINITION_ID, profile_id=UUID(snapshot.bucket_id))
    return NotificationsShowPublicResultV1(
        bucket_id=snapshot.bucket_id,
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.captured_at,
        source_url=snapshot.source_url,
        row_count=len(snapshot.rows),
        rows=tuple(
            NotificationRowPublicV1(
                certificado_id=row.certificado_id,
                tipo=row.tipo,
                concepto=row.concepto,
                titular_nif=row.titular_nif,
                titular_nombre=row.titular_nombre,
                destinatario_nif=row.destinatario_nif,
                destinatario_nombre=row.destinatario_nombre,
                fecha_emision=row.fecha_emision,
                fecha_notificacion=row.fecha_notificacion,
                modo_notificacion=row.modo_notificacion,
                leida=row.leida,
                source_url=row.source_url,
                mode=row.mode,
            )
            for row in snapshot.rows
        ),
    )


def _project_latest(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = NotificationsLatestOperationReport.model_validate(result, strict=True)
    _validate_receipt(receipt, definition_id=NOTIFICATIONS_LATEST_DEFINITION_ID, profile_id=UUID(report.bucket_id))
    snapshot = report.snapshot
    return NotificationsLatestPublicResultV1(
        bucket_id=report.bucket_id,
        snapshot_id=snapshot.snapshot_id if snapshot is not None else None,
        captured_at=snapshot.captured_at if snapshot is not None else None,
        source_url=snapshot.source_url if snapshot is not None else None,
        row_count=snapshot.row_count if snapshot is not None else None,
    )


def _validate_receipt(receipt: OperationTerminalReceipt, *, definition_id: str, profile_id: UUID) -> None:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("notification read result contradicts its terminal receipt")


def _resolve_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, definition_id: str
) -> ResolvedOperationAccess:
    expected_type: type[BaseModel]
    if definition_id == NOTIFICATIONS_LIST_DEFINITION_ID:
        expected_type = NotificationsListRequest
    elif definition_id == NOTIFICATIONS_SHOW_DEFINITION_ID:
        expected_type = NotificationsShowRequest
    elif definition_id == NOTIFICATIONS_LATEST_DEFINITION_ID:
        expected_type = NotificationsLatestRequest
    else:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != definition_id or not isinstance(request.payload, expected_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def resolve_notifications_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile whole-profile disclosure for list summaries."""
    return _resolve_read_access(request, context, NOTIFICATIONS_LIST_DEFINITION_ID)


def resolve_notifications_show_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile whole-profile access to full notification rows."""
    return _resolve_read_access(request, context, NOTIFICATIONS_SHOW_DEFINITION_ID)


def resolve_notifications_latest_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile whole-profile disclosure for latest snapshot facts."""
    return _resolve_read_access(request, context, NOTIFICATIONS_LATEST_DEFINITION_ID)


def build_notifications_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind list request and safe summary schemas to whole-profile access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=NotificationsListRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=NotificationsListPublicResultV1,
        ),
        result_projector=_project_list,
        access_resolver=resolve_notifications_list_access,
    )


def build_notifications_show_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind full-row detail to an exact-profile disclosure decision."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=NotificationsShowRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=NotificationsShowPublicResultV1,
        ),
        result_projector=_project_show,
        access_resolver=resolve_notifications_show_access,
    )


def build_notifications_latest_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind latest summary and explicit empty state to whole-profile access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=NotificationsLatestRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=NotificationsLatestPublicResultV1,
        ),
        result_projector=_project_latest,
        access_resolver=resolve_notifications_latest_access,
    )


__all__ = [
    "NOTIFICATIONS_LATEST_DEFINITION_ID",
    "NOTIFICATIONS_LIST_DEFINITION_ID",
    "NOTIFICATIONS_SHOW_DEFINITION_ID",
    "NotificationRowPublicV1",
    "NotificationsLatestPublicResultV1",
    "NotificationsLatestRequest",
    "NotificationsListPublicResultV1",
    "NotificationsListRequest",
    "NotificationsPortsFactory",
    "NotificationsShowPublicResultV1",
    "NotificationsShowRequest",
    "build_notifications_latest_definition",
    "build_notifications_latest_registration",
    "build_notifications_list_definition",
    "build_notifications_list_registration",
    "build_notifications_show_definition",
    "build_notifications_show_registration",
    "resolve_notifications_latest_access",
    "resolve_notifications_list_access",
    "resolve_notifications_show_access",
]
