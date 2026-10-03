"""Registered exact-profile Modelo 100 taxation comparison."""

from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
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
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .taxation_comparison import (
    TaxationComparisonError,
    TaxationComparisonResult,
    TaxationRecommendation,
    compare_taxation_for_work_unit,
)
from .taxation_comparison_ports import TaxationComparisonPortsFactory

MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID = "modelo.work.compare_taxation"
_MAX_RESULT_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096
_WorkUnitId = Annotated[str, Field(pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$")]
_AmountText = Annotated[str, Field(min_length=1, max_length=128)]


class ModeloTaxationComparisonRequest(CredentialFreeOperationRequest):
    """Select one work unit inside the authenticated profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: _WorkUnitId


class ModeloTaxationComparisonProjection(BaseModel):
    """Bounded comparison with the single-earner scope caveat intact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    work_unit_id: _WorkUnitId
    filing_year: FilingYear
    modelo: Literal["100"]
    revision: Annotated[str, Field(min_length=1, max_length=128)]
    conjunta_cuota_resultante: _AmountText
    individual_cuota_resultante: _AmountText
    conjunta_resultado: _AmountText
    individual_resultado: _AmountText
    delta_resultado: _AmountText
    recommendation: TaxationRecommendation
    recommendation_reason: Annotated[str, Field(min_length=1, max_length=512)]
    individual_branch_single_earner_only: Literal[True]
    individual_branch_caveat: Annotated[str, Field(min_length=1, max_length=1_024)]

    @field_validator(
        "conjunta_cuota_resultante",
        "individual_cuota_resultante",
        "conjunta_resultado",
        "individual_resultado",
        "delta_resultado",
    )
    @classmethod
    def finite_amount(cls, value: str) -> str:
        """Keep result amounts finite and free of surrounding whitespace."""
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid taxation amount") from exc
        if value != value.strip() or not amount.is_finite():
            raise ValueError("invalid taxation amount")
        return value

    @classmethod
    def from_comparison(
        cls, comparison: TaxationComparisonResult, *, profile_id: UUID, work_unit_id: str
    ) -> ModeloTaxationComparisonProjection:
        """Copy only closed public fields from the application comparison."""
        if comparison.modelo != "100" or comparison.individual_branch_single_earner_only is not True:
            raise TaxationComparisonError("comparison has an unsupported filing scope")
        return cls(
            profile_id=profile_id,
            work_unit_id=work_unit_id,
            filing_year=comparison.filing_year,
            modelo="100",
            revision=comparison.revision,
            conjunta_cuota_resultante=str(comparison.conjunta_cuota_resultante),
            individual_cuota_resultante=str(comparison.individual_cuota_resultante),
            conjunta_resultado=str(comparison.conjunta_resultado),
            individual_resultado=str(comparison.individual_resultado),
            delta_resultado=str(comparison.delta_resultado),
            recommendation=comparison.recommendation,
            recommendation_reason=comparison.recommendation_reason,
            individual_branch_single_earner_only=True,
            individual_branch_caveat=comparison.individual_branch_caveat,
        )


class ModeloTaxationComparisonExecutor:
    """Read and calculate under the worker's exact profile and authority pin."""

    def __init__(self, factory: TaxationComparisonPortsFactory) -> None:
        """Capture the exact-profile port factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloTaxationComparisonRequest], context: OperationExecutorContext
    ) -> str:
        """Calculate the selected work unit in the active profile worker."""
        payload = request.payload
        if request.definition_id != MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID)

        def compare() -> ModeloTaxationComparisonProjection:
            result = compare_taxation_for_work_unit(
                payload.work_unit_id,
                bucket_id=str(payload.profile_id),
                ports=self._factory(bucket_id=str(payload.profile_id)),
                operation=context.authority_operation,
            )
            return ModeloTaxationComparisonProjection.from_comparison(
                result, profile_id=payload.profile_id, work_unit_id=payload.work_unit_id
            )

        async def capture() -> str:
            projection = await asyncio.to_thread(compare)
            if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-taxation-comparison")


def build_modelo_taxation_comparison_definition(factory: TaxationComparisonPortsFactory) -> OperationDefinition:
    """Declare a recorded, nonmutating, profile-bound calculation."""
    return OperationDefinition(
        definition_id=MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
        request_type=ModeloTaxationComparisonRequest,
        result_type=ModeloTaxationComparisonProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloTaxationComparisonRequest,
            executor_type=ModeloTaxationComparisonExecutor,
            build=lambda: ModeloTaxationComparisonExecutor(factory),
        ),
        phase_codes=(MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_modelo_taxation_comparison_registration(
    definition: OperationDefinition, factory: TaxationComparisonPortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Bind one selected work period and the result disclosure to the profile."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(
            payload, ModeloTaxationComparisonRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if context.authority_operation is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            ports = factory(bucket_id=str(payload.profile_id))
            unit = ports.work_unit_reader.load().get(payload.work_unit_id)
            if unit is None or unit.bucket_id != str(payload.profile_id) or unit.work_unit_id != payload.work_unit_id:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
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
        public_result_type=ModeloTaxationComparisonProjection,
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID",
    "ModeloTaxationComparisonExecutor",
    "ModeloTaxationComparisonProjection",
    "ModeloTaxationComparisonRequest",
    "build_modelo_taxation_comparison_definition",
    "build_modelo_taxation_comparison_registration",
]
