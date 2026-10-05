"""Reconcile a worker-owned encrypted justificante capture with one work unit."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.identity.hex_ids import CalculationRevisionId, SnapshotId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..ledger.read_access import resolve_ledger_commit_access
from ..live.filed_observation_ports import FiledObservationProtocol
from ..live.justificante import (
    JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
    JustificanteCaptureSnapshotService,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_terminal_receipt_match,
)
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_errors import CalculationRevisionNotFoundError
from .reconciliation import (
    ModeloReconciliationBytesCommand,
    PreparedModeloReconciliation,
    prepare_filed_observation_reconciliation,
    prepare_modelo_reconcile_bytes,
)
from .reconciliation_import_operation import ModeloReconciliationImportProjection
from .reconciliation_records import ModeloReconciliationEvidenceKind
from .work_addressing import ModeloWorkAddressNotFoundError
from .work_unit_repository import work_unit_catalogue_repository

MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID = "modelo.reconcile.pull"
_PHASES = ("modelo-reconcile-pull.prepare", "modelo-reconcile-pull.persist", "modelo-reconcile-pull.result")
_MAX_RESULT_DOCUMENT_BYTES = 48 * 1024


class ModeloReconciliationPullRequest(CredentialFreeOperationRequest):
    """Address a captured receipt and exact work unit in one bound profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    snapshot_id: SnapshotId | None = None
    observation_id: SnapshotId | None = None
    source_kind: ModeloReconciliationEvidenceKind = ModeloReconciliationEvidenceKind.JUSTIFICANTE
    actor: Annotated[str, Field(min_length=1, max_length=64, pattern=r"\S")] = "operator"

    @model_validator(mode="after")
    def _exact_evidence_selection(self) -> ModeloReconciliationPullRequest:
        if self.source_kind is ModeloReconciliationEvidenceKind.JUSTIFICANTE:
            valid = self.snapshot_id is not None and self.observation_id is None
        else:
            valid = self.observation_id is not None and self.snapshot_id is None
        if not valid:
            raise ValueError("reconciliation pull requires exactly the selected evidence handle")
        return self


def reconciliation_pull_source_ref(
    source_kind: ModeloReconciliationEvidenceKind,
    snapshot_id: str | None,
    observation_id: str | None,
) -> str:
    """Name the selected encrypted evidence without exposing a filesystem path."""
    if (
        source_kind is ModeloReconciliationEvidenceKind.JUSTIFICANTE
        and (snapshot_id is None or observation_id is not None)
    ) or (
        source_kind is ModeloReconciliationEvidenceKind.DECLARATION
        and (observation_id is None or snapshot_id is not None)
    ):
        raise ValueError("reconciliation evidence reference is inconsistent with its source kind")
    if source_kind is ModeloReconciliationEvidenceKind.JUSTIFICANTE:
        return f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot_id}"
    return f"secure-object://cadrumo.outbound.aeat.sede.filed_declaration.observations/{observation_id}"


class ModeloReconciliationPullOperationReport(BaseModel):
    """Keep the public comparison coupled to evidence of its local write."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloReconciliationImportProjection
    snapshot_id: SnapshotId | None = None
    observation_id: SnapshotId | None = None
    source_kind: ModeloReconciliationEvidenceKind = ModeloReconciliationEvidenceKind.JUSTIFICANTE
    local_write_performed: Literal[True]


def _project_reconciliation_pull(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = ModeloReconciliationPullOperationReport.model_validate(result, strict=True)
    projection = report.projection
    expected_source_ref = reconciliation_pull_source_ref(report.source_kind, report.snapshot_id, report.observation_id)
    contradiction = "modelo reconciliation pull result contradicts its terminal receipt"
    require_terminal_receipt_match(
        receipt,
        definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.bucket_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        message=contradiction,
    )
    if projection.source_kind is not report.source_kind or projection.source_path != expected_source_ref:
        raise ValueError(contradiction)
    return projection


class ModeloReconciliationPullExecutor:
    """Prepare against a captured PDF, then guard the atomic record/event write."""

    def __init__(
        self,
        service_factory: Callable[[str], JustificanteCaptureSnapshotService],
        observation_loader: Callable[[str, str], FiledObservationProtocol] | None = None,
    ) -> None:
        """Bind the exact-profile secure snapshot service factory."""
        self._service_factory = service_factory
        self._observation_loader = observation_loader

    async def execute(
        self,
        request: OperationRequest[ModeloReconciliationPullRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Compare one captured receipt and persist its record and event."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        await context.events.phase(_PHASES[0])

        def prepare() -> PreparedModeloReconciliation:
            if require_active_bucket_id() != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            unit = work_unit_catalogue_repository(bucket_id=profile_id).load().get(payload.work_unit_id)
            if unit is None:
                raise ModeloWorkAddressNotFoundError(
                    translated_message="errors.error.modelo_work_address_not_found",
                    context={"work_unit_present": False},
                )
            if unit.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if payload.source_kind is ModeloReconciliationEvidenceKind.DECLARATION:
                if self._observation_loader is None or payload.observation_id is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                observation = self._observation_loader(profile_id, payload.observation_id)
                if (
                    observation.modelo != str(unit.modelo)
                    or observation.ejercicio != unit.filing_year
                    or observation.period != unit.period
                ):
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                with validating_governed_facts(context.authority_operation):
                    return prepare_filed_observation_reconciliation(
                        work_unit=unit,
                        observation=observation,
                        source_ref=reconciliation_pull_source_ref(payload.source_kind, None, payload.observation_id),
                        actor=payload.actor,
                        calculation_revision_id=payload.calculation_revision_id,
                        operation=context.authority_operation,
                    )
            if payload.snapshot_id is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            snapshot = self._service_factory(profile_id).show(payload.snapshot_id)
            if unit.bucket_id != profile_id or snapshot.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if (
                snapshot.modelo != str(unit.modelo)
                or snapshot.filing_year != unit.filing_year
                or snapshot.period != unit.period
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            source_ref = f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}"
            command = ModeloReconciliationBytesCommand(
                work_unit_id=unit.work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_bytes=snapshot.decoded_pdf_bytes(),
                source_ref=source_ref,
                actor=payload.actor,
                calculation_revision_id=payload.calculation_revision_id,
            )
            with validating_governed_facts(context.authority_operation):
                prepared = prepare_modelo_reconcile_bytes(command, operation=context.authority_operation)
            return prepared

        try:
            prepared = await await_cancellation_complete(
                asyncio.to_thread(prepare), task_name="modelo-reconciliation-pull-prepare"
            )
        except CalculationRevisionNotFoundError as exc:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from exc
        projection = ModeloReconciliationImportProjection.from_report(prepared.report)
        expected_source_ref = reconciliation_pull_source_ref(
            payload.source_kind, payload.snapshot_id, payload.observation_id
        )
        if (
            projection.bucket_id != profile_id
            or projection.work_unit_id != payload.work_unit_id
            or (
                payload.calculation_revision_id is not None
                and projection.calculation_revision_id != payload.calculation_revision_id
            )
            or projection.source_kind is not payload.source_kind
            or projection.source_path != expected_source_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_DOCUMENT_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

        await context.events.phase(_PHASES[1])
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            persisted = prepared.persist()
        if persisted != prepared.report:
            raise ValueError("prepared modelo reconciliation changed while being persisted")
        await context.events.effect(OperationEffect.UPDATED)

        await context.events.phase(_PHASES[2])
        result = ModeloReconciliationPullOperationReport(
            projection=projection,
            snapshot_id=payload.snapshot_id,
            observation_id=payload.observation_id,
            source_kind=payload.source_kind,
            local_write_performed=True,
        )
        async with context.cancellation.irreversible_section():
            return await context.operands.put(result, written_at=now())


def build_modelo_reconciliation_pull_definition(
    service_factory: Callable[[str], JustificanteCaptureSnapshotService],
    observation_loader: Callable[[str, str], FiledObservationProtocol] | None = None,
) -> OperationDefinition:
    """Declare a non-replayable write over an existing encrypted capture."""
    return OperationDefinition(
        definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
        request_type=ModeloReconciliationPullRequest,
        result_type=ModeloReconciliationPullOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloReconciliationPullRequest,
            executor_type=ModeloReconciliationPullExecutor,
            build=lambda: ModeloReconciliationPullExecutor(service_factory, observation_loader),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_modelo_reconciliation_pull_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax disclosure and authorization for the commit."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
        payload_type=ModeloReconciliationPullRequest,
        access_profile_id=context.profile_id,
    )
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_modelo_reconciliation_pull_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Release the full comparison only with a truthful terminal receipt."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloReconciliationImportProjection,
        result_projector=_project_reconciliation_pull,
        access_resolver=resolve_modelo_reconciliation_pull_access,
    )


__all__ = [
    "MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID",
    "ModeloReconciliationPullExecutor",
    "ModeloReconciliationPullOperationReport",
    "ModeloReconciliationPullRequest",
    "build_modelo_reconciliation_pull_definition",
    "build_modelo_reconciliation_pull_registration",
    "resolve_modelo_reconciliation_pull_access",
]
