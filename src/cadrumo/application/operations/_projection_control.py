"""Mutation and response-control stages for operation projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeGuard

from ...core.operations import OperationCancellation, OperationClosePolicy, OperationInteractionKind, OperationLifecycle
from .frontend_contracts import (
    OperationCancellationRefusalCode,
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationResultV1,
    OperationCancellationSuccessV1,
    OperationCancellationVersionHeader,
    OperationDetachRefusalCode,
    OperationDetachRefusalV1,
    OperationDetachRequestV1,
    OperationDetachVersionHeader,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalCode,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlResultV1,
    OperationResponseControlSuccessV1,
    OperationResponseControlVersionHeader,
    OperationResponseMutationRequestV1,
)
from .interactions import (
    OperationApplyResponse,
    OperationPendingInteraction,
    OperationRejectResponse,
    OperationResponseIntent,
    OperationResponseToken,
)
from .models import OperationId
from .persistence.journal import (
    OperationObservationReader,
    OperationPersistedSnapshot,
)
from .registry import OperationPublicDefinitionContractV1, OperationRegistry, operation_public_schema_reference

if TYPE_CHECKING:
    from .projection_services import OperationControlSupervisor, OperationSecureResponseAuthority, UnavailableSnapshot

_SUPPORTED_VERSION = 1


async def _read_snapshot(
    reader: OperationObservationReader,
    operation_id: OperationId,
) -> OperationPersistedSnapshot | UnavailableSnapshot | None:
    from .projection_services import read_snapshot

    return await read_snapshot(reader, operation_id)


def _is_persisted_snapshot(snapshot: object) -> TypeGuard[OperationPersistedSnapshot]:
    return isinstance(snapshot, OperationPersistedSnapshot)


@dataclass(frozen=True, slots=True)
class _ResponseControlContext:
    """Durable REVIEW facts that passed the response-control identity checks."""

    request: OperationResponseControlRequestV1
    snapshot: OperationPersistedSnapshot
    pending: OperationPendingInteraction


def _response_control_request_or_refusal(
    request: OperationResponseControlVersionHeader | OperationResponseControlRequestV1,
) -> OperationResponseControlRequestV1 | OperationResponseControlRefusalV1:
    """Validate the versioned response-control envelope before reading state."""
    if request.response_control_version != _SUPPORTED_VERSION:
        return _response_refusal(
            OperationResponseControlRefusalCode.UNSUPPORTED_VERSION,
            requested_version=request.response_control_version,
        )
    if not isinstance(request, OperationResponseControlRequestV1):
        return _response_refusal(
            OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
            requested_version=1,
        )
    return request


async def _load_response_control_context(
    reader: OperationObservationReader,
    request: OperationResponseControlRequestV1,
) -> _ResponseControlContext | OperationResponseControlRefusalV1:
    """Read and validate the exact live REVIEW checkpoint for response control."""
    snapshot = await _read_snapshot(reader, request.operation_id)
    if snapshot is None:
        return _response_refusal(OperationResponseControlRefusalCode.UNKNOWN_OPERATION, requested_version=1)
    if not _is_persisted_snapshot(snapshot):
        return _response_refusal(
            OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
            requested_version=1,
        )
    pending = snapshot.pending_interaction
    if (
        pending is None
        or pending.request.kind is not OperationInteractionKind.REVIEW
        or pending.request.interaction_id != request.interaction_id
    ):
        return _response_refusal(
            OperationResponseControlRefusalCode.RESPONSE_NOT_PENDING,
            requested_version=1,
        )
    if snapshot.revision != request.revision or pending.request.revision != request.revision:
        return _response_refusal(
            OperationResponseControlRefusalCode.STALE_OPERATION_REVISION,
            requested_version=1,
        )
    return _ResponseControlContext(request=request, snapshot=snapshot, pending=pending)


def _response_control_contract_is_current(
    registry: OperationRegistry,
    context: _ResponseControlContext,
) -> bool:
    """Require the checkpoint response schema and definition digest to match."""
    try:
        contract = registry.lookup_public_contract(context.snapshot.identity.definition_id)
        response_schema = contract.interaction_response_schema
        return (
            context.snapshot.definition_contract_digest == contract.definition_contract_digest
            and response_schema is not None
            and context.pending.request.response_schema_ref == operation_public_schema_reference(response_schema)
        )
    except Exception:
        return False


async def _inspect_response_authority(
    authority: OperationSecureResponseAuthority,
    context: _ResponseControlContext,
) -> OperationResponseControlResultV1:
    """Project only the supported intents authorized by the bound bearer."""
    try:
        intents = await authority.permitted_intents(context.request, context.pending)
        if not intents <= frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}):
            raise ValueError("secure response authority returned an unknown intent")
        return OperationResponseControlSuccessV1(
            operation_id=context.request.operation_id,
            interaction_id=context.request.interaction_id,
            revision=context.request.revision,
            available=bool(intents),
            permitted_intents=frozenset(intents),
        )
    except Exception:
        return _response_refusal(
            OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
            requested_version=1,
        )


def _response_for_mutation(
    request: OperationResponseMutationRequestV1,
    pending: OperationPendingInteraction,
    response_token: OperationResponseToken,
) -> OperationApplyResponse | OperationRejectResponse:
    """Materialize the exact response payload accepted by the supervisor."""
    if isinstance(request, OperationResponseApplyRequestV1):
        if pending.baseline_digest is None or pending.proposed_effect_digest is None:
            raise ValueError("pending REVIEW lacks APPLY digests")
        return OperationApplyResponse(
            interaction_id=pending.request.interaction_id,
            operation_id=pending.request.identity.operation_id,
            revision=pending.request.revision,
            response_token=response_token,
            continuation_digest=pending.request.continuation_digest,
            reviewed_proposal_digest=pending.reviewed_proposal_digest,
            actor_ref=request.actor_ref,
            responded_at=request.responded_at,
            baseline_digest=pending.baseline_digest,
            proposed_effect_digest=pending.proposed_effect_digest,
        )
    return OperationRejectResponse(
        interaction_id=pending.request.interaction_id,
        operation_id=pending.request.identity.operation_id,
        revision=pending.request.revision,
        response_token=response_token,
        continuation_digest=pending.request.continuation_digest,
        reviewed_proposal_digest=pending.reviewed_proposal_digest,
        actor_ref=request.actor_ref,
        responded_at=request.responded_at,
        reason_code=request.reason_code,
    )


@dataclass(frozen=True, slots=True)
class _CancellationSnapshot:
    """Request and durable state that passed cancellation identity checks."""

    request: OperationCancellationRequestV1
    snapshot: OperationPersistedSnapshot


@dataclass(frozen=True, slots=True)
class _CancellationContext:
    """One cancellation request bound to its current public contract."""

    request: OperationCancellationRequestV1
    snapshot: OperationPersistedSnapshot
    contract: OperationPublicDefinitionContractV1


def _cancellation_request_or_refusal(
    request: OperationCancellationVersionHeader | OperationCancellationRequestV1,
) -> OperationCancellationRequestV1 | OperationCancellationRefusalV1:
    """Validate the versioned request envelope before reading durable state."""
    if request.cancellation_version != _SUPPORTED_VERSION:
        return _cancellation_refusal(
            OperationCancellationRefusalCode.UNSUPPORTED_VERSION,
            requested_version=request.cancellation_version,
        )
    if not isinstance(request, OperationCancellationRequestV1):
        return _cancellation_refusal(
            OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
            requested_version=1,
        )
    return request


async def _load_cancellation_snapshot(
    reader: OperationObservationReader,
    request: OperationCancellationRequestV1,
) -> _CancellationSnapshot | OperationCancellationRefusalV1:
    """Read and validate the exact live snapshot named by the request."""
    snapshot = await _read_snapshot(reader, request.operation_id)
    if snapshot is None:
        return _cancellation_refusal(OperationCancellationRefusalCode.UNKNOWN_OPERATION, requested_version=1)
    if not _is_persisted_snapshot(snapshot):
        return _cancellation_refusal(
            OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
            requested_version=1,
        )
    if snapshot.revision != request.expected_revision:
        return _cancellation_refusal(
            OperationCancellationRefusalCode.STALE_OPERATION_REVISION,
            requested_version=1,
        )
    if snapshot.lifecycle is OperationLifecycle.TERMINAL:
        return _cancellation_refusal(OperationCancellationRefusalCode.OPERATION_TERMINAL, requested_version=1)
    return _CancellationSnapshot(request=request, snapshot=snapshot)


def _authorize_cancellation(
    registry: OperationRegistry,
    loaded: _CancellationSnapshot,
) -> _CancellationContext | OperationCancellationRefusalV1:
    """Bind the live snapshot to a current contract that permits cancellation."""
    try:
        contract = registry.lookup_public_contract(loaded.snapshot.identity.definition_id)
    except Exception:
        return _cancellation_refusal(
            OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
            requested_version=1,
        )
    if loaded.snapshot.definition_contract_digest != contract.definition_contract_digest:
        return _cancellation_refusal(
            OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
            requested_version=1,
        )
    if contract.cancellation is OperationCancellation.UNSUPPORTED:
        return _cancellation_refusal(
            OperationCancellationRefusalCode.CANCELLATION_UNSUPPORTED,
            requested_version=1,
        )
    if loaded.snapshot.cancellation_deferred or loaded.snapshot.lifecycle not in {
        OperationLifecycle.RUNNING,
        OperationLifecycle.WAITING_FOR_INTERACTION,
        OperationLifecycle.WAITING_FOR_EXTERNAL,
        OperationLifecycle.CANCELLATION_REQUESTED,
        OperationLifecycle.SETTLING,
    }:
        return _cancellation_refusal(
            OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
            requested_version=1,
        )
    return _CancellationContext(request=loaded.request, snapshot=loaded.snapshot, contract=contract)


async def _execute_cancellation(
    reader: OperationObservationReader,
    supervisor: OperationControlSupervisor,
    context: _CancellationContext,
) -> OperationCancellationResultV1:
    """Request cancellation and translate races into stable public outcomes."""
    try:
        successor = await supervisor.request_cancel(
            context.request.operation_id,
            expected_revision=context.request.expected_revision,
        )
        if (
            successor.identity.operation_id != context.request.operation_id
            or successor.cancellation_requested_at is None
        ):
            raise ValueError("supervisor returned an invalid cancellation state")
        return OperationCancellationSuccessV1(
            operation_id=context.request.operation_id,
            revision=successor.revision,
            cancellation_acknowledged=successor.cancellation_acknowledged_at is not None,
        )
    except Exception:
        latest = await _read_snapshot(reader, context.request.operation_id)
        if isinstance(latest, OperationPersistedSnapshot) and latest.revision != context.request.expected_revision:
            return _cancellation_refusal(
                OperationCancellationRefusalCode.STALE_OPERATION_REVISION,
                requested_version=1,
            )
        return _cancellation_refusal(
            OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
            requested_version=1,
        )


@dataclass(frozen=True, slots=True)
class _DetachContext:
    """Detach request and durable state bound to an allowed public contract."""

    request: OperationDetachRequestV1
    snapshot: OperationPersistedSnapshot


async def _load_detach_context(
    reader: OperationObservationReader,
    registry: OperationRegistry,
    request: OperationDetachVersionHeader | OperationDetachRequestV1,
) -> _DetachContext | OperationDetachRefusalV1:
    """Validate, read, and authorize the exact live detach snapshot."""
    if request.detach_version != _SUPPORTED_VERSION:
        return _detach_refusal(
            OperationDetachRefusalCode.UNSUPPORTED_VERSION,
            requested_version=request.detach_version,
        )
    if not isinstance(request, OperationDetachRequestV1):
        return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
    snapshot = await _read_snapshot(reader, request.operation_id)
    if snapshot is None:
        return _detach_refusal(OperationDetachRefusalCode.UNKNOWN_OPERATION, requested_version=1)
    if not _is_persisted_snapshot(snapshot):
        return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
    if snapshot.revision != request.expected_revision:
        return _detach_refusal(OperationDetachRefusalCode.STALE_OPERATION_REVISION, requested_version=1)
    try:
        contract = registry.lookup_public_contract(snapshot.identity.definition_id)
    except Exception:
        return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
    if (
        snapshot.definition_contract_digest != contract.definition_contract_digest
        or contract.close_policy is not OperationClosePolicy.DETACH_ALLOWED
    ):
        return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
    return _DetachContext(request=request, snapshot=snapshot)


def _response_refusal(
    code: OperationResponseControlRefusalCode,
    *,
    requested_version: int | None,
) -> OperationResponseControlRefusalV1:
    return OperationResponseControlRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


def _cancellation_refusal(
    code: OperationCancellationRefusalCode,
    *,
    requested_version: int | None,
) -> OperationCancellationRefusalV1:
    return OperationCancellationRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


def _detach_refusal(
    code: OperationDetachRefusalCode,
    *,
    requested_version: int | None,
) -> OperationDetachRefusalV1:
    return OperationDetachRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


authorize_cancellation = _authorize_cancellation
cancellation_request_or_refusal = _cancellation_request_or_refusal
detach_refusal = _detach_refusal
execute_cancellation = _execute_cancellation
inspect_response_authority = _inspect_response_authority
load_cancellation_snapshot = _load_cancellation_snapshot
load_detach_context = _load_detach_context
load_response_control_context = _load_response_control_context
response_control_contract_is_current = _response_control_contract_is_current
response_control_request_or_refusal = _response_control_request_or_refusal
response_for_mutation = _response_for_mutation
response_refusal = _response_refusal
