"""Canonical safe projection and public operation-control services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from secrets import compare_digest
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ...core.hashing import content_hash_hex
from ...core.identity.digest import ContentDigest
from ._projection_authority import (
    BoundOperationSecureResponseAuthorityMixin,
    OperationResponseAuthorityBrokerMixin,
)
from ._projection_control import (
    authorize_cancellation as _authorize_cancellation,
)
from ._projection_control import (
    cancellation_request_or_refusal as _cancellation_request_or_refusal,
)
from ._projection_control import (
    detach_refusal as _detach_refusal,
)
from ._projection_control import (
    execute_cancellation as _execute_cancellation,
)
from ._projection_control import (
    inspect_response_authority as _inspect_response_authority,
)
from ._projection_control import (
    load_cancellation_snapshot as _load_cancellation_snapshot,
)
from ._projection_control import (
    load_detach_context as _load_detach_context,
)
from ._projection_control import (
    load_response_control_context as _load_response_control_context,
)
from ._projection_control import (
    response_control_contract_is_current as _response_control_contract_is_current,
)
from ._projection_control import (
    response_control_request_or_refusal as _response_control_request_or_refusal,
)
from ._projection_control import (
    response_for_mutation as _response_for_mutation,
)
from ._projection_control import (
    response_refusal as _response_refusal,
)
from ._projection_read import (
    load_refresh_context as _load_refresh_context,
)
from ._projection_read import (
    load_result_context as _load_result_context,
)
from ._projection_read import (
    load_review_context as _load_review_context,
)
from ._projection_read import (
    lookup_refresh_registration as _lookup_refresh_registration,
)
from ._projection_read import (
    lookup_result_registration as _lookup_result_registration,
)
from ._projection_read import (
    lookup_review_registration as _lookup_review_registration,
)
from ._projection_read import (
    refresh_request_or_refusal as _refresh_request_or_refusal,
)
from ._projection_read import (
    resolve_refresh_target as _resolve_refresh_target,
)
from ._projection_read import (
    resolve_result_projection as _resolve_result_projection,
)
from ._projection_read import (
    resolve_review_projection as _resolve_review_projection,
)
from ._projection_read import (
    result_digest_or_refusal as _result_digest_or_refusal,
)
from ._projection_read import (
    result_request_or_refusal as _result_request_or_refusal,
)
from ._projection_read import (
    review_request_or_refusal as _review_request_or_refusal,
)
from .frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationResponseControlResultV1,
    OperationResponseMutationRequestV1,
    OperationResponseMutationResultV1,
    OperationResultProjectionResultV1,
    OperationReviewProjectionResultV1,
    OperationWorkspaceRefreshTargetResultV1,
)
from .frontend_requests import (
    OperationCancellationRefusalV1,
    OperationCancellationRequestV1,
    OperationCancellationVersionHeader,
    OperationDetachRefusalCode,
    OperationDetachRefusalV1,
    OperationDetachRequestV1,
    OperationDetachSuccessV1,
    OperationDetachVersionHeader,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalCode,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlVersionHeader,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionVersionHeader,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionVersionHeader,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetVersionHeader,
)
from .interactions import (
    OperationActorReference,
    OperationApplyResponse,
    OperationConsumedInteraction,
    OperationInteractionId,
    OperationPendingInteraction,
    OperationRejectResponse,
    OperationResponseIntent,
    OperationResponseToken,
)
from .models import OperationId
from .persistence.journal import (
    OperationObservationReader,
    OperationObservationUnknownOperationError,
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from .registry import (
    OperationRegistry,
)
from .secret_submission import zeroize_secret_buffer

_READ_LIMIT = 1


@runtime_checkable
class OperationControlSupervisor(Protocol):
    """Narrow mutation port implemented by the canonical operation supervisor."""

    async def request_cancel(
        self,
        operation_id: OperationId,
        *,
        expected_revision: int,
    ) -> OperationPersistedSnapshot:
        """Request cooperative cancellation at one expected revision."""
        ...

    async def detach(self, operation_id: OperationId) -> OperationPersistedSnapshot:
        """Detach the caller while retaining the durable operation state."""
        ...

    async def respond(
        self,
        response: OperationApplyResponse | OperationRejectResponse,
    ) -> OperationConsumedInteraction:
        """Consume one validated REVIEW response."""
        ...


@runtime_checkable
class OperationSecureResponseAuthority(Protocol):
    """Runtime-only authority for separately held REVIEW response capabilities."""

    async def permitted_intents(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        /,
    ) -> frozenset[OperationResponseIntent]:
        """Return the response intents authorized for an exact pending review."""
        ...

    async def response_token(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        intent: OperationResponseIntent,
        /,
    ) -> OperationResponseToken:
        """Return the opaque token only for one authorized response intent."""
        ...

    def close(self) -> None:
        """Irreversibly close and wipe this runtime-only authority."""
        ...


@runtime_checkable
class OperationResponseAuthorityIssuer(Protocol):
    """Runtime-only sink for one freshly published REVIEW bearer."""

    def issue(self, pending: OperationPendingInteraction, response_token: OperationResponseToken) -> None: ...


@dataclass(frozen=True, slots=True)
class BoundOperationSecureResponseAuthority(BoundOperationSecureResponseAuthorityMixin):
    """One runtime-only bearer bound to an exact pending REVIEW decision."""

    operation_id: OperationId
    interaction_id: OperationInteractionId
    revision: int
    reviewed_proposal_digest: ContentDigest
    actor_ref: OperationActorReference
    expires_at: datetime | None
    intents: frozenset[OperationResponseIntent]
    clock: Callable[[], datetime]
    _token: bytearray = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)


class UnavailableOperationSecureResponseAuthority:
    async def permitted_intents(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        /,
    ) -> frozenset[OperationResponseIntent]:
        del request, pending
        raise ValueError("response authority is unavailable")

    async def response_token(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        intent: OperationResponseIntent,
        /,
    ) -> OperationResponseToken:
        del request, pending, intent
        raise ValueError("response authority is unavailable")

    def close(self) -> None:
        """Close the empty authority idempotently."""


_CAPABILITY_ISSUER = object()


class OperationResponseCapability:
    """Opaque process-local capability retained separately from observation."""

    __slots__ = ("__actor_ref", "__closed", "__handle", "__operation_id")

    def __init__(
        self,
        operation_id: OperationId,
        actor_ref: OperationActorReference,
        handle: bytearray,
        *,
        _issuer: object,
    ) -> None:
        if _issuer is not _CAPABILITY_ISSUER:
            raise TypeError("response capabilities are issued only by production composition")
        self.__operation_id = operation_id
        self.__actor_ref = actor_ref
        self.__handle = handle
        self.__closed = False

    def matches(
        self,
        operation_id: OperationId,
        actor_ref: OperationActorReference,
        capability_digest: ContentDigest,
    ) -> bool:
        return (
            not self.__closed
            and self.__operation_id == operation_id
            and self.__actor_ref == actor_ref
            and compare_digest(content_hash_hex(self.__handle.hex()), capability_digest)
        )

    def close(self) -> None:
        """Irrevocably release this caller-held response capability."""
        zeroize_secret_buffer(self.__handle)
        self.__closed = True


class OperationResponseAuthorityBroker(OperationResponseAuthorityBrokerMixin):
    """Process-local REVIEW bearer custody that cannot survive restart."""

    _capability_issuer = _CAPABILITY_ISSUER


@dataclass(frozen=True, slots=True)
class OperationReviewProjectionService:
    """Resolve safe public REVIEW projections from durable operation state."""

    reader: OperationObservationReader
    registry: OperationRegistry
    operands: OperationSecureReferenceStore
    clock: Callable[[], datetime]

    async def resolve[ReviewProjectionT: BaseModel](
        self,
        request: OperationReviewProjectionVersionHeader | OperationReviewProjectionRequestV1,
    ) -> OperationReviewProjectionResultV1[ReviewProjectionT]:
        """Resolve the exact registered REVIEW projection or a typed refusal."""
        reference_or_refusal = _review_request_or_refusal(request)
        if isinstance(reference_or_refusal, OperationReviewProjectionRefusalV1):
            return reference_or_refusal
        context_or_refusal = await _load_review_context(self.reader, reference_or_refusal, self.clock)
        if isinstance(context_or_refusal, OperationReviewProjectionRefusalV1):
            return context_or_refusal
        registration_or_refusal = _lookup_review_registration(self.registry, context_or_refusal)
        if isinstance(registration_or_refusal, OperationReviewProjectionRefusalV1):
            return registration_or_refusal
        return await _resolve_review_projection(self.registry, self.operands, registration_or_refusal)


@dataclass(frozen=True, slots=True)
class OperationWorkspaceRefreshTargetService:
    """Resolve safe typed workspace refresh targets after terminal success."""

    reader: OperationObservationReader
    registry: OperationRegistry

    async def resolve[RefreshTargetT: BaseModel](
        self,
        request: OperationWorkspaceRefreshTargetVersionHeader | OperationWorkspaceRefreshTargetRequestV1,
    ) -> OperationWorkspaceRefreshTargetResultV1[RefreshTargetT]:
        """Resolve the exact registered refresh target or a typed refusal."""
        request_or_refusal = _refresh_request_or_refusal(request)
        if isinstance(request_or_refusal, OperationWorkspaceRefreshTargetRefusalV1):
            return request_or_refusal
        context_or_refusal = await _load_refresh_context(self.reader, request_or_refusal)
        if isinstance(context_or_refusal, OperationWorkspaceRefreshTargetRefusalV1):
            return context_or_refusal
        registration_or_refusal = _lookup_refresh_registration(self.registry, context_or_refusal)
        if isinstance(registration_or_refusal, OperationWorkspaceRefreshTargetRefusalV1):
            return registration_or_refusal
        return await _resolve_refresh_target(self.registry, registration_or_refusal)


@dataclass(frozen=True, slots=True)
class OperationResultProjectionService:
    """Resolve safe public settled-result projections after terminal success.

    Symmetric with :class:`OperationReviewProjectionService`: the private
    settled result is resolved behind the secure operand port and handed,
    with the safe terminal receipt, to the registered domain projector. The
    private result type never crosses this boundary; only the projector's
    typed public output does.
    """

    reader: OperationObservationReader
    registry: OperationRegistry
    operands: OperationSecureReferenceStore

    async def resolve[ResultProjectionT: BaseModel](
        self,
        request: OperationResultProjectionVersionHeader | OperationResultProjectionRequestV1,
    ) -> OperationResultProjectionResultV1[ResultProjectionT]:
        """Resolve the exact registered public result projection or a refusal."""
        request_or_refusal = _result_request_or_refusal(request)
        if isinstance(request_or_refusal, OperationResultProjectionRefusalV1):
            return request_or_refusal
        context_or_refusal = await _load_result_context(self.reader, request_or_refusal)
        if isinstance(context_or_refusal, OperationResultProjectionRefusalV1):
            return context_or_refusal
        registration_or_refusal = _lookup_result_registration(self.registry, context_or_refusal)
        if isinstance(registration_or_refusal, OperationResultProjectionRefusalV1):
            return registration_or_refusal
        digest_or_refusal = _result_digest_or_refusal(context_or_refusal)
        if isinstance(digest_or_refusal, OperationResultProjectionRefusalV1):
            return digest_or_refusal
        return await _resolve_result_projection(
            self.registry,
            self.operands,
            registration_or_refusal,
            digest_or_refusal,
        )


@dataclass(frozen=True, slots=True)
class OperationResponseControlService:
    """Inspect and execute safe REVIEW response control at the public boundary."""

    reader: OperationObservationReader
    registry: OperationRegistry
    authority: OperationSecureResponseAuthority
    supervisor: OperationControlSupervisor

    async def inspect(
        self,
        request: OperationResponseControlVersionHeader | OperationResponseControlRequestV1,
    ) -> OperationResponseControlResultV1:
        """Return authorized response intents or a typed refusal."""
        request_or_refusal = _response_control_request_or_refusal(request)
        if isinstance(request_or_refusal, OperationResponseControlRefusalV1):
            return request_or_refusal
        context_or_refusal = await _load_response_control_context(self.reader, request_or_refusal)
        if isinstance(context_or_refusal, OperationResponseControlRefusalV1):
            return context_or_refusal
        if not _response_control_contract_is_current(self.registry, context_or_refusal):
            return _response_refusal(
                OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
                requested_version=1,
            )
        return await _inspect_response_authority(self.authority, context_or_refusal)

    async def apply(self, request: OperationResponseApplyRequestV1) -> OperationResponseMutationResultV1:
        """Consume one exact APPLY response through the bound runtime authority."""
        return await self._respond(request)

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationResultV1:
        """Consume one exact REJECT response through the bound runtime authority."""
        return await self._respond(request)

    async def _respond(self, request: OperationResponseMutationRequestV1) -> OperationResponseMutationResultV1:
        availability = await self.inspect(request)
        if isinstance(availability, OperationResponseControlRefusalV1):
            return availability
        intent = OperationResponseIntent(request.response_action)
        if request.response_action not in availability.permitted_intents:
            return _response_refusal(
                OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
                requested_version=1,
            )
        snapshot = await read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _response_refusal(OperationResponseControlRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, UnavailableSnapshot) or snapshot.pending_interaction is None:
            return _response_refusal(
                OperationResponseControlRefusalCode.RESPONSE_NOT_PENDING,
                requested_version=1,
            )
        pending = snapshot.pending_interaction
        try:
            response_token = await self.authority.response_token(request, pending, intent)
            response = _response_for_mutation(request, pending, response_token)
            consumed = await self.supervisor.respond(response)
            if consumed.interaction_id != request.interaction_id or consumed.intent is not intent:
                raise ValueError("operation supervisor consumed a different response")
            return OperationResponseMutationSuccessV1(
                operation_id=request.operation_id,
                interaction_id=request.interaction_id,
                revision=request.revision,
                response_action=intent,
            )
        except Exception:
            return _response_refusal(
                OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
                requested_version=1,
            )
        finally:
            self.authority.close()


@dataclass(frozen=True, slots=True)
class OperationCancellationService:
    """Request cooperative cancellation through one versioned public boundary."""

    reader: OperationObservationReader
    registry: OperationRegistry
    supervisor: OperationControlSupervisor

    async def request(
        self,
        request: OperationCancellationVersionHeader | OperationCancellationRequestV1,
    ) -> OperationCancellationResultV1:
        """Request cancellation or return a stable typed refusal."""
        request_or_refusal = _cancellation_request_or_refusal(request)
        if isinstance(request_or_refusal, OperationCancellationRefusalV1):
            return request_or_refusal
        snapshot_or_refusal = await _load_cancellation_snapshot(self.reader, request_or_refusal)
        if isinstance(snapshot_or_refusal, OperationCancellationRefusalV1):
            return snapshot_or_refusal
        context_or_refusal = _authorize_cancellation(self.registry, snapshot_or_refusal)
        if isinstance(context_or_refusal, OperationCancellationRefusalV1):
            return context_or_refusal
        return await _execute_cancellation(self.reader, self.supervisor, context_or_refusal)


@dataclass(frozen=True, slots=True)
class OperationDetachService:
    """Detach a frontend from an operation through one public boundary."""

    reader: OperationObservationReader
    registry: OperationRegistry
    supervisor: OperationControlSupervisor

    async def detach(
        self,
        request: OperationDetachVersionHeader | OperationDetachRequestV1,
    ) -> OperationDetachResultV1:
        """Detach the requested operation or return a stable typed refusal."""
        context_or_refusal = await _load_detach_context(self.reader, self.registry, request)
        if isinstance(context_or_refusal, OperationDetachRefusalV1):
            return context_or_refusal
        try:
            detached = await self.supervisor.detach(context_or_refusal.request.operation_id)
            if (
                detached.identity.operation_id != context_or_refusal.request.operation_id
                or detached.revision != context_or_refusal.snapshot.revision
            ):
                raise ValueError("supervisor returned an invalid detach state")
            return OperationDetachSuccessV1(
                operation_id=context_or_refusal.request.operation_id,
                revision=detached.revision,
            )
        except Exception:
            return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)


class UnavailableSnapshot:
    pass


async def read_snapshot(
    reader: OperationObservationReader,
    operation_id: OperationId,
) -> OperationPersistedSnapshot | UnavailableSnapshot | None:
    try:
        materialization = await reader.read_observation(operation_id, 0, limit=_READ_LIMIT)
        return materialization.snapshot
    except OperationObservationUnknownOperationError:
        return None
    except Exception:
        return UnavailableSnapshot()


__all__ = [
    "BoundOperationSecureResponseAuthority",
    "OperationCancellationService",
    "OperationControlSupervisor",
    "OperationDetachService",
    "OperationResponseControlService",
    "OperationResultProjectionService",
    "OperationReviewProjectionService",
    "OperationSecureResponseAuthority",
    "OperationWorkspaceRefreshTargetService",
]
