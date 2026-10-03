"""Registered exact-profile read of one persisted Modelo filing record."""

from __future__ import annotations

from functools import partial
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
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
from .filing_projection import ModeloFilingRecordSnapshot
from .filing_record_ownership import load_profile_filing_record
from .metadata_projection import ModeloWorkMetadataSnapshot
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID = "modelo.work.filing_record"


class ModeloWorkFilingRecordRequest(CredentialFreeOperationRequest):
    """Select one filing by exact identity in the admitted profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    filing_record_id: FilingRecordId


class ModeloWorkFilingRecordProjection(BaseModel):
    """The selected canonical filing and its exact owning work unit."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    record: ModeloFilingRecordSnapshot
    unit: ModeloWorkMetadataSnapshot

    @model_validator(mode="after")
    def _bound_result(self) -> Self:
        if (
            self.record.bucket_id != str(self.profile_id)
            or self.unit.bucket_id != str(self.profile_id)
            or self.record.work_unit_id != self.unit.work_unit_id
            or self.record.modelo != self.unit.modelo
            or self.record.filing_year != self.unit.filing_year
            or self.record.period != self.unit.period
        ):
            raise ValueError("filing projection coordinates do not match the selected profile and work unit")
        return self


def _capture(
    payload: ModeloWorkFilingRecordRequest, bundle: VerificationRepositoryBundle
) -> ModeloWorkFilingRecordProjection:
    record, unit = load_profile_filing_record(
        bundle, profile_id=payload.profile_id, filing_record_id=payload.filing_record_id
    )
    return ModeloWorkFilingRecordProjection(
        profile_id=payload.profile_id,
        record=ModeloFilingRecordSnapshot.from_record(record),
        unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
    )


class ModeloWorkFilingRecordExecutor:
    """Capture the exact persisted filing inside worker-owned profile custody."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkFilingRecordRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID)

        return await capture_read_result(
            context,
            partial(_capture, payload, self._factory(str(payload.profile_id), operation=context.authority_operation)),
            task_name="modelo-filing-record-read",
        )


def build_modelo_work_filing_record_definition(factory: VerificationRepositoryBundleFactory) -> OperationDefinition:
    """Declare an encrypted-result, credential-free exact filing read."""
    return OperationDefinition(
        definition_id=MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkFilingRecordRequest,
        result_type=ModeloWorkFilingRecordProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkFilingRecordRequest,
            executor_type=ModeloWorkFilingRecordExecutor,
            build=lambda: ModeloWorkFilingRecordExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_filing_record_registration(
    definition: OperationDefinition, factory: VerificationRepositoryBundleFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Resolve current period at admission and retain its scope for history."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloWorkFilingRecordRequest
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
            projection = _capture(payload, factory(str(payload.profile_id), operation=context.authority_operation))
            periods = frozenset({projection.unit.period.to_period()})
        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkFilingRecordProjection,
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID",
    "ModeloWorkFilingRecordProjection",
    "ModeloWorkFilingRecordRequest",
    "build_modelo_work_filing_record_definition",
    "build_modelo_work_filing_record_registration",
]
