"""Agent-safe Modelo lifecycle timeline over the canonical encrypted history."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import replace
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
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
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import BucketEvent, BucketEventType
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
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
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, DisclosureCategory, DisclosurePermission
from ..user_profile.access_errors import ProfileAccessRefusedError
from .history import assemble_modelo_lifecycle_history
from .history_ports import ModeloHistoryPortsFactory

MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID = "modelo.history.timeline"


class ModeloHistoryTimelineRequest(CredentialFreeOperationRequest):
    """Select one profile's Modelo timeline with optional canonical filters."""

    profile_id: UUID
    modelo: str = Field(min_length=1, max_length=16)
    year: int | None = Field(default=None, ge=1900, le=9999)
    period: str | None = Field(default=None, min_length=1, max_length=32)


class ModeloTimelineEvent(BaseModel):
    """A verified event identity, kind and instant without private payload text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    event_id: Hex64Str
    event_type: BucketEventType
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    @pydantic_validation_boundary
    def _occurred_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _modelo_lifecycle_kind(self) -> Self:
        if not self.event_type.name.startswith("MODELO_"):
            raise ValueError("timeline event kind is outside the Modelo lifecycle")
        return self

    @classmethod
    def from_event(cls, event: BucketEvent) -> Self:
        """Use only canonical event metadata; keep actor and details in custody."""
        return cls(event_id=event.event_id, event_type=event.event_type, occurred_at=event.occurred_at)


class ModeloHistoryTimelineProjection(BaseModel):
    """Closed agent result preserving full event count and canonical order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    modelo: str = Field(min_length=1, max_length=16)
    year: int | None = Field(default=None, ge=1900, le=9999)
    period: str | None = Field(default=None, min_length=1, max_length=32)
    count: int = Field(ge=0)
    events: tuple[ModeloTimelineEvent, ...]

    @model_validator(mode="after")
    def _complete_ordered_timeline(self) -> Self:
        if self.count != len(self.events) or len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("timeline count or event identity mismatch")
        if tuple(sorted(self.events, key=lambda event: (event.occurred_at, event.event_id))) != self.events:
            raise ValueError("timeline is not canonically ordered")
        return self


class ModeloHistoryTimelineExecutor:
    """Read the existing lifecycle history and store only its approved summary."""

    def __init__(self, factory: ModeloHistoryPortsFactory) -> None:
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloHistoryTimelineRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        subject = profile_operation_subject(str(payload.profile_id))
        if (
            request.definition_id != MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID)

        def read() -> ModeloHistoryTimelineProjection:
            bucket_id = str(payload.profile_id)
            ports = self._factory(bucket_id=bucket_id, operation=context.authority_operation)
            for repository in (
                ports.work_unit_repository,
                ports.calculation_repository,
                ports.verification_repository,
                ports.filing_repository,
            ):
                if repository.bucket_id != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            history = assemble_modelo_lifecycle_history(
                payload.modelo, filing_year=payload.year, period=payload.period, ports=ports
            )
            return ModeloHistoryTimelineProjection(
                profile_id=payload.profile_id,
                modelo=str(history.modelo),
                year=history.filing_year,
                period=history.period,
                count=len(history.events),
                events=tuple(ModeloTimelineEvent.from_event(event) for event in history.events),
            )

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-history-timeline")


def build_modelo_history_timeline_definition(factory: ModeloHistoryPortsFactory) -> OperationDefinition:
    """Declare a metadata-only agent timeline with no domain write capability."""
    return OperationDefinition(
        definition_id=MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
        request_type=ModeloHistoryTimelineRequest,
        result_type=ModeloHistoryTimelineProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloHistoryTimelineRequest,
            executor_type=ModeloHistoryTimelineExecutor,
            build=lambda: ModeloHistoryTimelineExecutor(factory),
        ),
        phase_codes=(MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,),
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
        permitted_frontends=frozenset({OperationFrontendProjection.MCP}),
    )


def build_modelo_history_timeline_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require exact profile/period authority and metadata disclosure at release."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if (
            request.definition_id != MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID
            or type(payload) is not ModeloHistoryTimelineRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if not isinstance(payload, ModeloHistoryTimelineRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        periods = frozenset[Period]()
        if payload.year is not None and payload.period is not None:
            with suppress(PeriodError):
                # Censal period selectors can filter history without denoting a tax period.
                periods = frozenset({Period.from_year_and_code(payload.year, payload.period)})
        resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=periods)
        if context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            resolved = replace(
                resolved,
                policy=resolved.policy.model_copy(
                    update={
                        "disclosures": frozenset(
                            (
                                DisclosurePermission(
                                    destination_id=context.destination_id,
                                    projection_id=schema.schema_id,
                                    category=DisclosureCategory.OPERATION_METADATA,
                                ),
                            )
                        )
                    }
                ),
            )
        return resolved

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ModeloHistoryTimelineRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ModeloHistoryTimelineProjection
        ),
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID",
    "ModeloHistoryTimelineProjection",
    "ModeloHistoryTimelineRequest",
    "ModeloTimelineEvent",
    "build_modelo_history_timeline_definition",
    "build_modelo_history_timeline_registration",
]
