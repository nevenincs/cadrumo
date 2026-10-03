"""Exact-profile registered read of the complete local bucket event history."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..bucket_event_projection import BucketEventProjection
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
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
from .history_contracts import (
    ProfileHistoryExecutionResult,
    ProfileHistoryProjection,
    ProfileHistoryRequest,
    event_matches_profile_history_request,
)

PROFILE_HISTORY_OPERATION_DEFINITION_ID = "profile.history"


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


def _read_profile_history(
    factory: ProfileHistoryReadPortsFactory,
    payload: ProfileHistoryRequest,
    operation: PinnedAuthorityOperation,
) -> ProfileHistoryExecutionResult:
    """Load and filter the exact bucket's complete history under the pinned authority."""
    bucket_id = str(payload.profile_id)
    ports = factory(bucket_id=bucket_id, operation=operation)
    if ports.bucket_id != bucket_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    events = tuple(
        event
        for event in ports.event_repository.load().for_bucket(bucket_id, event_types=payload.event_types)
        if event_matches_profile_history_request(event, payload)
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


def project_profile_history_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only an exact profile's successful, effect-free history capture."""
    if type(result) is not ProfileHistoryExecutionResult:
        raise ValueError("invalid private profile history result")
    projection = result.projection
    _require_profile_history_receipt(projection, receipt)
    return projection


def _require_profile_history_receipt(projection: ProfileHistoryProjection, receipt: OperationTerminalReceipt) -> None:
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
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_profile_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict public schemas to exact-profile whole-history admission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ProfileHistoryProjection,
        result_projector=project_profile_history_result,
        access_resolver=resolve_profile_history_access,
    )


def resolve_profile_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require one profile, all periods, and result disclosure to this destination."""
    _validated_profile_history_request(request, context)
    _require_admitted_profile_history_request(request, context)
    disclosures = _profile_history_disclosures(context)
    return _resolved_profile_history_access(request, context, disclosures)


def _validated_profile_history_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> ProfileHistoryRequest:
    payload = request.payload
    if request.definition_id != PROFILE_HISTORY_OPERATION_DEFINITION_ID or type(payload) is not ProfileHistoryRequest:
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


def _profile_history_disclosures(context: OperationAccessContext) -> frozenset[DisclosurePermission]:
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        return frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    if context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return frozenset(
            DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=schema.schema_id,
                category=category,
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return frozenset()


def _resolved_profile_history_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    disclosures: frozenset[DisclosurePermission],
) -> ResolvedOperationAccess:
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
    "ProfileHistoryExecutor",
    "ProfileHistoryReadPorts",
    "ProfileHistoryReadPortsFactory",
    "build_profile_history_definition",
    "build_profile_history_registration",
    "project_profile_history_result",
    "resolve_profile_history_access",
]
