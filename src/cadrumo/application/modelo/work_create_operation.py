"""Registered exact-profile creation or reuse of canonical Modelo work."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.contribuyente.ccaa import CCAA
from ...domain.contribuyente.tax_residence import parse_tax_region
from ..operations.access_resolution import (
    COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
)
from ..operations.capabilities import RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..overview.status_report import build_filing_obligation_advisories
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.projections import record_to_values
from .action_errors import WorkUnitMutationRefusedError
from .metadata_projection import ModeloWorkMetadataSnapshot
from .profile_readiness_gate import (
    load_modelo_work_profile,
    require_existing_profile_baseline_ready_for_modelo_work,
    require_profile_ready_for_modelo_work,
)
from .work_addressing import (
    ModeloWorkEnsureResult,
    ensure_modelo_work_unit_for_active_target,
    law_selected_revision_for_work_target,
)
from .work_create_policy import (
    guard_active_profile_foral_ccaa,
    modelo_work_create_applicability_refusal,
    modelo_work_create_refusal_locale_key,
)
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory, WorkLifecyclePorts
from .work_profile import ModeloWorkProfile

MODELO_WORK_CREATE_OPERATION_DEFINITION_ID = "modelo.work.create"
MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE = "REFUSED_MODELO_WORK_CREATE_APPLICABILITY"


class ModeloWorkCreateRequest(BaseModel):
    """Private, bounded work target and operator intent for one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    period: PublicPeriod
    revision_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    actor: Annotated[str, Field(min_length=1, max_length=128)]
    causante_ccaa: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    allow_not_applicable: bool = False


class ModeloWorkCreateSuccess(BaseModel):
    """Canonical writer return plus locale-neutral advisory identities."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["success"] = "success"
    unit: ModeloWorkMetadataSnapshot
    reused: bool
    name_applied: Annotated[str, Field(min_length=1, max_length=200)] | None
    applicability_guard_bypassed: bool
    advisory_keys: tuple[Annotated[str, Field(min_length=1, max_length=160)], ...]

    @model_validator(mode="after")
    def _coherent_name(self) -> Self:
        if self.name_applied is not None and (not self.reused or self.name_applied != self.unit.name):
            raise ValueError("work create rename must describe the reused unit")
        return self


class ModeloWorkCreateRefusal(BaseModel):
    """Only the canonical applicability reason crosses the refusal detail door."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["refused"] = "refused"
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")]
    reason: Annotated[str, Field(min_length=1, max_length=2048)]


class ModeloWorkCreateResult(BaseModel):
    """Encrypted private result addressed by either terminal condition."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    period: PublicPeriod
    outcome: Annotated[ModeloWorkCreateSuccess | ModeloWorkCreateRefusal, Field(discriminator="kind")]

    @model_validator(mode="after")
    def _bound_outcome(self) -> Self:
        if isinstance(self.outcome, ModeloWorkCreateSuccess):
            unit = self.outcome.unit
            if unit.bucket_id != str(self.profile_id) or unit.period != self.period:
                raise ValueError("work create result belongs to another profile or period")
        return self


class ModeloWorkCreateProjection(BaseModel):
    """Explicit public fields released only by the terminal projector."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    period: PublicPeriod
    outcome: Annotated[ModeloWorkCreateSuccess | ModeloWorkCreateRefusal, Field(discriminator="kind")]

    @model_validator(mode="after")
    def _bound_outcome(self) -> Self:
        if isinstance(self.outcome, ModeloWorkCreateSuccess):
            unit = self.outcome.unit
            if unit.bucket_id != str(self.profile_id) or unit.period != self.period:
                raise ValueError("work create projection belongs to another profile or period")
        return self


def project_modelo_work_create_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only a result matching the recorded terminal condition and effect."""
    if (
        type(result) is not ModeloWorkCreateResult
        or receipt.identity.definition_id != MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
    ):
        raise ValueError("invalid work create result identity")
    private = ModeloWorkCreateResult.model_validate(result.model_dump(mode="python"), strict=True)
    if receipt.identity.subject_ref != profile_operation_subject(str(private.profile_id)):
        raise ValueError("work create result belongs to another subject")
    outcome = private.outcome
    if isinstance(outcome, ModeloWorkCreateRefusal):
        if (
            receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.refusal_ref != MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
            or receipt.effect is not OperationEffect.NONE
        ):
            raise ValueError("work create refusal has an incompatible terminal receipt")
    elif receipt.condition is not OperationTerminalCondition.SUCCEEDED or receipt.effect is not (
        OperationEffect.UPDATED if not outcome.reused or outcome.name_applied is not None else OperationEffect.NONE
    ):
        raise ValueError("work create success has an incompatible terminal receipt")
    return ModeloWorkCreateProjection(profile_id=private.profile_id, period=private.period, outcome=outcome)


def _bound_ports(factory: ActiveWorkLifecyclePortsFactory, profile_id: str) -> WorkLifecyclePorts:
    ports = factory()
    if ports.work_unit_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


class ModeloWorkCreateExecutor:
    """Use the existing readiness, selector, and atomic work writer in custody."""

    def __init__(self, factory: ActiveWorkLifecyclePortsFactory) -> None:
        """Retain composition's active-profile lifecycle factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkCreateRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Store a private success or bounded applicability refusal operand."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_WORK_CREATE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_WORK_CREATE_OPERATION_DEFINITION_ID)
        operation = context.authority_operation
        period = payload.period.to_period()

        def prepare() -> tuple[
            WorkLifecyclePorts, ModeloWorkProfile, ModeloWorkCreateRefusal | None, CCAA | None, tuple[str, ...]
        ]:
            locale_key = modelo_work_create_refusal_locale_key(payload.modelo)
            if locale_key is not None:
                raise WorkUnitMutationRefusedError(translated_message=locale_key, context={"modelo": payload.modelo})
            ports = _bound_ports(self._factory, profile_id)
            profile = load_modelo_work_profile(
                bucket_id=profile_id, profile_decode_context=operation.profile_decode_context()
            )
            if profile is None or str(profile.record.profile_id) != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            guard_active_profile_foral_ccaa(profile.record)
            applicability = modelo_work_create_applicability_refusal(
                payload.modelo,
                allow_not_applicable=payload.allow_not_applicable,
                record=profile.record,
                operation=operation,
            )
            if applicability is not None:
                return (
                    ports,
                    profile,
                    ModeloWorkCreateRefusal(modelo=applicability.modelo, reason=applicability.reason),
                    None,
                    (),
                )
            require_existing_profile_baseline_ready_for_modelo_work(
                bucket_id=profile_id,
                modelo=payload.modelo,
                filing_year=period.filing_year,
                period=period,
                enforce_applicability=not payload.allow_not_applicable,
                profile_decode_context=operation.profile_decode_context(),
                operation=operation,
                profile=profile,
            )
            revision = law_selected_revision_for_work_target(
                modelo=payload.modelo,
                filing_year=period.filing_year,
                period=period,
                requested_revision_id=payload.revision_id,
                operation=operation,
            )
            require_profile_ready_for_modelo_work(
                bucket_id=profile_id,
                modelo=payload.modelo,
                revision_id=revision,
                filing_year=period.filing_year,
                period=period,
                enforce_applicability=not payload.allow_not_applicable,
                profile_decode_context=operation.profile_decode_context(),
                operation=operation,
                profile=profile,
            )
            causante = parse_tax_region(payload.causante_ccaa) if payload.causante_ccaa is not None else None
            advisory_keys = (
                build_filing_obligation_advisories(
                    record_to_values(profile.record, schema=operation.profile_schema()),
                    filing_year=period.filing_year,
                    operation=operation,
                )
                if payload.modelo == "100"
                else ()
            )
            return ports, profile, None, causante, advisory_keys

        async def publish() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                ports, profile, refusal, causante, advisory_keys = await asyncio.to_thread(prepare)
                if refusal is not None:
                    detail = ModeloWorkCreateResult(
                        profile_id=payload.profile_id, period=payload.period, outcome=refusal
                    )
                    reference = await context.operands.put(detail, written_at=now())
                    await context.events.effect(OperationEffect.NONE)
                    return OperationRefusalEvidence(
                        refusal_code=MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE, detail_ref=reference
                    )
                await context.events.effect(OperationEffect.UNKNOWN)

                def ensure() -> ModeloWorkEnsureResult:
                    return ensure_modelo_work_unit_for_active_target(
                        bucket_id=profile_id,
                        modelo=payload.modelo,
                        filing_year=period.filing_year,
                        period=period,
                        registry_revision_id=payload.revision_id,
                        name=payload.name,
                        actor=payload.actor,
                        causante_ccaa=causante,
                        enforce_applicability=not payload.allow_not_applicable,
                        catalogue=ports.work_unit_repository.load(),
                        ports=ports,
                        operation=operation,
                        profile=profile,
                    )

                ensured = await asyncio.to_thread(ensure)
                await context.events.effect(
                    OperationEffect.UPDATED
                    if not ensured.reused or ensured.name_applied is not None
                    else OperationEffect.NONE
                )
                unit = ensured.work_unit
                if unit.bucket_id != profile_id or unit.period != period:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                outcome = ModeloWorkCreateSuccess(
                    unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
                    reused=ensured.reused,
                    name_applied=ensured.name_applied,
                    applicability_guard_bypassed=payload.allow_not_applicable,
                    advisory_keys=advisory_keys,
                )
                return await context.operands.put(
                    ModeloWorkCreateResult(profile_id=payload.profile_id, period=payload.period, outcome=outcome),
                    written_at=now(),
                )

        return await await_cancellation_complete(publish(), task_name="modelo-work-create-publication")


def build_modelo_work_create_definition(factory: ActiveWorkLifecyclePortsFactory) -> OperationDefinition:
    """Declare secure-reference create intent and one bounded refusal detail code."""
    return OperationDefinition(
        definition_id=MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkCreateRequest,
        result_type=ModeloWorkCreateResult,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkCreateRequest,
            executor_type=ModeloWorkCreateExecutor,
            build=lambda: ModeloWorkCreateExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        refusal_detail_codes=frozenset({MODELO_WORK_CREATE_APPLICABILITY_REFUSAL_CODE}),
    )


def build_modelo_work_create_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Authorize only the requested profile period and explicit COMMIT."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, ModeloWorkCreateRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = payload.period.to_period()
        admitted = context.admitted_request
        if (
            admitted is not None
            and context.action
            in {
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
            and (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or admitted.period_independent
                or admitted.periods != frozenset({period})
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return bind_operation_access_profile(
            context,
            COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=frozenset({period}),
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkCreateProjection,
        result_projector=project_modelo_work_create_result,
        access_resolver=resolve,
    )
