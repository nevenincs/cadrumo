"""Registered exact-profile Modelo 100 taxation comparison."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.projection_pages import PROJECTION_RESULT_MAX_BYTES

from ...core.async_cleanup import await_cancellation_complete
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.i18n.render import output_language
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.modelos.codes import ModeloCodeText
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
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_action_ports import CalculationActionPortsFactory
from .taxation_comparison import (
    TaxationComparisonRefusal,
    TaxationComparisonResult,
    TaxationRecommendation,
    TaxationRecommendationReason,
    compare_taxation_for_work_unit,
    taxation_comparison_refusal,
)
from .taxation_comparison_ports import TaxationComparisonPortsFactory
from .taxation_comparison_words import individual_branch_caveat_words, recommendation_reason_words

MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID = "modelo.work.compare_taxation"
_WorkUnitId = Annotated[str, Field(pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$")]
_AmountText = Annotated[str, Field(min_length=1, max_length=128)]
_REASON_OF_RECOMMENDATION: Final[Mapping[TaxationRecommendation, TaxationRecommendationReason]] = MappingProxyType(
    {
        TaxationRecommendation.CONJUNTA: TaxationRecommendationReason.CONJUNTA_LOWER_RESULT,
        TaxationRecommendation.INDIVIDUAL: TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT,
        TaxationRecommendation.INDIFFERENT: TaxationRecommendationReason.BELOW_MATERIALITY,
    }
)


class ModeloTaxationComparisonRequest(CredentialFreeOperationRequest):
    """Select one work unit inside the authenticated profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: _WorkUnitId


class ModeloTaxationComparisonProjection(BaseModel):
    """Bounded comparison with the single-earner scope caveat intact.

    ``recommendation_reason`` is the closed token of why the mode is
    recommended; ``recommendation_reason_words`` is the same reason in words
    naming the results it compares, in ``words_language``;
    ``individual_branch_caveat`` states in the same language why the individual
    figure is reliable only for a single-earner household.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[2] = 2
    profile_id: UUID
    work_unit_id: _WorkUnitId
    filing_year: FilingYear
    modelo: ModeloCodeText
    revision: Annotated[str, Field(min_length=1, max_length=128)]
    conjunta_cuota_resultante: _AmountText
    individual_cuota_resultante: _AmountText
    conjunta_resultado: _AmountText
    individual_resultado: _AmountText
    delta_resultado: _AmountText
    recommendation: TaxationRecommendation
    recommendation_reason: TaxationRecommendationReason
    recommendation_reason_words: Annotated[str, Field(min_length=1, max_length=512)]
    words_language: OutputLanguage
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

    @model_validator(mode="after")
    def _reason_matches_recommendation(self) -> ModeloTaxationComparisonProjection:
        if _REASON_OF_RECOMMENDATION[self.recommendation] is not self.recommendation_reason:
            raise ValueError("taxation comparison reason does not belong to its recommendation")
        return self

    @classmethod
    def from_comparison(
        cls, comparison: TaxationComparisonResult, *, profile_id: UUID, work_unit_id: str
    ) -> ModeloTaxationComparisonProjection:
        """Copy only closed public fields from the application comparison."""
        if (
            comparison.modelo != form_for_role("renta.annual")
            or comparison.individual_branch_single_earner_only is not True
        ):
            raise taxation_comparison_refusal(TaxationComparisonRefusal.NOT_DECLARED)
        language = OutputLanguage(output_language())
        return cls(
            profile_id=profile_id,
            work_unit_id=work_unit_id,
            filing_year=comparison.filing_year,
            modelo=comparison.modelo,
            revision=comparison.revision,
            conjunta_cuota_resultante=str(comparison.conjunta_cuota_resultante),
            individual_cuota_resultante=str(comparison.individual_cuota_resultante),
            conjunta_resultado=str(comparison.conjunta_resultado),
            individual_resultado=str(comparison.individual_resultado),
            delta_resultado=str(comparison.delta_resultado),
            recommendation=comparison.recommendation,
            recommendation_reason=comparison.recommendation_reason,
            recommendation_reason_words=recommendation_reason_words(
                comparison.recommendation_reason,
                conjunta_resultado=comparison.conjunta_resultado,
                individual_resultado=comparison.individual_resultado,
                delta_resultado=comparison.delta_resultado,
                language=language,
            ),
            words_language=language,
            individual_branch_single_earner_only=True,
            individual_branch_caveat=individual_branch_caveat_words(language),
        )


class ModeloTaxationComparisonExecutor:
    """Evaluate both filing modes under the worker's exact profile and authority pin, saving nothing."""

    def __init__(self, calculation_action_ports_factory: CalculationActionPortsFactory) -> None:
        """Capture the exact-profile calculation port factory."""
        self._calculation_action_ports_factory = calculation_action_ports_factory

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
                ports=self._calculation_action_ports_factory(
                    bucket_id=str(payload.profile_id), operation=context.authority_operation
                ),
            )
            return ModeloTaxationComparisonProjection.from_comparison(
                result, profile_id=payload.profile_id, work_unit_id=payload.work_unit_id
            )

        async def capture() -> str:
            projection = await asyncio.to_thread(compare)
            if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_RESULT_MAX_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-taxation-comparison")


def build_modelo_taxation_comparison_definition(
    calculation_action_ports_factory: CalculationActionPortsFactory,
) -> OperationDefinition:
    """Declare a recorded, nonmutating, profile-bound calculation."""
    return build_single_phase_definition(
        definition_id=MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID,
        request_type=ModeloTaxationComparisonRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=ModeloTaxationComparisonProjection,
        executor_type=ModeloTaxationComparisonExecutor,
        build=lambda: ModeloTaxationComparisonExecutor(calculation_action_ports_factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def build_modelo_taxation_comparison_registration(
    definition: OperationDefinition, factory: TaxationComparisonPortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Bind one selected work period and the result disclosure to the profile."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = _require_taxation_comparison_request(request, context, definition)
        periods = _taxation_comparison_periods(request, context, payload, factory)

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


def _require_taxation_comparison_request(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    definition: OperationDefinition,
) -> ModeloTaxationComparisonRequest:
    payload = request.payload
    if request.definition_id != definition.definition_id or not isinstance(payload, ModeloTaxationComparisonRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def _taxation_comparison_periods(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    payload: ModeloTaxationComparisonRequest,
    factory: TaxationComparisonPortsFactory,
) -> frozenset[Period]:
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        return require_single_period_admission(
            admitted, profile_id=context.profile_id, definition_id=request.definition_id
        )
    ports = factory(bucket_id=str(payload.profile_id))
    unit = ports.work_unit_reader.load().get(payload.work_unit_id)
    if unit is None or unit.bucket_id != str(payload.profile_id) or unit.work_unit_id != payload.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return frozenset({unit.period})


__all__ = [
    "MODELO_TAXATION_COMPARISON_OPERATION_DEFINITION_ID",
    "ModeloTaxationComparisonExecutor",
    "ModeloTaxationComparisonProjection",
    "ModeloTaxationComparisonRequest",
    "build_modelo_taxation_comparison_definition",
    "build_modelo_taxation_comparison_registration",
]
