"""Agent-safe Modelo lifecycle timeline over the canonical encrypted history."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import replace
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period, PeriodError
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import BucketEvent, BucketEventType
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_payload, require_operation_profile
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
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
    authority_generation: ContentDigest
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
        if request.definition_id != MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
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
                authority_generation=context.authority_operation.generation.logical_generation,
                profile_id=payload.profile_id,
                modelo=str(history.modelo),
                year=history.filing_year,
                period=history.period,
                count=len(history.events),
                events=tuple(ModeloTimelineEvent.from_event(event) for event in history.events),
            )

        return await capture_read_result(context, read, task_name="modelo-history-timeline")


def build_modelo_history_timeline_definition(factory: ModeloHistoryPortsFactory) -> OperationDefinition:
    """Declare a metadata-only agent timeline with no domain write capability."""
    return build_single_phase_definition(
        definition_id=MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
        request_type=ModeloHistoryTimelineRequest,
        result_type=ModeloHistoryTimelineProjection,
        executor_type=ModeloHistoryTimelineExecutor,
        build=lambda: ModeloHistoryTimelineExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.MCP}),
    )


def build_modelo_history_timeline_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require exact profile/period authority and metadata disclosure at release."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = require_access_request_payload(
            request,
            definition_id=MODELO_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
            payload_type=ModeloHistoryTimelineRequest,
            exact_type=True,
        )
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

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloHistoryTimelineProjection,
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
