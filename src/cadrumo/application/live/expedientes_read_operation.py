"""Registered exact-profile reads of encrypted expediente snapshots."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, NonNegativeInt, StringConstraints, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.aeat_expediente import AeatExpedienteId
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
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .expedientes import ExpedientesService, PersistedExpedientesSnapshot
from .expedientes_ports import ExpedientesPortsFactory

EXPEDIENTES_LIST_DEFINITION_ID = "live.expedientes.list"
EXPEDIENTES_SHOW_DEFINITION_ID = "live.expedientes.show"
EXPEDIENTES_LATEST_DEFINITION_ID = "live.expedientes.latest"
_LIST_PHASES = ("expedientes-list.read", "expedientes-list.result")
_SHOW_PHASES = ("expedientes-show.read", "expedientes-show.result")
_LATEST_PHASES = ("expedientes-latest.read", "expedientes-latest.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
_SnapshotIdPrefix = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[0-9a-f]+$")
]


class ExpedientesListRequest(CredentialFreeOperationRequest):
    """List snapshot summaries from one immutable profile worker."""

    profile_id: UUID


class ExpedientesShowRequest(CredentialFreeOperationRequest):
    """Resolve one snapshot by its full digest or unambiguous prefix."""

    profile_id: UUID
    snapshot_id: _SnapshotIdPrefix


class ExpedientesLatestRequest(CredentialFreeOperationRequest):
    """Read the newest persisted snapshot without contacting AEAT."""

    profile_id: UUID


class ExpedientesSnapshotSummaryPublicV1(BaseModel):
    """Allowlisted snapshot facts already present in the CLI result."""

    model_config = _PUBLIC_CONFIG
    snapshot_id: SnapshotId
    captured_at: datetime
    source_url: str
    declaration_count: NonNegativeInt


class ExpedientesListOperationReport(BaseModel):
    """Private encrypted list operand scoped to one bucket."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    rows: tuple[ExpedientesSnapshotSummaryPublicV1, ...]


class ExpedientesShowOperationReport(BaseModel):
    """Keep the full persisted snapshot in encrypted operation custody."""

    model_config = _PUBLIC_CONFIG
    snapshot: PersistedExpedientesSnapshot


class ExpedientesLatestOperationReport(BaseModel):
    """Private latest summary, including an explicit empty state."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot: ExpedientesSnapshotSummaryPublicV1 | None


class ExpedientesListPublicResultV1(BaseModel):
    """Closed snapshot inventory for an authorized whole-profile read."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    count: NonNegativeInt
    rows: tuple[ExpedientesSnapshotSummaryPublicV1, ...]

    @model_validator(mode="after")
    def _count_matches_rows(self) -> ExpedientesListPublicResultV1:
        if self.count != len(self.rows):
            raise ValueError("expedientes count disagrees with its snapshot rows")
        return self


class ExpedienteDeclarationPublicV1(BaseModel):
    """Explicit declaration projection without the internal Period codec."""

    model_config = _PUBLIC_CONFIG
    modelo: str
    ejercicio: int
    period: str
    expediente_id: AeatExpedienteId
    estado: str
    tipo_solicitud: str | None
    observaciones: str | None
    presented_at: datetime
    justificante_link_text: str | None
    archive_link_text: str | None
    declaration_copy_link_text: str | None
    justificante_cell_index: int
    archive_cell_index: int | None
    declaration_copy_cell_index: int | None
    mode: Literal["read"]


class ExpedientesShowPublicResultV1(BaseModel):
    """Existing CLI view fields with every declaration field allowlisted."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    source_url: str
    declaration_count: NonNegativeInt
    declarations: tuple[ExpedienteDeclarationPublicV1, ...]

    @model_validator(mode="after")
    def _count_matches_declarations(self) -> ExpedientesShowPublicResultV1:
        if self.declaration_count != len(self.declarations):
            raise ValueError("expedientes count disagrees with its declarations")
        return self


class ExpedientesLatestPublicResultV1(BaseModel):
    """Newest snapshot summary or a coherent empty result."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: datetime | None
    source_url: str | None
    declaration_count: NonNegativeInt | None

    @model_validator(mode="after")
    def _optional_fields_agree(self) -> ExpedientesLatestPublicResultV1:
        present = (self.captured_at is not None, self.source_url is not None, self.declaration_count is not None)
        if self.snapshot_id is None and any(present):
            raise ValueError("empty latest expedientes result carries snapshot fields")
        if self.snapshot_id is not None and not all(present):
            raise ValueError("latest expedientes result lacks snapshot fields")
        return self


def _exact_bucket(profile_id: UUID, subject_ref: str) -> str:
    bucket_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != bucket_id or subject_ref != profile_operation_subject(bucket_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def _check_identity[Payload: BaseModel](
    request: OperationRequest[Payload], context: OperationExecutorContext, definition_id: str
) -> None:
    if (
        request.definition_id != definition_id
        or context.identity.definition_id != definition_id
        or context.identity.subject_ref != request.subject_ref
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _summary(snapshot: PersistedExpedientesSnapshot) -> ExpedientesSnapshotSummaryPublicV1:
    return ExpedientesSnapshotSummaryPublicV1(
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.captured_at,
        source_url=snapshot.source_url,
        declaration_count=len(snapshot.declarations),
    )


def _require_bucket(snapshot: PersistedExpedientesSnapshot, bucket_id: str) -> None:
    if str(snapshot.bucket_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


class ExpedientesListExecutor:
    """Read local summaries without browser or provider resources."""

    def __init__(self, ports_factory: ExpedientesPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[ExpedientesListRequest], context: OperationExecutorContext
    ) -> str:
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
        _check_identity(request, context, EXPEDIENTES_LIST_DEFINITION_ID)
        await context.events.phase(_LIST_PHASES[0])

        def read() -> ExpedientesListOperationReport:
            snapshots = ExpedientesService(ports=self._ports_factory(bucket_id=bucket_id)).list_snapshots(
                bucket_id=bucket_id
            )
            for snapshot in snapshots:
                _require_bucket(snapshot, bucket_id)
            return ExpedientesListOperationReport(bucket_id=bucket_id, rows=tuple(_summary(s) for s in snapshots))

        report = await asyncio.to_thread(read)
        await context.events.phase(_LIST_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="expedientes-list-result"
        )


class ExpedientesShowExecutor:
    """Read one encrypted snapshot and retain it as a private operand."""

    def __init__(self, ports_factory: ExpedientesPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[ExpedientesShowRequest], context: OperationExecutorContext
    ) -> str:
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
        _check_identity(request, context, EXPEDIENTES_SHOW_DEFINITION_ID)
        await context.events.phase(_SHOW_PHASES[0])

        def read() -> ExpedientesShowOperationReport:
            snapshot = ExpedientesService(ports=self._ports_factory(bucket_id=bucket_id)).show(
                bucket_id=bucket_id, snapshot_id=request.payload.snapshot_id
            )
            _require_bucket(snapshot, bucket_id)
            return ExpedientesShowOperationReport(snapshot=snapshot)

        report = await asyncio.to_thread(read)
        await context.events.phase(_SHOW_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="expedientes-show-result"
        )


class ExpedientesLatestExecutor:
    """Read the most recent local summary, including an empty state."""

    def __init__(self, ports_factory: ExpedientesPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[ExpedientesLatestRequest], context: OperationExecutorContext
    ) -> str:
        bucket_id = _exact_bucket(request.payload.profile_id, request.subject_ref)
        _check_identity(request, context, EXPEDIENTES_LATEST_DEFINITION_ID)
        await context.events.phase(_LATEST_PHASES[0])

        def read() -> ExpedientesLatestOperationReport:
            snapshot = ExpedientesService(ports=self._ports_factory(bucket_id=bucket_id)).latest(bucket_id=bucket_id)
            if snapshot is not None:
                _require_bucket(snapshot, bucket_id)
            return ExpedientesLatestOperationReport(
                bucket_id=bucket_id, snapshot=_summary(snapshot) if snapshot else None
            )

        report = await asyncio.to_thread(read)
        await context.events.phase(_LATEST_PHASES[1])
        await context.events.effect(OperationEffect.NONE)
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="expedientes-latest-result"
        )


def _capabilities() -> OperationCapabilities:
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


def build_expedientes_list_definition(ports_factory: ExpedientesPortsFactory) -> OperationDefinition:
    """Declare an encrypted, profile-bound local snapshot inventory."""
    return OperationDefinition(
        definition_id=EXPEDIENTES_LIST_DEFINITION_ID,
        request_type=ExpedientesListRequest,
        result_type=ExpedientesListOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ExpedientesListRequest,
            executor_type=ExpedientesListExecutor,
            build=lambda: ExpedientesListExecutor(ports_factory),
        ),
        phase_codes=_LIST_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_expedientes_show_definition(ports_factory: ExpedientesPortsFactory) -> OperationDefinition:
    """Declare an encrypted, profile-bound declaration detail read."""
    return OperationDefinition(
        definition_id=EXPEDIENTES_SHOW_DEFINITION_ID,
        request_type=ExpedientesShowRequest,
        result_type=ExpedientesShowOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ExpedientesShowRequest,
            executor_type=ExpedientesShowExecutor,
            build=lambda: ExpedientesShowExecutor(ports_factory),
        ),
        phase_codes=_SHOW_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_expedientes_latest_definition(ports_factory: ExpedientesPortsFactory) -> OperationDefinition:
    """Declare a local newest-snapshot read with an empty state."""
    return OperationDefinition(
        definition_id=EXPEDIENTES_LATEST_DEFINITION_ID,
        request_type=ExpedientesLatestRequest,
        result_type=ExpedientesLatestOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ExpedientesLatestRequest,
            executor_type=ExpedientesLatestExecutor,
            build=lambda: ExpedientesLatestExecutor(ports_factory),
        ),
        phase_codes=_LATEST_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def _validate_receipt(receipt: OperationTerminalReceipt, *, definition_id: str, bucket_id: str) -> None:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(bucket_id)
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
    ):
        raise ValueError("expedientes read result contradicts its terminal receipt")


def _project_list(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not ExpedientesListOperationReport:
        raise ValueError("invalid expedientes list report")
    report = ExpedientesListOperationReport.model_validate(result, strict=True)
    _validate_receipt(receipt, definition_id=EXPEDIENTES_LIST_DEFINITION_ID, bucket_id=str(report.bucket_id))
    return ExpedientesListPublicResultV1(bucket_id=report.bucket_id, count=len(report.rows), rows=report.rows)


def _project_show(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not ExpedientesShowOperationReport:
        raise ValueError("invalid expedientes show report")
    report = ExpedientesShowOperationReport.model_validate(result, strict=True)
    snapshot = report.snapshot
    _validate_receipt(receipt, definition_id=EXPEDIENTES_SHOW_DEFINITION_ID, bucket_id=str(snapshot.bucket_id))
    return ExpedientesShowPublicResultV1(
        bucket_id=snapshot.bucket_id,
        snapshot_id=snapshot.snapshot_id,
        captured_at=snapshot.captured_at,
        source_url=snapshot.source_url,
        declaration_count=len(snapshot.declarations),
        declarations=tuple(
            ExpedienteDeclarationPublicV1(
                modelo=row.modelo,
                ejercicio=int(row.ejercicio),
                period=row.period.registry_token,
                expediente_id=row.expediente_id,
                estado=row.estado,
                tipo_solicitud=row.tipo_solicitud,
                observaciones=row.observaciones,
                presented_at=row.presented_at,
                justificante_link_text=row.justificante_link_text,
                archive_link_text=row.archive_link_text,
                declaration_copy_link_text=row.declaration_copy_link_text,
                justificante_cell_index=row.justificante_cell_index,
                archive_cell_index=row.archive_cell_index,
                declaration_copy_cell_index=row.declaration_copy_cell_index,
                mode=row.mode,
            )
            for row in snapshot.declarations
        ),
    )


def _project_latest(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not ExpedientesLatestOperationReport:
        raise ValueError("invalid expedientes latest report")
    report = ExpedientesLatestOperationReport.model_validate(result, strict=True)
    _validate_receipt(receipt, definition_id=EXPEDIENTES_LATEST_DEFINITION_ID, bucket_id=str(report.bucket_id))
    snapshot = report.snapshot
    return ExpedientesLatestPublicResultV1(
        bucket_id=report.bucket_id,
        snapshot_id=snapshot.snapshot_id if snapshot else None,
        captured_at=snapshot.captured_at if snapshot else None,
        source_url=snapshot.source_url if snapshot else None,
        declaration_count=snapshot.declaration_count if snapshot else None,
    )


def _resolve_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, definition_id: str
) -> ResolvedOperationAccess:
    expected_type: type[BaseModel]
    if definition_id == EXPEDIENTES_LIST_DEFINITION_ID:
        expected_type = ExpedientesListRequest
    elif definition_id == EXPEDIENTES_SHOW_DEFINITION_ID:
        expected_type = ExpedientesShowRequest
    elif definition_id == EXPEDIENTES_LATEST_DEFINITION_ID:
        expected_type = ExpedientesLatestRequest
    else:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != definition_id or not isinstance(request.payload, expected_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def resolve_expedientes_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    return _resolve_read_access(request, context, EXPEDIENTES_LIST_DEFINITION_ID)


def resolve_expedientes_show_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    return _resolve_read_access(request, context, EXPEDIENTES_SHOW_DEFINITION_ID)


def resolve_expedientes_latest_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    return _resolve_read_access(request, context, EXPEDIENTES_LATEST_DEFINITION_ID)


def build_expedientes_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind list request, disclosure, and closed result projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ExpedientesListRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ExpedientesListPublicResultV1
        ),
        result_projector=_project_list,
        access_resolver=resolve_expedientes_list_access,
    )


def build_expedientes_show_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind detail request, disclosure, and closed row projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ExpedientesShowRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ExpedientesShowPublicResultV1
        ),
        result_projector=_project_show,
        access_resolver=resolve_expedientes_show_access,
    )


def build_expedientes_latest_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind latest request, disclosure, and coherent optional result."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ExpedientesLatestRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ExpedientesLatestPublicResultV1
        ),
        result_projector=_project_latest,
        access_resolver=resolve_expedientes_latest_access,
    )


__all__ = [
    "EXPEDIENTES_LATEST_DEFINITION_ID",
    "EXPEDIENTES_LIST_DEFINITION_ID",
    "EXPEDIENTES_SHOW_DEFINITION_ID",
    "ExpedienteDeclarationPublicV1",
    "ExpedientesLatestPublicResultV1",
    "ExpedientesLatestRequest",
    "ExpedientesListPublicResultV1",
    "ExpedientesListRequest",
    "ExpedientesShowPublicResultV1",
    "ExpedientesShowRequest",
    "build_expedientes_latest_definition",
    "build_expedientes_latest_registration",
    "build_expedientes_list_definition",
    "build_expedientes_list_registration",
    "build_expedientes_show_definition",
    "build_expedientes_show_registration",
]
