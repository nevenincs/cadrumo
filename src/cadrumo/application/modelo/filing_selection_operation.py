"""Registered exact-profile read of one persisted Modelo filing record."""

from __future__ import annotations

import asyncio
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filing_projection import ModeloFilingRecordSnapshot
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
    profile_id = str(payload.profile_id)
    if bundle.filing.bucket_id != profile_id or bundle.work_unit.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    record = bundle.filing.load().get(payload.filing_record_id)
    if record is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if record.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    unit = bundle.work_unit.load().get(record.work_unit_id)
    if unit is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if (
        unit.bucket_id != profile_id
        or unit.work_unit_id != record.work_unit_id
        or unit.modelo != record.modelo
        or unit.filing_year != record.filing_year
        or unit.period != record.period
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
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

        async def capture() -> str:
            projection = await asyncio.to_thread(
                _capture, payload, self._factory(str(payload.profile_id), operation=context.authority_operation)
            )
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-filing-record-read")


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
        capabilities=OperationCapabilities(
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
        ),
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
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }:
            if (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or admitted.period_independent
                or len(admitted.periods) != 1
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            periods = admitted.periods
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            projection = _capture(payload, factory(str(payload.profile_id), operation=context.authority_operation))
            periods = frozenset({projection.unit.period.to_period()})
        disclosures = frozenset[DisclosurePermission]()
        if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                )
            )
        elif context.action is AccessAction.RESULT:
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
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=periods,
                period_independent=False,
                destination_id=context.destination_id,
            ),
            policy=OperationAccessPolicy(
                definition_id=request.definition_id,
                definition_contract_digest=context.contract.definition_contract_digest,
                actions=frozenset(
                    {
                        AccessAction.SUBMIT,
                        AccessAction.START,
                        AccessAction.RESUME,
                        AccessAction.OBSERVE,
                        AccessAction.RESULT,
                        AccessAction.CANCEL,
                        AccessAction.DETACH,
                    }
                ),
                disclosures=disclosures,
                periods=periods,
                allow_period_independent=False,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ModeloWorkFilingRecordRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloWorkFilingRecordProjection,
        ),
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID",
    "ModeloWorkFilingRecordProjection",
    "ModeloWorkFilingRecordRequest",
    "build_modelo_work_filing_record_definition",
    "build_modelo_work_filing_record_registration",
]
