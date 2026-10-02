"""Read-only revision discovery within an explicitly authorized profile scope."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.modelos.calculation_revision import CalculationRevisionState
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
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .verification_repository_ports import VerificationRepositoryBundleFactory

MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID = "modelo.work.revisions"


class ModeloWorkRevisionsRequest(CredentialFreeOperationRequest):
    """An exact unit filter, or explicit profile-wide discovery."""

    profile_id: UUID
    work_unit_id: WorkUnitId | None = None


class ModeloRevisionInventoryRow(BaseModel):
    """Stored revision identity and lifecycle metadata without calculation values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: CalculationRevisionState
    created_at: datetime


class ModeloWorkRevisionsProjection(BaseModel):
    """One complete ordered inventory captured inside profile custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    work_unit_id_filter: WorkUnitId | None
    revisions: tuple[ModeloRevisionInventoryRow, ...]

    @model_validator(mode="after")
    def _coherent_rows(self) -> ModeloWorkRevisionsProjection:
        if len({row.calculation_revision_id for row in self.revisions}) != len(self.revisions):
            raise ValueError("revision inventory repeats an identity")
        if self.work_unit_id_filter is not None and any(
            row.work_unit_id != self.work_unit_id_filter for row in self.revisions
        ):
            raise ValueError("revision inventory contains another work unit")
        if tuple(sorted(self.revisions, key=lambda row: (row.work_unit_id, row.created_at))) != self.revisions:
            raise ValueError("revision inventory is not chronologically ordered")
        return self


class ModeloWorkRevisionsExecutor:
    """Capture discovery without the old read-side catalogue migration write."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        """Retain the exact-profile repository composition capability."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkRevisionsRequest], context: OperationExecutorContext
    ) -> str:
        """Store the canonical inventory in encrypted operands with no mutation."""
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID)

        def read() -> ModeloWorkRevisionsProjection:
            profile_id = str(payload.profile_id)
            operation = context.authority_operation
            bundle = self._factory(profile_id, operation=operation)
            if bundle.calculation.bucket_id != profile_id or bundle.work_unit.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            units = bundle.work_unit.load()
            if payload.work_unit_id is not None:
                unit = units.get(payload.work_unit_id)
                if unit is None or unit.bucket_id != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            rows: list[ModeloRevisionInventoryRow] = []
            for revision in bundle.calculation.load(operation=operation):
                if payload.work_unit_id is not None and revision.work_unit_id != payload.work_unit_id:
                    continue
                unit = units.get(revision.work_unit_id)
                if unit is None or unit.bucket_id != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                require_calculation_revision_coordinates_current(revision, operation=operation)
                rows.append(
                    ModeloRevisionInventoryRow(
                        calculation_revision_id=revision.calculation_revision_id,
                        work_unit_id=revision.work_unit_id,
                        state=revision.state,
                        created_at=revision.created_at,
                    )
                )
            return ModeloWorkRevisionsProjection(
                profile_id=payload.profile_id,
                work_unit_id_filter=payload.work_unit_id,
                revisions=tuple(sorted(rows, key=lambda row: (row.work_unit_id, row.created_at))),
            )

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-revision-inventory")


def build_modelo_work_revisions_definition(factory: VerificationRepositoryBundleFactory) -> OperationDefinition:
    """Declare recorded encrypted discovery with no domain mutation capability."""
    return OperationDefinition(
        definition_id=MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRevisionsRequest,
        result_type=ModeloWorkRevisionsProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkRevisionsRequest,
            executor_type=ModeloWorkRevisionsExecutor,
            build=lambda: ModeloWorkRevisionsExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_REVISIONS_OPERATION_DEFINITION_ID,),
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


def build_modelo_work_revisions_registration(
    definition: OperationDefinition, factory: VerificationRepositoryBundleFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Require independent-profile permission for unfiltered discovery.

    A period-restricted grant cannot list other periods by omitting the filter,
    even when it permits unrelated period-independent profile operations.
    Filtered discovery derives its one period from the immutable unit identity;
    historical release uses sealed admission rather than rereading the catalogue.
    """

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, ModeloWorkRevisionsRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        independent = payload.work_unit_id is None
        periods: frozenset[Period]
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
                or admitted.period_independent != independent
                or (not independent and len(admitted.periods) != 1)
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            periods = admitted.periods
        elif independent:
            periods = frozenset[Period]()
        else:
            if context.authority_operation is None or payload.work_unit_id is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            bundle = factory(str(context.profile_id), operation=context.authority_operation)
            if bundle.work_unit.bucket_id != str(context.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            unit = bundle.work_unit.load().get(payload.work_unit_id)
            if unit is None or unit.bucket_id != str(context.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            periods = frozenset({unit.period})
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
                period_independent=independent,
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
                allow_period_independent=independent,
                requires_all_periods=independent,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ModeloWorkRevisionsRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ModeloWorkRevisionsProjection
        ),
        access_resolver=resolve,
    )
