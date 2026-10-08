"""Registered, exact-profile read of one modelo's complete event history."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period, PeriodError
from ...domain.buckets.event import bucket_event_order_key
from ..bucket_event_projection import BucketEventProjection
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_admitted_submission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .history import assemble_modelo_lifecycle_history
from .history_ports import ModeloHistoryPortsFactory

MODELO_HISTORY_OPERATION_DEFINITION_ID = "modelo.history"


class ModeloHistoryOperationRequest(CredentialFreeOperationRequest):
    """Address one modelo in a bound profile, optionally refining its history."""

    profile_id: UUID
    modelo: str = Field(min_length=1, max_length=16)
    year: int | None = Field(default=None, ge=1900, le=9999)
    period: str | None = Field(default=None, min_length=1, max_length=32)


class ModeloHistoryOperationProjection(BaseModel):
    """Carry every canonical event field, including ordered payload details."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    modelo: str = Field(min_length=1, max_length=16)
    year: int | None = Field(default=None, ge=1900, le=9999)
    period: str | None = Field(default=None, min_length=1, max_length=32)
    count: int = Field(ge=0)
    events: tuple[BucketEventProjection, ...]

    @model_validator(mode="after")
    def _bound_ordered_history(self) -> Self:
        if self.count != len(self.events) or any(event.bucket_id != self.profile_id for event in self.events):
            raise ValueError("modelo history count or profile mismatch")
        if len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("modelo history repeats an event")
        if tuple(sorted(self.events, key=lambda event: bucket_event_order_key(event.to_event()))) != self.events:
            raise ValueError("modelo history is not canonically ordered")
        return self


class ModeloHistoryExecutor:
    """Capture the canonical event read under the retained authority pin."""

    def __init__(self, factory: ModeloHistoryPortsFactory) -> None:
        """Retain only the outer profile-bound history factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloHistoryOperationRequest], context: OperationExecutorContext
    ) -> str:
        """Capture the complete filtered event history without a repository write."""
        payload = request.payload
        if request.definition_id != MODELO_HISTORY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_HISTORY_OPERATION_DEFINITION_ID)

        def read() -> ModeloHistoryOperationProjection:
            ports = self._factory(bucket_id=str(payload.profile_id), operation=context.authority_operation)
            for repository in (
                ports.work_unit_repository,
                ports.calculation_repository,
                ports.verification_repository,
                ports.filing_repository,
            ):
                if repository.bucket_id != str(payload.profile_id):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            history = assemble_modelo_lifecycle_history(
                payload.modelo, filing_year=payload.year, period=payload.period, ports=ports
            )
            return ModeloHistoryOperationProjection(
                profile_id=payload.profile_id,
                modelo=str(history.modelo),
                year=history.filing_year,
                period=history.period,
                count=len(history.events),
                events=tuple(BucketEventProjection.from_event(event) for event in history.events),
            )

        return await capture_read_result(context, read, task_name="modelo-lifecycle-history")


def build_modelo_history_definition(factory: ModeloHistoryPortsFactory) -> OperationDefinition:
    """Declare a recorded, encrypted, nonmutating modelo history read."""
    return build_single_phase_definition(
        definition_id=MODELO_HISTORY_OPERATION_DEFINITION_ID,
        request_type=ModeloHistoryOperationRequest,
        result_type=ModeloHistoryOperationProjection,
        executor_type=ModeloHistoryExecutor,
        build=lambda: ModeloHistoryExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _validated_history_access_payload(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> ModeloHistoryOperationRequest:
    return require_access_request_profile_payload(
        request,
        definition_id=MODELO_HISTORY_OPERATION_DEFINITION_ID,
        payload_type=ModeloHistoryOperationRequest,
        access_profile_id=context.profile_id,
    )


def _resolve_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    payload = _validated_history_access_payload(request, context)
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        require_admitted_submission(admitted, profile_id=context.profile_id, definition_id=request.definition_id)
        periods, independent = admitted.periods, admitted.period_independent
    else:
        if context.authority_operation is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        periods, independent = frozenset[Period](), True
        if payload.year is not None and payload.period is not None:
            try:
                periods = frozenset({Period.from_year_and_code(payload.year, payload.period)})
            except PeriodError:
                # Censo lifecycle selectors such as ``alta`` are valid
                # history filters, yet do not identify a filing period.
                pass
            else:
                independent = False
    return bind_operation_access_profile(
        context,
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS
        if independent
        else LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=periods,
    )


def build_modelo_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Require exact profile and truthful period scope through every release."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloHistoryOperationProjection,
        access_resolver=_resolve_history_access,
    )
