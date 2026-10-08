"""Registered local publication of explicitly selected saved reconciliation reviews."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.external_constants import OutputLanguage
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
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
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..ledger.read_access import resolve_ledger_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationIdentity,
    OperationRequest,
    OperationTerminalReceipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_payload, require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..storage.calc_sheets.workbook_export import SheetWorkbookMaterializer
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .export_sink import LocalFileExportSink
from .reconciliation_export import build_modelo_reconciliation_export_plan
from .reconciliation_export_labels import ReconciliationWorkbookLabels
from .reconciliation_list_operation import ModeloReconciliationListEntryProjection, ModeloReconciliationListProjection
from .reconciliation_records import list_modelo_reconciliations

RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID = "modelo.reconcile.export-xlsx"


class ReconciliationExportXlsxRequest(CredentialFreeOperationRequest):
    """Select one saved record, one work unit, or an explicitly requested full history."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    event_id: Hex64Str | None = None
    work_unit_id: WorkUnitId | None = None
    all_history: bool = False
    output_path: str = Field(min_length=1, max_length=4096)
    replace_existing: bool = False
    report_language: OutputLanguage = OutputLanguage.ES

    @model_validator(mode="after")
    def _explicit_selection_and_path(self) -> Self:
        if sum((self.event_id is not None, self.work_unit_id is not None, self.all_history)) != 1:
            raise ValueError("select exactly one reconciliation record, work unit, or full history")
        if not Path(self.output_path).is_absolute():
            raise ValueError("reconciliation export output path must be absolute")
        return self


class ReconciliationExportXlsxProjection(BaseModel):
    """Settled local byte receipt without the exported taxpayer values."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    event_id: Hex64Str | None = None
    work_unit_id: WorkUnitId | None = None
    all_history: bool
    reconciliation_count: NonNegativeInt
    difference_count: NonNegativeInt
    advisory_count: NonNegativeInt
    output_path: str
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    snapshot_digest: ContentDigest
    title: str


class ReconciliationExportXlsxResult(ReconciliationExportXlsxProjection):
    """Worker-owned publication receipt before terminal-gated public disclosure."""

    publication_id: UUID
    operation_identity: OperationIdentity


@dataclass(frozen=True, slots=True)
class ReconciliationExportXlsxPorts:
    """Profile-bound materializer composed inside the admitted host custody lifetime."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    materialize: SheetWorkbookMaterializer


class ReconciliationExportXlsxPortsFactory(Protocol):
    """Bind the local workbook materializer to the exact profile and authority pin."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ReconciliationExportXlsxPorts:
        """Return the admitted profile's export ports."""
        ...


def _read_selected(
    payload: ReconciliationExportXlsxRequest, operation: PinnedAuthorityOperation
) -> ModeloReconciliationListProjection:
    entries = list_modelo_reconciliations(
        bucket_id=str(payload.profile_id), operation=operation, work_unit_id=payload.work_unit_id
    )
    if payload.event_id is not None:
        entries = tuple(row for row in entries if row.event_id == payload.event_id)
        if len(entries) != 1:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return ModeloReconciliationListProjection(
        profile_id=payload.profile_id,
        work_unit_id=payload.work_unit_id,
        reconciliation_count=len(entries),
        reconciliations=tuple(ModeloReconciliationListEntryProjection.from_history_entry(row) for row in entries),
    )


class ReconciliationExportXlsxExecutor:
    """Read stored review details, render once, then guard local publication."""

    def __init__(self, factory: ReconciliationExportXlsxPortsFactory) -> None:
        """Retain the composition factory without opening custody."""
        self._factory = factory

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Publish only the explicitly requested stored comparison set."""
        payload = require_access_request_payload(
            request,
            definition_id=RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID,
            payload_type=ReconciliationExportXlsxRequest,
        )
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID)
        ports = self._factory(profile_id=payload.profile_id, operation=context.authority_operation)
        if ports.profile_id != payload.profile_id or ports.operation is not context.authority_operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        sink = LocalFileExportSink(path=Path(payload.output_path), replace_existing=payload.replace_existing)
        sink.require_writable()
        projection = await asyncio.to_thread(_read_selected, payload, ports.operation)
        plan = build_modelo_reconciliation_export_plan(
            projection,
            publication_id=uuid4(),
            exported_at=now(),
            label=ReconciliationWorkbookLabels(payload.report_language),
        )
        data = await asyncio.to_thread(ports.materialize, plan)

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                require_operation_profile(request, context, payload.profile_id)
                sink.require_writable()
                await context.events.effect(OperationEffect.UNKNOWN)
                receipt = await asyncio.to_thread(sink.write, data)
                await context.events.effect(OperationEffect.UPDATED)
                result = ReconciliationExportXlsxResult(
                    publication_id=plan.metadata.publication_id,
                    operation_identity=context.identity,
                    profile_id=payload.profile_id,
                    event_id=payload.event_id,
                    work_unit_id=payload.work_unit_id,
                    all_history=payload.all_history,
                    reconciliation_count=len(projection.reconciliations),
                    difference_count=sum(row.diff_count for row in projection.reconciliations),
                    advisory_count=sum(row.advisory_count for row in projection.reconciliations),
                    output_path=str(receipt.path),
                    byte_size=receipt.byte_size,
                    file_sha256=receipt.sha256,
                    snapshot_digest=plan.metadata.snapshot_digest,
                    title=plan.metadata.title,
                )
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(publish(), task_name="reconciliation-xlsx-publication")


def build_reconciliation_export_xlsx_definition(factory: ReconciliationExportXlsxPortsFactory) -> OperationDefinition:
    """Enroll a guarded local export without remote reads or filing mutations."""
    return build_single_phase_definition(
        definition_id=RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID,
        request_type=ReconciliationExportXlsxRequest,
        result_type=ReconciliationExportXlsxResult,
        executor_type=ReconciliationExportXlsxExecutor,
        build=lambda: ReconciliationExportXlsxExecutor(factory),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _resolve_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    payload = require_access_request_payload(
        request,
        definition_id=RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID,
        payload_type=ReconciliationExportXlsxRequest,
    )
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def _project_result(value: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(value) is not ReconciliationExportXlsxResult:
        raise ValueError("invalid reconciliation export result")
    if (
        receipt.identity != value.operation_identity
        or receipt.identity.definition_id != RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(value.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("reconciliation export result differs from its terminal receipt")
    return ReconciliationExportXlsxProjection.model_validate(
        value.model_dump(exclude={"publication_id", "operation_identity"})
    )


def build_reconciliation_export_xlsx_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require whole-profile consent and only disclose a settled publication receipt."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ReconciliationExportXlsxProjection,
        access_resolver=_resolve_access,
        result_projector=_project_result,
    )
