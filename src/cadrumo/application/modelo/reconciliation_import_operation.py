"""Registered exact-profile import of local modelo reconciliation evidence."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.codes import ModeloCode
from ..ledger.read_access import resolve_ledger_commit_access
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
    ModeloReconciliationCommand,
    ModeloReconciliationReport,
    PreparedModeloReconciliation,
    prepare_modelo_reconcile,
)
from .reconciliation_list_operation import MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH
from .reconciliation_records import (
    ModeloReconciliationAdvisory,
    ModeloReconciliationDiff,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
)
from .verification_report_public_facts import ModeloVerificationRegistrySnapshotProjection
from .work_addressing import ModeloWorkAddressNotFoundError
from .work_selection import ModeloWorkSelectorRequest, ModeloWorkSelectorState, select_modelo_work_resolution
from .work_unit_repository import work_unit_catalogue_repository

MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID = "modelo.reconcile.import"
_PHASES = (
    "modelo-reconcile-import.prepare",
    "modelo-reconcile-import.persist",
    "modelo-reconcile-import.result",
)

# A settled operation result travels inside a native 64 KiB runtime frame. Keep
# 16 KiB available for its envelope and the remaining operation metadata.
_MAX_RESULT_DOCUMENT_BYTES = 48 * 1024

_BoundedSourcePath = Annotated[
    str,
    Field(
        min_length=1,
        max_length=MAX_MODELO_RECONCILIATION_SOURCE_PATH_LENGTH,
        pattern=r"\S",
    ),
]
_WorkUnitLookupId = Annotated[
    str,
    Field(min_length=12, max_length=64, pattern=r"^(?:[0-9a-fA-F]{12}|[0-9a-fA-F]{64})$"),
]
_ModeloSelector = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")]
_PeriodToken = Annotated[str, Field(min_length=1, max_length=16, pattern=r"\S")]
_RevisionSelector = Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]
_BucketSelector = Annotated[str, Field(min_length=1, max_length=128, pattern=r"\S")]


class ModeloReconciliationImportRequest(CredentialFreeOperationRequest):
    """Address one work unit and one local evidence file in an exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: _WorkUnitLookupId | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    modelo: _ModeloSelector | None = None
    filing_year: FilingYear | None = None
    period: _PeriodToken | None = None
    revision_id: _RevisionSelector | None = None
    bucket_id: _BucketSelector | None = None
    source_kind: ModeloReconciliationEvidenceKind
    source_path: _BoundedSourcePath
    actor: Annotated[str, Field(min_length=1, max_length=64, pattern=r"\S")] = "operator"

    @model_validator(mode="after")
    def _period_requires_filing_year(self) -> ModeloReconciliationImportRequest:
        """Keep the operator period token attached to its filing year."""
        if self.period is not None and self.filing_year is None:
            raise ValueError("filing_year is required when period is supplied")
        return self

    @field_validator("source_path")
    @classmethod
    def _require_local_path_text(cls, value: str) -> str:
        """Reject values that cannot designate a local filesystem path."""
        if "\x00" in value or not value.strip():
            raise ValueError("source_path must identify a local file")
        return value


class ModeloReconciliationImportAdvisoryProjection(BaseModel):
    """Closed immutable advisory fields with lossless context key/value pairs."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: str
    message: str
    context: tuple[tuple[str, str], ...]

    @model_validator(mode="after")
    def _require_canonical_context(self) -> ModeloReconciliationImportAdvisoryProjection:
        """Refuse duplicate or reordered context keys at the public boundary."""
        keys = tuple(key for key, _value in self.context)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("reconciliation advisory context keys must be unique and sorted")
        return self


class ModeloReconciliationImportProjection(BaseModel):
    """Public report with every canonical diff and advisory field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    bucket_id: BucketId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    registry_snapshot_ref: ModeloVerificationRegistrySnapshotProjection | None = None
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    advisories: tuple[ModeloReconciliationImportAdvisoryProjection, ...] = ()
    reconciled_at: datetime
    narrative: str = ""

    @classmethod
    def from_report(cls, report: ModeloReconciliationReport) -> ModeloReconciliationImportProjection:
        """Copy the canonical report without dropping diff or advisory data."""
        return cls(
            work_unit_id=report.work_unit_id,
            calculation_revision_id=report.calculation_revision_id,
            registry_snapshot_ref=(
                ModeloVerificationRegistrySnapshotProjection.from_snapshot(report.registry_snapshot_ref)
                if report.registry_snapshot_ref
                else None
            ),
            bucket_id=report.bucket_id,
            source_kind=report.source_kind,
            source_path=report.source_path,
            verdict=report.verdict,
            diffs=report.diffs,
            advisories=tuple(
                ModeloReconciliationImportAdvisoryProjection(
                    code=advisory.code,
                    message=advisory.message,
                    context=tuple(sorted(advisory.context.items())),
                )
                for advisory in report.advisories
            ),
            reconciled_at=report.reconciled_at,
            narrative=report.narrative,
        )

    def to_report(self) -> ModeloReconciliationReport:
        """Reconstruct the original advisory mappings for existing renderers."""
        return ModeloReconciliationReport(
            work_unit_id=self.work_unit_id,
            calculation_revision_id=self.calculation_revision_id,
            registry_snapshot_ref=(
                RegistrySnapshotRef(**self.registry_snapshot_ref.model_dump()) if self.registry_snapshot_ref else None
            ),
            bucket_id=self.bucket_id,
            source_kind=self.source_kind,
            source_path=self.source_path,
            verdict=self.verdict,
            diffs=self.diffs,
            advisories=tuple(
                ModeloReconciliationAdvisory(
                    code=advisory.code,
                    message=advisory.message,
                    context=dict(advisory.context),
                )
                for advisory in self.advisories
            ),
            reconciled_at=self.reconciled_at,
            narrative=self.narrative,
        )


class ModeloReconciliationImportOperationReport(BaseModel):
    """Private strict report retained in encrypted operation result storage."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloReconciliationImportProjection
    local_write_performed: Literal[True]


def _project_reconciliation_import(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release the complete report only when its settled receipt proves the write."""
    report = ModeloReconciliationImportOperationReport.model_validate(result, strict=True)
    projection = report.projection
    require_terminal_receipt_match(
        receipt,
        definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.bucket_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        message="modelo reconciliation import result contradicts its terminal receipt",
    )
    return projection


def _reconciliation_import_work_selector(payload: ModeloReconciliationImportRequest) -> ModeloWorkSelectorRequest:
    """Preserve the full and abbreviated operator addresses and optional period scope."""
    work_unit_lookup = payload.work_unit_id.lower() if payload.work_unit_id is not None else None
    typed_period = (
        Period.from_year_and_code(payload.filing_year, payload.period.strip())
        if payload.period is not None and payload.filing_year is not None
        else None
    )
    return ModeloWorkSelectorRequest(
        work_unit_id=(work_unit_lookup if work_unit_lookup is not None and len(work_unit_lookup) == 64 else None),
        operator_work_unit_id=(
            work_unit_lookup if work_unit_lookup is not None and len(work_unit_lookup) == 12 else None
        ),
        modelo=ModeloCode(payload.modelo) if payload.modelo is not None else None,
        filing_year=payload.filing_year,
        period=typed_period,
        revision_id=payload.revision_id,
        bucket_id=payload.bucket_id,
    )


class ModeloReconciliationImportExecutor:
    """Prepare a local comparison, then atomically persist its record and event."""

    async def execute(
        self,
        request: OperationRequest[ModeloReconciliationImportRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Reconcile one local PDF while keeping work scoped to its profile."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        await context.events.phase(_PHASES[0])

        def prepare() -> tuple[ModeloReconciliationCommand, PreparedModeloReconciliation]:
            if require_active_bucket_id() != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            catalogue = work_unit_catalogue_repository(bucket_id=profile_id).load()
            selector = _reconciliation_import_work_selector(payload)
            resolution = select_modelo_work_resolution(
                selector,
                catalogue=catalogue,
                bucket_id=profile_id,
            )
            selected_work_unit = resolution.work_unit
            if resolution.state is ModeloWorkSelectorState.ABSENT or selected_work_unit is None:
                raise ModeloWorkAddressNotFoundError(
                    translated_message="errors.error.modelo_work_address_not_found",
                    context={"work_unit_present": False},
                )
            if selected_work_unit.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            command = ModeloReconciliationCommand(
                work_unit_id=selected_work_unit.work_unit_id,
                source_kind=payload.source_kind,
                source_path=Path(payload.source_path),
                actor=payload.actor,
                calculation_revision_id=payload.calculation_revision_id,
            )
            with validating_governed_facts(context.authority_operation):
                prepared = prepare_modelo_reconcile(command, operation=context.authority_operation)
            return command, prepared

        try:
            command, prepared = await await_cancellation_complete(
                asyncio.to_thread(prepare),
                task_name="modelo-reconciliation-import-prepare",
            )
        except CalculationRevisionNotFoundError as exc:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from exc
        report = ModeloReconciliationImportProjection.from_report(prepared.report)
        if (
            report.bucket_id != profile_id
            or report.work_unit_id != command.work_unit_id
            or (
                payload.calculation_revision_id is not None
                and report.calculation_revision_id != payload.calculation_revision_id
            )
            or report.source_kind is not payload.source_kind
            or report.source_path != str(command.source_path)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if len(canonical_json_bytes(report.model_dump(mode="json"))) > _MAX_RESULT_DOCUMENT_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

        await context.events.phase(_PHASES[1])
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            persisted_report = prepared.persist()
        if persisted_report != prepared.report:
            raise ValueError("prepared modelo reconciliation changed while being persisted")
        await context.events.effect(OperationEffect.UPDATED)

        private_report = ModeloReconciliationImportOperationReport(
            projection=report,
            local_write_performed=True,
        )
        await context.events.phase(_PHASES[2])
        async with context.cancellation.irreversible_section():
            return await context.operands.put(private_report, written_at=now())


def build_modelo_reconciliation_import_definition() -> OperationDefinition:
    """Declare an interrupt-on-restart, exact-profile local evidence import."""
    return OperationDefinition(
        definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
        request_type=ModeloReconciliationImportRequest,
        result_type=ModeloReconciliationImportOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloReconciliationImportRequest,
            executor_type=ModeloReconciliationImportExecutor,
            build=ModeloReconciliationImportExecutor,
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_modelo_reconciliation_import_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require whole-profile tax disclosure and authorize the local commit."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
        payload_type=ModeloReconciliationImportRequest,
        access_profile_id=context.profile_id,
    )
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_modelo_reconciliation_import_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the complete grounded report to exact whole-profile access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloReconciliationImportProjection,
        result_projector=_project_reconciliation_import,
        access_resolver=resolve_modelo_reconciliation_import_access,
    )


__all__ = [
    "MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID",
    "ModeloReconciliationImportExecutor",
    "ModeloReconciliationImportOperationReport",
    "ModeloReconciliationImportProjection",
    "ModeloReconciliationImportRequest",
    "build_modelo_reconciliation_import_definition",
    "build_modelo_reconciliation_import_registration",
    "resolve_modelo_reconciliation_import_access",
]
