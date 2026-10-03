"""Registered, exact-profile reads of a canonical work-unit event history."""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, model_validator

from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.buckets.event import bucket_event_order_key
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.work_unit import WorkUnit
from ..bucket_event_projection import BucketEventProjection
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
from .history import WorkUnitHistory, assemble_work_unit_history
from .history_ports import ModeloHistoryPorts, ModeloHistoryPortsFactory

MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID = "modelo.work.history"


class ModeloWorkHistoryRequest(CredentialFreeOperationRequest):
    """Address one full work identity in the authenticated profile."""

    profile_id: UUID
    work_unit_id: WorkUnitId


class ModeloWorkHistorySnapshot(BaseModel):
    """Closed transport fields that reconstruct the canonical history losslessly."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    bucket_id: BucketId
    work_unit_id: WorkUnitId
    events: tuple[BucketEventProjection, ...]

    @classmethod
    def from_history(cls, history: WorkUnitHistory) -> ModeloWorkHistorySnapshot:
        """Copy each canonical event using the shared validated projection."""
        return cls(
            bucket_id=history.bucket_id,
            work_unit_id=history.work_unit_id,
            events=tuple(BucketEventProjection.from_event(event) for event in history.events),
        )

    def to_history(self) -> WorkUnitHistory:
        """Reconstruct the domain-validated read result for existing presentation."""
        return WorkUnitHistory(
            bucket_id=self.bucket_id,
            work_unit_id=self.work_unit_id,
            events=tuple(event.to_event() for event in self.events),
        )


class ModeloWorkHistoryProjection(BaseModel):
    """Retain canonical event constraints within an encrypted profile result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    history: ModeloWorkHistorySnapshot

    @model_validator(mode="after")
    def _bound_history(self) -> Self:
        if self.history.bucket_id != str(self.profile_id) or any(
            str(event.bucket_id) != self.history.bucket_id for event in self.history.events
        ):
            raise ValueError("work history contains another profile")
        if len({event.event_id for event in self.history.events}) != len(self.history.events):
            raise ValueError("work history repeats an event")
        if (
            tuple(sorted(self.history.events, key=lambda event: bucket_event_order_key(event.to_event())))
            != self.history.events
        ):
            raise ValueError("work history is not chronologically ordered")
        return self


def _bound_ports(
    payload: ModeloWorkHistoryRequest, factory: ModeloHistoryPortsFactory, *, operation: PinnedAuthorityOperation
) -> ModeloHistoryPorts:
    ports = factory(bucket_id=str(payload.profile_id), operation=operation)
    if any(
        repository.bucket_id != str(payload.profile_id)
        for repository in (
            ports.work_unit_repository,
            ports.calculation_repository,
            ports.verification_repository,
            ports.filing_repository,
        )
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _read_unit(payload: ModeloWorkHistoryRequest, ports: ModeloHistoryPorts) -> WorkUnit:
    unit = ports.work_unit_repository.load().get(payload.work_unit_id)
    if unit is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if unit.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


class ModeloWorkHistoryExecutor:
    """Capture the canonical event aggregate without a competing history store."""

    def __init__(self, factory: ModeloHistoryPortsFactory) -> None:
        """Retain only the composition-owned profile repository factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkHistoryRequest], context: OperationExecutorContext
    ) -> str:
        """Read under the retained authority pin and store the encrypted result."""
        payload = request.payload
        if request.definition_id != MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id, expected_subject_ref=payload.work_unit_id)
        await context.events.phase(MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID)

        def read() -> ModeloWorkHistoryProjection:
            ports = _bound_ports(payload, self._factory, operation=context.authority_operation)
            _read_unit(payload, ports)
            history = assemble_work_unit_history(
                payload.work_unit_id, ports=ports, operation=context.authority_operation
            )
            if history.work_unit_id != payload.work_unit_id:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return ModeloWorkHistoryProjection(
                profile_id=payload.profile_id, history=ModeloWorkHistorySnapshot.from_history(history)
            )

        return await capture_read_result(context, read, task_name="modelo-work-history")


def build_modelo_work_history_definition(factory: ModeloHistoryPortsFactory) -> OperationDefinition:
    """Declare recorded, encrypted, nonmutating work history."""
    return OperationDefinition(
        definition_id=MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkHistoryRequest,
        result_type=ModeloWorkHistoryProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkHistoryRequest,
            executor_type=ModeloWorkHistoryExecutor,
            build=lambda: ModeloWorkHistoryExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_history_registration(
    definition: OperationDefinition, factory: ModeloHistoryPortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Authorize the stored work period and retain its sealed disclosure scope."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID or not isinstance(
            payload, ModeloWorkHistoryRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != payload.work_unit_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            ports = _bound_ports(payload, factory, operation=context.authority_operation)
            periods = frozenset({_read_unit(payload, ports).period})
        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkHistoryProjection,
        access_resolver=resolve,
    )
