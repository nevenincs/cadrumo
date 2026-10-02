"""Exact-profile registered read of the complete local bucket event history."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import UtcInstant
from ...domain.buckets.event import BucketEventType, bucket_event_order_key
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
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
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from .access_errors import ProfileAccessRefusedError

PROFILE_HISTORY_OPERATION_DEFINITION_ID = "profile.history"
_FilterValue = Annotated[str, Field(min_length=1, max_length=4096)]


class ProfileHistoryRequest(BaseModel):
    """An explicit profile target and the existing CLI's inclusive history filters."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    event_types: tuple[BucketEventType, ...] | None = None
    since: UtcInstant | None = None
    until: UtcInstant | None = None
    object_id: _FilterValue | None = None
    actor: _FilterValue | None = None

    @model_validator(mode="after")
    def _valid_range(self) -> Self:
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError("profile history since is after until")
        return self


class ProfileHistoryProjection(BaseModel):
    """Every canonical event field and the exact filters used to select it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    event_types: tuple[BucketEventType, ...] | None = None
    since: UtcInstant | None = None
    until: UtcInstant | None = None
    object_id: _FilterValue | None = None
    actor: _FilterValue | None = None
    event_count: int = Field(ge=0)
    events: tuple[BucketEventProjection, ...]

    @model_validator(mode="after")
    def _exact_filtered_history(self) -> Self:
        if self.since is not None and self.until is not None and self.since > self.until:
            raise ValueError("profile history since is after until")
        if self.event_count != len(self.events) or len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("profile history count or event identities differ")
        if tuple(sorted(self.events, key=lambda event: bucket_event_order_key(event.to_event()))) != self.events:
            raise ValueError("profile history events are not in canonical order")
        for event in self.events:
            if (
                event.bucket_id != self.profile_id
                or (self.event_types is not None and event.event_type not in self.event_types)
                or (self.since is not None and event.occurred_at < self.since)
                or (self.until is not None and event.occurred_at > self.until)
                or (self.object_id is not None and event.object_id != self.object_id)
                or (self.actor is not None and event.actor != self.actor)
            ):
                raise ValueError("profile history event does not match its profile or filters")
        return self


class ProfileHistoryExecutionResult(BaseModel):
    """Private encrypted operand retained until the current result release."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ProfileHistoryProjection


@dataclass(frozen=True, slots=True)
class ProfileHistoryReadPorts:
    """Repository identity and retained authority pin for one profile worker."""

    bucket_id: str
    operation: PinnedAuthorityOperation
    event_repository: BucketEventHistoryRepositoryProtocol


class ProfileHistoryReadPortsFactory(Protocol):
    """Build one pinned profile history reader from an explicit bucket identity."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> ProfileHistoryReadPorts:
        """Return the bound repository without consulting an ambient selection."""
        ...


def project_profile_history_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only an exact profile's successful, effect-free history capture."""
    if type(result) is not ProfileHistoryExecutionResult:
        raise ValueError("invalid private profile history result")
    projection = result.projection
    if (
        receipt.identity.definition_id != PROFILE_HISTORY_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("profile history result differs from its terminal receipt")
    return projection


class ProfileHistoryExecutor:
    """Capture the current encrypted event catalogue under an exact profile pin."""

    def __init__(self, factory: ProfileHistoryReadPortsFactory) -> None:
        """Retain the composition-owned exact-profile reader factory."""
        self._factory = factory

    async def execute(self, request: OperationRequest[ProfileHistoryRequest], context: OperationExecutorContext) -> str:
        """Store one complete filtered snapshot and record a NONE effect."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if (
            request.definition_id != PROFILE_HISTORY_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(PROFILE_HISTORY_OPERATION_DEFINITION_ID)

        def read() -> ProfileHistoryExecutionResult:
            operation = context.authority_operation
            ports = self._factory(bucket_id=bucket_id, operation=operation)
            if ports.bucket_id != bucket_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            events = tuple(
                event
                for event in ports.event_repository.load().for_bucket(bucket_id, event_types=payload.event_types)
                if (payload.since is None or event.occurred_at >= payload.since)
                and (payload.until is None or event.occurred_at <= payload.until)
                and (payload.object_id is None or event.object_id == payload.object_id)
                and (payload.actor is None or event.actor == payload.actor)
            )
            return ProfileHistoryExecutionResult(
                projection=ProfileHistoryProjection(
                    profile_id=payload.profile_id,
                    event_types=payload.event_types,
                    since=payload.since,
                    until=payload.until,
                    object_id=payload.object_id,
                    actor=payload.actor,
                    event_count=len(events),
                    events=tuple(BucketEventProjection.from_event(event) for event in events),
                )
            )

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name=PROFILE_HISTORY_OPERATION_DEFINITION_ID)


def build_profile_history_definition(factory: ProfileHistoryReadPortsFactory) -> OperationDefinition:
    """Declare a CLI-only read of all periods without COMMIT or provider effects."""
    return OperationDefinition(
        definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID,
        request_type=ProfileHistoryRequest,
        result_type=ProfileHistoryExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=ProfileHistoryRequest,
            executor_type=ProfileHistoryExecutor,
            build=lambda: ProfileHistoryExecutor(factory),
        ),
        phase_codes=(PROFILE_HISTORY_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_profile_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict public schemas to exact-profile whole-history admission."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=ProfileHistoryRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=ProfileHistoryProjection
        ),
        result_projector=project_profile_history_result,
        access_resolver=resolve_profile_history_access,
    )


def resolve_profile_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require one profile, all periods, and result disclosure to this destination."""
    payload = request.payload
    if request.definition_id != PROFILE_HISTORY_OPERATION_DEFINITION_ID or type(payload) is not ProfileHistoryRequest:
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
            or admitted.destination_id != context.destination_id
            or admitted.action is not AccessAction.SUBMIT
            or admitted.periods
            or not admitted.period_independent
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
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
            DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=schema.schema_id,
                category=category,
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
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
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


__all__ = [
    "PROFILE_HISTORY_OPERATION_DEFINITION_ID",
    "ProfileHistoryExecutionResult",
    "ProfileHistoryExecutor",
    "ProfileHistoryProjection",
    "ProfileHistoryReadPorts",
    "ProfileHistoryReadPortsFactory",
    "ProfileHistoryRequest",
    "build_profile_history_definition",
    "build_profile_history_registration",
    "project_profile_history_result",
    "resolve_profile_history_access",
]
