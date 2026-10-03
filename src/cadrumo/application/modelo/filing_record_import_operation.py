"""Registered exact-profile import of external modelo filing evidence."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.identity.hex_ids import WorkUnitId
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    require_single_period_admission,
)
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_action_ports import CalculationActionPorts, CalculationActionPortsFactory
from .external_import_actions import (
    ExternalFilingBaselineSource,
    ExternalFilingImportResult,
    external_filing_source_casillas,
    import_external_filing_evidence,
)
from .filing_chain_reconciliation import (
    FilingReconciliationOutcome,
)
from .filing_record_import_contracts import (
    MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
    ModeloFilingRecordImportOperationReport,
    ModeloFilingRecordImportProjection,
    ModeloFilingRecordImportReconciliationProjection,
    ModeloFilingRecordImportRequest,
)
from .filing_record_list_contracts import ModeloFilingRecordListEntryProjection
from .local_observation_spreadsheet import parse_casilla_lexical_spreadsheet
from .work_addressing import ModeloWorkRegistryYearMismatchError, law_selected_revision_for_work_target

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


# Leave envelope and operation metadata headroom inside the local runtime frame.
_MAX_RESULT_DOCUMENT_BYTES = 48 * 1024


_PHASES = (
    "modelo-filing-record-import.prepare",
    "modelo-filing-record-import.commit",
    "modelo-filing-record-import.result",
)


def _project_filing_record_import(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release the allowlisted result only when the terminal effect agrees."""
    report = ModeloFilingRecordImportOperationReport.model_validate(result, strict=True)
    projection = report.projection
    expected_effect = OperationEffect.UPDATED if report.local_write_performed else OperationEffect.NONE
    require_terminal_receipt_match(
        receipt,
        definition_id=MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=expected_effect,
        message="filing import projection contradicts its terminal receipt",
    )
    return projection


def _selected_work_unit(ports: CalculationActionPorts, payload: ModeloFilingRecordImportRequest) -> WorkUnit:
    """Load the exact selected work unit from the worker's profile repositories."""
    profile_id = str(payload.profile_id)
    repository = ports.work_unit_repository
    if repository.bucket_id != profile_id or ports.work_lifecycle_ports.work_unit_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    work_unit = repository.load().get(payload.work_unit_id)
    if work_unit is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if work_unit.bucket_id != profile_id or work_unit.work_unit_id != payload.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return work_unit


def _declared_tax_id(ports: CalculationActionPorts, *, profile_id: str) -> str:
    """Read the declared NIF from this worker's exact profile capability."""
    values = ports.profile_read_ports.path_values.load_path_values(bucket_id=profile_id) or {}
    value = values.get("identity.tax_id")
    return value.strip() if isinstance(value, str) else ""


def _require_law_current_source_work_unit(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse source import unless its exact work unit remains law-current."""
    try:
        selected_revision_id = law_selected_revision_for_work_target(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            requested_revision_id=work_unit.revision_id,
            stored_revision_id=work_unit.revision_id,
            operation=operation,
        )
    except ModeloWorkRegistryYearMismatchError as exc:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from exc
    if selected_revision_id != work_unit.revision_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _record_projection(
    imported: ExternalFilingImportResult,
    *,
    profile_id: UUID,
    expected_work_unit_id: WorkUnitId | None,
    request: ModeloFilingRecordImportRequest,
) -> ModeloFilingRecordImportProjection:
    """Copy the writer receipt while correlating the result to the submitted intent."""
    record = imported.filing_record
    reconciliation = imported.reconciliation
    if (
        record.bucket_id != str(profile_id)
        or record.external_evidence is None
        or record.external_evidence.kind is not request.evidence_kind
        or record.external_evidence.reference_id != request.evidence_reference_id
        or (expected_work_unit_id is not None and record.work_unit_id != expected_work_unit_id)
        or reconciliation.bucket_id != str(profile_id)
        or reconciliation.filing_record_id != record.filing_record_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ModeloFilingRecordImportProjection(
        profile_id=profile_id,
        record=ModeloFilingRecordListEntryProjection.from_record(record),
        reconciliation=ModeloFilingRecordImportReconciliationProjection.from_result(reconciliation),
    )


class ModeloFilingRecordImportExecutor:
    """Run the existing external-import writer inside exact-profile custody."""

    def __init__(self, ports_factory: CalculationActionPortsFactory) -> None:
        """Retain the composition-supplied per-profile application capabilities."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ModeloFilingRecordImportRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Import one filing while guarding every possible domain write."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        await context.events.phase(_PHASES[0])

        source_file_lexicals = None
        if payload.source_path is not None:
            source_file_lexicals = await await_cancellation_complete(
                asyncio.to_thread(parse_casilla_lexical_spreadsheet, Path(payload.source_path)),
                task_name="modelo-filing-record-import-source-parse",
            )

        def import_record() -> tuple[ModeloFilingRecordImportProjection, bool]:
            if require_active_bucket_id() != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            ports = self._ports_factory(bucket_id=profile_id, operation=context.authority_operation)
            if (
                ports.operation is not context.authority_operation
                or ports.filing_repository.bucket_id != profile_id
                or ports.calculation_repository.bucket_id != profile_id
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            work_unit = _selected_work_unit(ports, payload)
            expected_tax_id = _declared_tax_id(ports, profile_id=profile_id)

            if payload.source_path is not None:
                if source_file_lexicals is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                source = ExternalFilingBaselineSource(
                    modelo=str(work_unit.modelo),
                    filing_year=work_unit.filing_year,
                    period=work_unit.period,
                    evidence_kind=payload.evidence_kind,
                    evidence_reference_id=payload.evidence_reference_id,
                    tax_id=expected_tax_id,
                    casilla_lexicals=source_file_lexicals,
                    registry_revision_id=work_unit.revision_id,
                )
                _require_law_current_source_work_unit(work_unit, operation=context.authority_operation)
                source_lexicals, casilla_values = external_filing_source_casillas(source)
            else:
                source_lexicals = None
                casilla_values = {key: Decimal(lexical) for key, lexical in payload.casilla_values}

            imported = import_external_filing_evidence(
                work_unit_id=payload.work_unit_id,
                casilla_values=casilla_values,
                source_lexical_values_by_casilla_id=source_lexicals,
                evidence_kind=payload.evidence_kind,
                evidence_reference_id=payload.evidence_reference_id,
                declared_kind=payload.declared_kind,
                actor=payload.actor,
                expected_tax_id=expected_tax_id,
                work_unit_repository=ports.work_unit_repository,
                calculation_repository=ports.calculation_repository,
                filing_repository=ports.filing_repository,
                bucket_event_repository=ports.bucket_event_repository,
                justificante_repository=None,
                observation_repository=ports.observation_repository,
                operation=context.authority_operation,
            )

            projection = _record_projection(
                imported,
                profile_id=payload.profile_id,
                expected_work_unit_id=payload.work_unit_id,
                request=payload,
            )
            local_write_performed = imported.reconciliation.outcome is not FilingReconciliationOutcome.ALREADY_RECORDED
            return projection, local_write_performed

        await context.events.phase(_PHASES[1])
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            projection, local_write_performed = await await_cancellation_complete(
                asyncio.to_thread(import_record),
                task_name="modelo-filing-record-import",
            )
            effect = OperationEffect.UPDATED if local_write_performed else OperationEffect.NONE
            await context.events.effect(effect)
            report = ModeloFilingRecordImportOperationReport(
                projection=projection,
                local_write_performed=local_write_performed,
            )
            if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_DOCUMENT_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            await context.events.phase(_PHASES[2])
            return await context.operands.put(report, written_at=now())


def build_modelo_filing_record_import_definition(
    ports_factory: CalculationActionPortsFactory,
) -> OperationDefinition:
    """Declare an interrupt-on-restart import with confidential request custody."""
    return OperationDefinition(
        definition_id=MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
        request_type=ModeloFilingRecordImportRequest,
        result_type=ModeloFilingRecordImportOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloFilingRecordImportRequest,
            executor_type=ModeloFilingRecordImportExecutor,
            build=lambda: ModeloFilingRecordImportExecutor(ports_factory),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def _resolve_import_period(
    payload: ModeloFilingRecordImportRequest,
    context: OperationAccessContext,
    ports_factory: CalculationActionPortsFactory,
) -> Period:
    """Resolve exact filing period from the selected unit in worker custody."""
    if context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = str(payload.profile_id)
    ports = ports_factory(bucket_id=profile_id, operation=context.authority_operation)
    repository = ports.work_unit_repository
    if repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    unit = repository.load().get(payload.work_unit_id)
    if unit is None or unit.bucket_id != profile_id or unit.work_unit_id != payload.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return unit.period


def build_modelo_filing_record_import_registration(
    definition: OperationDefinition,
    ports_factory: CalculationActionPortsFactory,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the CLI-compatible result and exact filing-period COMMIT policy."""

    def resolve(
        request: OperationRequest[BaseModel],
        context: OperationAccessContext,
        /,
    ) -> ResolvedOperationAccess:
        payload = require_access_request_profile_payload(
            request,
            definition_id=definition.definition_id,
            payload_type=ModeloFilingRecordImportRequest,
            access_profile_id=context.profile_id,
        )

        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            period = _resolve_import_period(payload, context, ports_factory)
            periods = frozenset({period})

        resolved = resolve_ledger_read_access(
            request,
            context,
            profile_id=payload.profile_id,
            periods=periods,
        )
        disclosures = resolved.policy.disclosures
        policy = OperationAccessPolicy.model_validate(
            {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
        )
        if context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=schema.schema_id,
                        category=DisclosureCategory.TAX_VALUES,
                    ),
                )
            )
            policy = policy.model_copy(update={"disclosures": disclosures})
        return ResolvedOperationAccess(request=resolved.request, policy=policy)

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloFilingRecordImportProjection,
        result_projector=_project_filing_record_import,
        access_resolver=resolve,
    )
