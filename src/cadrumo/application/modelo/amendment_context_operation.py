"""Registered profile-bound context read for a guided Modelo amendment."""

from __future__ import annotations

from functools import partial
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...domain.calculations.registry.amendment_regime_policy import permitted_amendment_kind_values_for_period
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.query_reports import ModeloCasillaRow
from ...domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentKind,
    m303_rectificativa_motive_is_applicable,
)
from ...domain.modelos.filing_record import ModeloRecord
from ...domain.modelos.work_unit import WorkUnit
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_single_period_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_projection import ModeloCalculationSnapshot
from .filing_projection import ModeloFilingRecordSnapshot
from .filing_record_ownership import load_profile_filing_record
from .metadata_projection import ModeloWorkMetadataSnapshot
from .registry_discovery import registry_casillas_for_registry_scope
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID = "modelo.work.amendment_context"


class ModeloWorkAmendmentContextRequest(CredentialFreeOperationRequest):
    """Name one exact stored filing in the currently admitted profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    filing_record_id: FilingRecordId


class ModeloWorkAmendmentContextProjection(BaseModel):
    """Canonical filing, unit, and calculation facts for guided correction."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    record: ModeloFilingRecordSnapshot
    unit: ModeloWorkMetadataSnapshot
    calculation: ModeloCalculationSnapshot
    casilla_rows: tuple[ModeloCasillaRow, ...]
    permitted_amendment_kinds: tuple[CalculationRevisionAmendmentKind, ...]
    m303_rectificativa_motive_applicable: bool

    @model_validator(mode="after")
    def _bound_result(self) -> Self:
        profile_id = str(self.profile_id)
        if (
            self.record.bucket_id != profile_id
            or self.unit.bucket_id != profile_id
            or self.calculation.bucket_id != profile_id
            or self.record.work_unit_id != self.unit.work_unit_id
            or self.calculation.work_unit_id != self.unit.work_unit_id
            or self.record.calculation_revision_id != self.calculation.calculation_revision_id
            or self.record.modelo != self.unit.modelo
            or self.calculation.modelo != self.unit.modelo
            or self.record.filing_year != self.unit.filing_year
            or self.calculation.filing_year != self.unit.filing_year
            or self.record.period != self.unit.period
            or self.calculation.period != self.unit.period
        ):
            raise ValueError("amendment context filing, work unit, and calculation do not match")
        row_ids = tuple(row.casilla_id for row in self.casilla_rows)
        if len(set(row_ids)) != len(row_ids):
            raise ValueError("amendment context has duplicate registry casillas")
        if not self.permitted_amendment_kinds or len(set(self.permitted_amendment_kinds)) != len(
            self.permitted_amendment_kinds
        ):
            raise ValueError("amendment context has invalid permitted kinds")
        return self


def _filing_unit(
    payload: ModeloWorkAmendmentContextRequest, bundle: VerificationRepositoryBundle
) -> tuple[ModeloRecord, WorkUnit]:
    if bundle.calculation.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return load_profile_filing_record(bundle, profile_id=payload.profile_id, filing_record_id=payload.filing_record_id)


def _capture(
    payload: ModeloWorkAmendmentContextRequest,
    bundle: VerificationRepositoryBundle,
    context: OperationExecutorContext,
) -> ModeloWorkAmendmentContextProjection:
    record, unit = _filing_unit(payload, bundle)
    revision = bundle.calculation.load(operation=context.authority_operation).get(record.calculation_revision_id)
    if revision is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if revision.work_unit_id != unit.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    evidence = revision.filing_instance_evidence
    motive_applicable = False
    if evidence is not None and str(unit.modelo) == "303":
        regimen = evidence.m303.regimen_simplificado.regimen_snapshot
        motive_applicable = m303_rectificativa_motive_is_applicable(
            registry_revision_id=regimen.registry_revision_id,
            record_design=regimen.record_design,
            operation=context.authority_operation,
        )
    with validating_governed_facts(context.authority_operation):
        permitted_values = permitted_amendment_kind_values_for_period(str(unit.modelo), unit.period)
    permitted_kinds = tuple(kind for kind in CalculationRevisionAmendmentKind if kind.value in permitted_values)
    if frozenset(kind.value for kind in permitted_kinds) != permitted_values:
        raise ValueError("amendment context contains an unknown permitted kind")
    return ModeloWorkAmendmentContextProjection(
        profile_id=payload.profile_id,
        record=ModeloFilingRecordSnapshot.from_record(record),
        unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
        calculation=ModeloCalculationSnapshot.from_revision(
            revision, work_unit=unit, operation=context.authority_operation
        ),
        casilla_rows=registry_casillas_for_registry_scope(
            str(unit.modelo),
            filing_year=unit.filing_year,
            period=unit.period.registry_token,
            operation=context.authority_operation,
        ).rows,
        permitted_amendment_kinds=permitted_kinds,
        m303_rectificativa_motive_applicable=motive_applicable,
    )


class ModeloWorkAmendmentContextExecutor:
    """Capture persisted amendment operands inside immutable worker custody."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkAmendmentContextRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID)

        return await capture_read_result(
            context,
            partial(
                _capture,
                payload,
                self._factory(str(payload.profile_id), operation=context.authority_operation),
                context,
            ),
            task_name="modelo-amendment-context-read",
        )


def build_modelo_work_amendment_context_definition(factory: VerificationRepositoryBundleFactory) -> OperationDefinition:
    """Declare one credential-free read with an encrypted public result."""
    return OperationDefinition(
        definition_id=MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkAmendmentContextRequest,
        result_type=ModeloWorkAmendmentContextProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkAmendmentContextRequest,
            executor_type=ModeloWorkAmendmentContextExecutor,
            build=lambda: ModeloWorkAmendmentContextExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_amendment_context_registration(
    definition: OperationDefinition, factory: VerificationRepositoryBundleFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Resolve period from the stored filing; retain admitted scope for history."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloWorkAmendmentContextRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        require_access_request_profile_identity(
            request,
            payload_profile_id=payload.profile_id,
            access_profile_id=context.profile_id,
        )
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            _record, unit = _filing_unit(
                payload, factory(str(payload.profile_id), operation=context.authority_operation)
            )
            periods = frozenset({unit.period})
        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkAmendmentContextProjection,
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID",
    "ModeloWorkAmendmentContextProjection",
    "ModeloWorkAmendmentContextRequest",
    "build_modelo_work_amendment_context_definition",
    "build_modelo_work_amendment_context_registration",
]
