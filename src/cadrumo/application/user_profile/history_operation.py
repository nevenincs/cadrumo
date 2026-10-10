"""Exact-profile registered reads of the complete local bucket event history.

The history is the person's read. The timeline is the agent-facing read of the
same events: it shares the history's reader and admission, and its result
leaves each event's payload in custody.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.buckets.event import BucketEvent
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..bucket_event_projection import BucketEventProjection
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    OBSERVATION_DISCLOSING_ACTIONS,
    OPERATION_LIFECYCLE_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
    require_period_independent_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
)
from .access_contracts import AccessDenialCode, Availability, DisclosureCategory
from .access_errors import ProfileAccessRefusedError
from .history_contracts import (
    ProfileHistoryExecutionResult,
    ProfileHistoryProjection,
    ProfileHistoryRequest,
    ProfileHistoryTimelineExecutionResult,
    ProfileHistoryTimelineProjection,
    ProfileTimelineEvent,
    event_matches_profile_history_request,
)

PROFILE_HISTORY_OPERATION_DEFINITION_ID = "profile.history"
PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID = "profile.history.timeline"


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


def _selected_profile_events(
    factory: ProfileHistoryReadPortsFactory,
    payload: ProfileHistoryRequest,
    operation: PinnedAuthorityOperation,
) -> tuple[BucketEvent, ...]:
    """Load and filter the exact bucket's complete history under the pinned authority."""
    bucket_id = str(payload.profile_id)
    ports = factory(bucket_id=bucket_id, operation=operation)
    if ports.bucket_id != bucket_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return tuple(
        event
        for event in ports.event_repository.load().for_bucket(bucket_id, event_types=payload.event_types)
        if event_matches_profile_history_request(event, payload)
    )


def _read_profile_history(
    factory: ProfileHistoryReadPortsFactory,
    payload: ProfileHistoryRequest,
    operation: PinnedAuthorityOperation,
) -> ProfileHistoryExecutionResult:
    """Project every selected event with its complete payload."""
    events = _selected_profile_events(factory, payload, operation)
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


def _read_profile_history_timeline(
    factory: ProfileHistoryReadPortsFactory,
    payload: ProfileHistoryRequest,
    operation: PinnedAuthorityOperation,
) -> ProfileHistoryTimelineExecutionResult:
    """Project every selected event's declared facts; its payload never enters the result."""
    events = _selected_profile_events(factory, payload, operation)
    return ProfileHistoryTimelineExecutionResult(
        projection=ProfileHistoryTimelineProjection(
            profile_id=payload.profile_id,
            event_types=payload.event_types,
            since=payload.since,
            until=payload.until,
            object_id=payload.object_id,
            actor=payload.actor,
            event_count=len(events),
            events=tuple(ProfileTimelineEvent.from_event(event) for event in events),
        )
    )


def project_profile_history_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only an exact profile's successful, effect-free history capture."""
    if type(result) is not ProfileHistoryExecutionResult:
        raise ValueError("invalid private profile history result")
    projection = result.projection
    require_terminal_receipt_match(
        receipt,
        definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message="profile history result differs from its terminal receipt",
    )
    return projection


def project_profile_history_timeline_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only an exact profile's successful, effect-free timeline capture."""
    if type(result) is not ProfileHistoryTimelineExecutionResult:
        raise ValueError("invalid private profile timeline result")
    projection = result.projection
    require_terminal_receipt_match(
        receipt,
        definition_id=PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message="profile timeline result differs from its terminal receipt",
    )
    return projection


class ProfileHistoryExecutor:
    """Capture the current encrypted event catalogue under an exact profile pin."""

    def __init__(self, factory: ProfileHistoryReadPortsFactory) -> None:
        """Retain the composition-owned exact-profile reader factory."""
        self._factory = factory

    async def execute(self, request: OperationRequest[ProfileHistoryRequest], context: OperationExecutorContext) -> str:
        """Store one complete filtered snapshot and record a NONE effect."""
        payload = request.payload
        if request.definition_id != PROFILE_HISTORY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(PROFILE_HISTORY_OPERATION_DEFINITION_ID)

        def read() -> ProfileHistoryExecutionResult:
            return _read_profile_history(self._factory, payload, context.authority_operation)

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name=PROFILE_HISTORY_OPERATION_DEFINITION_ID)


class ProfileHistoryTimelineExecutor:
    """Capture the same event catalogue as the history, retaining no event payload."""

    def __init__(self, factory: ProfileHistoryReadPortsFactory) -> None:
        """Retain the composition-owned exact-profile reader factory."""
        self._factory = factory

    async def execute(self, request: OperationRequest[ProfileHistoryRequest], context: OperationExecutorContext) -> str:
        """Store one complete filtered timeline and record a NONE effect."""
        payload = request.payload
        if request.definition_id != PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID)

        def read() -> ProfileHistoryTimelineExecutionResult:
            return _read_profile_history_timeline(self._factory, payload, context.authority_operation)

        async def capture() -> str:
            result = await asyncio.to_thread(read)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name=PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID)


def build_profile_history_definition(factory: ProfileHistoryReadPortsFactory) -> OperationDefinition:
    """Declare a CLI-only read of all periods without COMMIT or provider effects."""
    return build_single_phase_definition(
        definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID,
        request_type=ProfileHistoryRequest,
        result_type=ProfileHistoryExecutionResult,
        executor_type=ProfileHistoryExecutor,
        build=lambda: ProfileHistoryExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_profile_history_timeline_definition(factory: ProfileHistoryReadPortsFactory) -> OperationDefinition:
    """Declare the agent-only read of the same events, without COMMIT or provider effects."""
    return build_single_phase_definition(
        definition_id=PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID,
        request_type=ProfileHistoryRequest,
        result_type=ProfileHistoryTimelineExecutionResult,
        executor_type=ProfileHistoryTimelineExecutor,
        build=lambda: ProfileHistoryTimelineExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.MCP}),
    )


def build_profile_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict public schemas to exact-profile whole-history admission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ProfileHistoryProjection,
        result_projector=project_profile_history_result,
        access_resolver=resolve_profile_history_access,
    )


def build_profile_history_timeline_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the timeline's strict public schemas to the history's whole-profile admission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ProfileHistoryTimelineProjection,
        result_projector=project_profile_history_timeline_result,
        access_resolver=resolve_profile_history_timeline_access,
    )


def resolve_profile_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require one profile, all periods, and result disclosure to this destination."""
    return _resolve_history_read_access(request, context, definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID)


def resolve_profile_history_timeline_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit the timeline as the history is admitted, on the agent frontend alone."""
    if context.frontend is not OperationFrontendProjection.MCP:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    return _resolve_history_read_access(
        request, context, definition_id=PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID
    )


def _resolve_history_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, *, definition_id: str
) -> ResolvedOperationAccess:
    _validated_profile_history_request(request, context, definition_id=definition_id)
    _require_admitted_profile_history_request(request, context)
    disclosures = operation_disclosures(
        context,
        observed_by=OBSERVATION_DISCLOSING_ACTIONS,
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
        result_schema_id=None,
    )
    return bind_operation_access(
        context,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        actions=OPERATION_LIFECYCLE_ACTIONS,
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=True,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )


def _validated_profile_history_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext, *, definition_id: str
) -> ProfileHistoryRequest:
    payload = request.payload
    if request.definition_id != definition_id or type(payload) is not ProfileHistoryRequest:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def _require_admitted_profile_history_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> None:
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        # Observation is caller-independent: a fresh process replays from a new
        # destination, and result disclosure is checked against that destination.
        require_period_independent_admission(
            admitted, profile_id=context.profile_id, definition_id=request.definition_id
        )
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


__all__ = [
    "PROFILE_HISTORY_OPERATION_DEFINITION_ID",
    "PROFILE_HISTORY_TIMELINE_OPERATION_DEFINITION_ID",
    "ProfileHistoryExecutor",
    "ProfileHistoryReadPorts",
    "ProfileHistoryReadPortsFactory",
    "ProfileHistoryTimelineExecutor",
    "build_profile_history_definition",
    "build_profile_history_registration",
    "build_profile_history_timeline_definition",
    "build_profile_history_timeline_registration",
    "project_profile_history_result",
    "project_profile_history_timeline_result",
    "resolve_profile_history_access",
    "resolve_profile_history_timeline_access",
]
