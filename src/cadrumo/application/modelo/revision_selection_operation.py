"""Registered, profile-bound selection of a persisted modelo calculation revision."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
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
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
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
from ..operations.public_period import PublicPeriod
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
from .metadata_projection import ModeloWorkMetadataSnapshot
from .selectors import (
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorError,
    resolve_modelo_calculation_revision_pick,
)
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory
from .work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ModeloWorkSelectorError,
    resolve_modelo_work_unit_for_operator_target,
)
from .work_lifecycle import RevisionParentOperation, require_revision_parent_active

MODELO_WORK_REVISION_OPERATION_DEFINITION_ID = "modelo.work.revision"


class ModeloWorkRevisionRequest(CredentialFreeOperationRequest):
    """Exact or natural work address and canonical calculation-revision pick."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId | None = None
    work_unit_id: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$")] | None = None
    modelo: Annotated[str, Field(min_length=1, max_length=16)] | None = None
    year: FilingYear | None = None
    period: PublicPeriod | None = None
    revision: RevisionId | None = None
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT
    default_for: ModeloCalculationRevisionDefault | None = None


class ModeloWorkRevisionProjection(BaseModel):
    """Bounded selection and existing granting report, without financial values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    unit: ModeloWorkMetadataSnapshot
    calculation_revision_id: CalculationRevisionId
    calculation_state: CalculationRevisionState
    verification_report_id: VerificationReportId | None
    granted_verificado_completo: bool

    @model_validator(mode="after")
    def _bound_result(self) -> ModeloWorkRevisionProjection:
        if self.unit.bucket_id != str(self.profile_id):
            raise ValueError("revision projection profile does not match its work unit")
        if (self.verification_report_id is not None) != self.granted_verificado_completo:
            raise ValueError("revision projection report and grant must agree")
        return self


def _unit(
    payload: ModeloWorkRevisionRequest, bundle: VerificationRepositoryBundle, *, operation: PinnedAuthorityOperation
) -> WorkUnit:
    """Resolve the persisted unit before interpreting its revision selector."""
    profile_id = str(payload.profile_id)
    if bundle.work_unit.bucket_id != profile_id or bundle.calculation.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    catalogue = bundle.work_unit.load()
    if (
        payload.calculation_revision_id is not None
        and payload.work_unit_id is None
        and payload.modelo is None
        and payload.year is None
        and payload.period is None
        and payload.revision is None
    ):
        revision = bundle.calculation.load(operation=operation).get(payload.calculation_revision_id)
        if revision is None:
            # The established verify/file positional-id route also accepts an
            # exact work-unit id and then selects its current calculation.
            unit = catalogue.get(payload.calculation_revision_id) if payload.default_for in {"verify", "file"} else None
        else:
            unit = catalogue.get(revision.work_unit_id)
        if unit is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    else:
        unit = resolve_modelo_work_unit_for_operator_target(
            work_unit_id=payload.work_unit_id,
            modelo=payload.modelo,
            year=payload.year,
            period=payload.period.to_period() if payload.period is not None else None,
            registry_revision_id=payload.revision,
            bucket_id=profile_id,
            catalogue=catalogue,
            resolved_bucket_id=profile_id,
            operation=operation,
        )
    if unit.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


def _capture(
    payload: ModeloWorkRevisionRequest, bundle: VerificationRepositoryBundle, operation: OperationExecutorContext
) -> ModeloWorkRevisionProjection:
    unit = _unit(payload, bundle, operation=operation.authority_operation)
    selected_id = payload.calculation_revision_id
    if (
        selected_id is not None
        and selected_id == unit.work_unit_id
        and bundle.calculation.load(operation=operation.authority_operation).get(selected_id) is None
    ):
        selected_id = None
    selection = resolve_modelo_calculation_revision_pick(
        unit,
        selector=payload.selector,
        calculation_revision_id=selected_id,
        default_for=payload.default_for,
        calculation_repository=bundle.calculation,
        operation=operation.authority_operation,
    )
    revision = selection.revision
    if payload.default_for in {"verify", "file"}:
        require_revision_parent_active(
            work_unit=unit,
            calculation_revision_id=revision.calculation_revision_id,
            operation=RevisionParentOperation.VERIFY
            if payload.default_for == "verify"
            else RevisionParentOperation.FILE,
        )
    if bundle.verification.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    reports = require_verification_report_coordinates_current(
        bundle.verification.load(operation=operation.authority_operation), operation=operation.authority_operation
    ).for_calculation_revision(revision.calculation_revision_id)
    granting = tuple(report for report in reports if report.granted_verificado_completo)
    if len(granting) > 1 or (revision.verified_at is not None) != bool(granting):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return ModeloWorkRevisionProjection(
        profile_id=payload.profile_id,
        unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
        calculation_revision_id=revision.calculation_revision_id,
        calculation_state=revision.state,
        verification_report_id=granting[0].verification_report_id if granting else None,
        granted_verificado_completo=bool(granting),
    )


class ModeloWorkRevisionExecutor:
    """Capture one selected revision and its report under pinned authority."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkRevisionRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_REVISION_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            projection = await asyncio.to_thread(
                _capture,
                payload,
                self._factory(str(payload.profile_id), operation=context.authority_operation),
                context,
            )
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-revision-read")


def build_modelo_work_revision_definition(factory: VerificationRepositoryBundleFactory) -> OperationDefinition:
    """Declare one credential-free, encrypted-result revision read."""
    return OperationDefinition(
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRevisionRequest,
        result_type=ModeloWorkRevisionProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkRevisionRequest,
            executor_type=ModeloWorkRevisionExecutor,
            build=lambda: ModeloWorkRevisionExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,),
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


def build_modelo_work_revision_registration(
    definition: OperationDefinition, factory: VerificationRepositoryBundleFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Resolve fresh period scope and retain admitted scope for history."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_WORK_REVISION_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloWorkRevisionRequest
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
            try:
                unit = _unit(
                    payload,
                    factory(str(payload.profile_id), operation=context.authority_operation),
                    operation=context.authority_operation,
                )
            except (
                ModeloWorkSelectorError,
                ModeloWorkAddressNotFoundError,
                ModeloWorkPeriodTokenError,
                ModeloCalculationRevisionSelectorError,
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
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
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ModeloWorkRevisionRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ModeloWorkRevisionProjection
        ),
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_WORK_REVISION_OPERATION_DEFINITION_ID",
    "ModeloWorkRevisionProjection",
    "ModeloWorkRevisionRequest",
    "build_modelo_work_revision_definition",
    "build_modelo_work_revision_registration",
]
