"""Registered, exact-profile read of one modelo's complete event history."""

from __future__ import annotations

import asyncio
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.period import Period, PeriodError
from ...core.time.clock import now
from ...domain.buckets.event import bucket_event_order_key
from ..bucket_event_projection import BucketEventProjection
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
        from ...core.bucket_pointer import require_active_bucket_id

        payload = request.payload
        if (
            request.definition_id != MODELO_HISTORY_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
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

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-lifecycle-history")


def build_modelo_history_definition(factory: ModeloHistoryPortsFactory) -> OperationDefinition:
    """Declare a recorded, encrypted, nonmutating modelo history read."""
    return OperationDefinition(
        definition_id=MODELO_HISTORY_OPERATION_DEFINITION_ID,
        request_type=ModeloHistoryOperationRequest,
        result_type=ModeloHistoryOperationProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloHistoryOperationRequest,
            executor_type=ModeloHistoryExecutor,
            build=lambda: ModeloHistoryExecutor(factory),
        ),
        phase_codes=(MODELO_HISTORY_OPERATION_DEFINITION_ID,),
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


def build_modelo_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Require exact profile and truthful period scope through every release."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if (
            request.definition_id != MODELO_HISTORY_OPERATION_DEFINITION_ID
            or type(payload) is not ModeloHistoryOperationRequest
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
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
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
        disclosure = None
        if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
            disclosure = DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                category=DisclosureCategory.OPERATION_METADATA,
            )
        elif context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            disclosure = DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=schema.schema_id,
                category=DisclosureCategory.TAX_VALUES,
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
                disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
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
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ModeloHistoryOperationRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloHistoryOperationProjection,
        ),
        access_resolver=resolve,
    )
