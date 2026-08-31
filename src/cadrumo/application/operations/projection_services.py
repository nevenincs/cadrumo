"""Canonical safe projection and public operation-control services."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from secrets import compare_digest
from threading import RLock
from typing import Protocol, cast, runtime_checkable

from pydantic import BaseModel, TypeAdapter, ValidationError

from ...core import (
    OperationCancellation,
    OperationClosePolicy,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
    content_hash_hex,
)
from ...core.identity import ContentDigest
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
    OperationDetachResultV1,
    OperationDetachSuccessV1,
    OperationDetachVersionHeader,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalCode,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlResultV1,
    OperationResponseControlSuccessV1,
    OperationResponseControlVersionHeader,
    OperationResponseMutationRequestV1,
    OperationResponseMutationResultV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionResultV1,
    OperationResultProjectionSuccessV1,
    OperationResultProjectionVersionHeader,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionResultV1,
    OperationReviewProjectionSuccessV1,
    OperationReviewProjectionVersionHeader,
    OperationWorkspaceRefreshTargetRefusalCode,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetResultV1,
    OperationWorkspaceRefreshTargetSuccessV1,
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
from .registry import OperationRegistry, operation_public_schema_reference
from .secret_submission import zeroize_secret_buffer

_SUPPORTED_VERSION = 1
_READ_LIMIT = 1
_CONTENT_DIGEST_ADAPTER: TypeAdapter[ContentDigest] = TypeAdapter(ContentDigest)


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
class BoundOperationSecureResponseAuthority:
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

    @classmethod
    def bind(
        cls,
        *,
        operation_id: OperationId,
        interaction_id: OperationInteractionId,
        revision: int,
        reviewed_proposal_digest: ContentDigest,
        actor_ref: OperationActorReference,
        expires_at: datetime | None,
        intents: frozenset[OperationResponseIntent],
        response_token: OperationResponseToken,
        clock: Callable[[], datetime],
    ) -> BoundOperationSecureResponseAuthority:
        """Bind one mutable bearer to an exact pending REVIEW decision."""
        if not intents or not intents <= frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}):
            raise ValueError("secure response authority requires supported REVIEW intents")
        return cls(
            operation_id=operation_id,
            interaction_id=interaction_id,
            revision=revision,
            reviewed_proposal_digest=reviewed_proposal_digest,
            actor_ref=actor_ref,
            expires_at=expires_at,
            intents=intents,
            clock=clock,
            _token=bytearray(response_token, "ascii"),
        )

    async def permitted_intents(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        /,
    ) -> frozenset[OperationResponseIntent]:
        """Validate the binding and return its still-permitted response intents."""
        if self._closed:
            raise ValueError("secure response authority is closed")
        if (
            request.operation_id != self.operation_id
            or request.interaction_id != self.interaction_id
            or request.revision != self.revision
            or request.actor_ref != self.actor_ref
            or pending.request.identity.operation_id != self.operation_id
            or pending.request.interaction_id != self.interaction_id
            or pending.request.revision != self.revision
            or pending.reviewed_proposal_digest != self.reviewed_proposal_digest
            or pending.request.expires_at != self.expires_at
        ):
            raise ValueError("secure response authority binding is stale")
        if self.expires_at is not None and self.clock() > self.expires_at:
            raise ValueError("secure response authority is expired")
        token_digest = content_hash_hex(self._token.decode("ascii"))
        if not compare_digest(token_digest, pending.response_token_digest):
            raise ValueError("secure response authority bearer does not match the pending interaction")
        return self.intents

    async def response_token(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        intent: OperationResponseIntent,
        /,
    ) -> OperationResponseToken:
        """Return the private token only after exact authority validation."""
        intents = await self.permitted_intents(request, pending)
        if intent not in intents:
            raise ValueError("secure response authority does not permit the requested intent")
        return self._token.decode("ascii")

    def close(self) -> None:
        """Zeroize the in-memory response bearer and prevent reuse."""
        zeroize_secret_buffer(self._token)
        object.__setattr__(self, "_closed", True)


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


class OperationResponseAuthorityBroker:
    """Process-local REVIEW bearer custody that cannot survive restart."""

    def __init__(self) -> None:
        self._entries: dict[
            OperationId,
            tuple[OperationActorReference, ContentDigest, OperationPendingInteraction | None, bytearray | None],
        ] = {}
        self._lock = RLock()

    def reserve(
        self,
        operation_id: OperationId,
        actor_ref: OperationActorReference,
    ) -> OperationResponseCapability:
        """Issue an actor-bound opaque handle before operation execution starts."""
        handle = bytearray(secrets.token_bytes(32))
        digest = content_hash_hex(handle.hex())
        capability = OperationResponseCapability(operation_id, actor_ref, handle, _issuer=_CAPABILITY_ISSUER)
        with self._lock:
            if operation_id in self._entries:
                capability.close()
                raise ValueError("response capability is already reserved")
            self._entries[operation_id] = (actor_ref, digest, None, None)
        return capability

    def issue(self, pending: OperationPendingInteraction, response_token: OperationResponseToken) -> None:
        """Retain one mutable bearer only after its digest-bound checkpoint exists."""
        operation_id = pending.request.identity.operation_id
        token = bytearray(response_token, "ascii")
        with self._lock:
            entry = self._entries.get(operation_id)
            if entry is None:
                zeroize_secret_buffer(token)
                return
            actor_ref, capability_digest, issued_pending, issued_token = entry
            if issued_pending is not None or issued_token is not None:
                zeroize_secret_buffer(token)
                raise ValueError("response authority is already issued")
            self._entries[operation_id] = (actor_ref, capability_digest, pending, token)

    def bind(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        capability: OperationResponseCapability,
        *,
        clock: Callable[[], datetime],
    ) -> OperationSecureResponseAuthority:
        """Transfer one exact live bearer into an actor-bound response service."""
        token: bytearray | None = None
        with self._lock:
            entry = self._entries.get(request.operation_id)
            if entry is None:
                return UnavailableOperationSecureResponseAuthority()
            actor_ref, capability_digest, issued_pending, issued_token = entry
            valid = (
                capability.matches(request.operation_id, actor_ref, capability_digest)
                and request.actor_ref == actor_ref
                and issued_pending == pending
                and issued_token is not None
                and pending.request.identity.operation_id == request.operation_id
                and pending.request.interaction_id == request.interaction_id
                and pending.request.revision == request.revision
            )
            if not valid:
                return UnavailableOperationSecureResponseAuthority()
            self._entries.pop(request.operation_id)
            token = issued_token
        capability.close()
        assert token is not None
        try:
            return BoundOperationSecureResponseAuthority.bind(
                operation_id=request.operation_id,
                interaction_id=request.interaction_id,
                revision=request.revision,
                reviewed_proposal_digest=pending.reviewed_proposal_digest,
                actor_ref=request.actor_ref,
                expires_at=pending.request.expires_at,
                intents=frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
                response_token=token.decode("ascii"),
                clock=clock,
            )
        finally:
            zeroize_secret_buffer(token)

    def close(self) -> None:
        """Wipe every unbound bearer during application shutdown."""
        with self._lock:
            entries = tuple(self._entries.values())
            self._entries.clear()
        for _actor_ref, _capability_digest, _pending, token in entries:
            if token is not None:
                zeroize_secret_buffer(token)


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
        if request.review_projection_version != _SUPPORTED_VERSION:
            return _review_refusal(
                OperationReviewProjectionRefusalCode.UNSUPPORTED_VERSION,
                requested_version=request.review_projection_version,
            )
        if not isinstance(request, OperationReviewProjectionRequestV1):
            return _review_refusal(
                OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
                requested_version=_SUPPORTED_VERSION,
            )
        reference = request.reference
        snapshot = await read_snapshot(self.reader, reference.operation_id)
        if snapshot is None:
            return _review_refusal(OperationReviewProjectionRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, UnavailableSnapshot):
            return _review_refusal(
                OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
                requested_version=1,
            )
        pending = snapshot.pending_interaction
        if pending is None or pending.request.kind is not OperationInteractionKind.REVIEW:
            return _review_refusal(OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING, requested_version=1)
        interaction = pending.request
        if (
            interaction.identity.operation_id != reference.operation_id
            or interaction.interaction_id != reference.interaction_id
            or interaction.revision != reference.revision
            or interaction.expires_at != reference.expires_at
        ):
            return _review_refusal(OperationReviewProjectionRefusalCode.STALE_REVIEW_REFERENCE, requested_version=1)
        if interaction.expires_at is not None and self.clock() > interaction.expires_at:
            return _review_refusal(OperationReviewProjectionRefusalCode.REVIEW_EXPIRED, requested_version=1)
        try:
            registration = self.registry.lookup_public_registration(snapshot.identity.definition_id)
        except Exception:
            return _review_refusal(
                OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        contract = registration.contract
        if (
            snapshot.definition_contract_digest != contract.definition_contract_digest
            or reference.definition_contract_digest != contract.definition_contract_digest
        ):
            return _review_refusal(
                OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        if reference.review_projection_schema != contract.review_projection_schema:
            return _review_refusal(OperationReviewProjectionRefusalCode.REVIEW_SCHEMA_MISMATCH, requested_version=1)
        response_schema = contract.interaction_response_schema
        if response_schema is None or interaction.response_schema_ref != operation_public_schema_reference(
            response_schema
        ):
            return _review_refusal(
                OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        if registration.review_projector is None or registration.reviewed_operand_type is None:
            return _review_refusal(
                OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
                requested_version=1,
            )
        try:
            binding = self.registry.lookup_public_schema_binding(reference.review_projection_schema)
            operand = await self.operands.resolve(
                pending.reviewed_proposal_digest,
                registration.reviewed_operand_type,
            )
            projected = registration.review_projector(operand, interaction)
            del operand
            if type(projected) is not binding.model_type:
                raise TypeError("REVIEW projector returned an unregistered model")
            validated = binding.model_type.model_validate(projected.model_dump(mode="python"))
            return OperationReviewProjectionSuccessV1[ReviewProjectionT](
                projection_schema=binding.identity,
                definition_contract_digest=contract.definition_contract_digest,
                projection=cast(ReviewProjectionT, validated),
            )
        except Exception:
            return _review_refusal(
                OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
                requested_version=1,
            )


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
        if request.refresh_target_version != _SUPPORTED_VERSION:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.UNSUPPORTED_VERSION,
                requested_version=request.refresh_target_version,
            )
        if not isinstance(request, OperationWorkspaceRefreshTargetRequestV1):
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
                requested_version=1,
            )
        snapshot = await read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _refresh_refusal(OperationWorkspaceRefreshTargetRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, UnavailableSnapshot):
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
                requested_version=1,
            )
        if snapshot.lifecycle is not OperationLifecycle.TERMINAL or snapshot.terminal_receipt is None:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.OPERATION_NOT_TERMINAL,
                requested_version=1,
            )
        if snapshot.revision != request.terminal_revision:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
                requested_version=1,
            )
        if snapshot.terminal_receipt.condition is not OperationTerminalCondition.SUCCEEDED:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.OPERATION_NOT_SUCCESSFUL,
                requested_version=1,
            )
        try:
            registration = self.registry.lookup_public_registration(snapshot.identity.definition_id)
        except Exception:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        contract = registration.contract
        if (
            snapshot.definition_contract_digest != contract.definition_contract_digest
            or request.definition_contract_digest != contract.definition_contract_digest
        ):
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        if contract.workspace_refresh_target_schema is None or registration.workspace_refresh_adapter is None:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.REFRESH_ADAPTER_UNAVAILABLE,
                requested_version=1,
            )
        if request.target_schema != contract.workspace_refresh_target_schema:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.REFRESH_SCHEMA_MISMATCH,
                requested_version=1,
            )
        try:
            binding = self.registry.lookup_public_schema_binding(request.target_schema)
            target = registration.workspace_refresh_adapter(snapshot.terminal_receipt)
            if type(target) is not binding.model_type:
                raise TypeError("Workspace refresh adapter returned an unregistered model")
            validated = binding.model_type.model_validate(target.model_dump(mode="python"))
            return OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT](
                target_schema=binding.identity,
                definition_contract_digest=contract.definition_contract_digest,
                target=cast(RefreshTargetT, validated),
            )
        except Exception:
            return _refresh_refusal(
                OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
                requested_version=1,
            )


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
        if request.result_projection_version != _SUPPORTED_VERSION:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.UNSUPPORTED_VERSION,
                requested_version=request.result_projection_version,
            )
        if not isinstance(request, OperationResultProjectionRequestV1):
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
                requested_version=1,
            )
        snapshot = await read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.UNKNOWN_OPERATION,
                requested_version=1,
            )
        if isinstance(snapshot, UnavailableSnapshot):
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
                requested_version=1,
            )
        if snapshot.lifecycle is not OperationLifecycle.TERMINAL or snapshot.terminal_receipt is None:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.OPERATION_NOT_TERMINAL,
                requested_version=1,
            )
        if snapshot.revision != request.terminal_revision:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION,
                requested_version=1,
            )
        receipt = snapshot.terminal_receipt
        # A settled result is resolvable whenever the receipt carries one,
        # not only on OperationTerminalCondition.SUCCEEDED: the accepted
        # terminal-reference invariant (validate_terminal_reference_meaning)
        # forbids result_ref only for REFUSED, so a FAILED settlement that
        # still committed partial evidence remains genuinely resolvable here.
        if receipt.result_ref is None:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.OPERATION_NOT_SUCCESSFUL,
                requested_version=1,
            )
        try:
            registration = self.registry.lookup_public_registration(snapshot.identity.definition_id)
        except Exception:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        contract = registration.contract
        if (
            snapshot.definition_contract_digest != contract.definition_contract_digest
            or request.definition_contract_digest != contract.definition_contract_digest
        ):
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        if contract.result_schema is None or registration.result_projector is None:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
                requested_version=1,
            )
        if request.result_schema != contract.result_schema:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.RESULT_SCHEMA_MISMATCH,
                requested_version=1,
            )
        try:
            digest = _CONTENT_DIGEST_ADAPTER.validate_python(receipt.result_ref)
        except ValidationError:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
                requested_version=1,
            )
        try:
            binding = self.registry.lookup_public_schema_binding(request.result_schema)
            definition = self.registry.lookup(snapshot.identity.definition_id)
            if definition.result_type is None:
                raise TypeError("result-less operation definition cannot resolve a settled result")
            resolved = await self.operands.resolve(digest, definition.result_type)
            projected = registration.result_projector(resolved, receipt)
            del resolved
            if type(projected) is not binding.model_type:
                raise TypeError("result projector returned an unregistered model")
            validated = binding.model_type.model_validate(projected.model_dump(mode="python"))
            return OperationResultProjectionSuccessV1[ResultProjectionT](
                result_schema=binding.identity,
                definition_contract_digest=contract.definition_contract_digest,
                projection=cast(ResultProjectionT, validated),
            )
        except Exception:
            return _result_projection_refusal(
                OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
                requested_version=1,
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
        snapshot = await read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _response_refusal(OperationResponseControlRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, UnavailableSnapshot):
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
        try:
            contract = self.registry.lookup_public_contract(snapshot.identity.definition_id)
            response_schema = contract.interaction_response_schema
            if (
                snapshot.definition_contract_digest != contract.definition_contract_digest
                or response_schema is None
                or pending.request.response_schema_ref != operation_public_schema_reference(response_schema)
            ):
                raise ValueError("pending response does not reproduce its public definition")
        except Exception:
            return _response_refusal(
                OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
                requested_version=1,
            )
        try:
            intents = await self.authority.permitted_intents(request, pending)
            if not intents <= frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}):
                raise ValueError("secure response authority returned an unknown intent")
            return OperationResponseControlSuccessV1(
                operation_id=request.operation_id,
                interaction_id=request.interaction_id,
                revision=request.revision,
                available=bool(intents),
                permitted_intents=frozenset(intent.value for intent in intents),
            )
        except Exception:
            return _response_refusal(
                OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
                requested_version=1,
            )

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
            response: OperationApplyResponse | OperationRejectResponse
            if isinstance(request, OperationResponseApplyRequestV1):
                if pending.baseline_digest is None or pending.proposed_effect_digest is None:
                    raise ValueError("pending REVIEW lacks APPLY digests")
                response = OperationApplyResponse(
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
            else:
                response = OperationRejectResponse(
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
            consumed = await self.supervisor.respond(response)
            if consumed.interaction_id != request.interaction_id or consumed.intent is not intent:
                raise ValueError("operation supervisor consumed a different response")
            return OperationResponseMutationSuccessV1(
                operation_id=request.operation_id,
                interaction_id=request.interaction_id,
                revision=request.revision,
                response_action=request.response_action,
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
        snapshot = await read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _cancellation_refusal(OperationCancellationRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, UnavailableSnapshot):
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
        try:
            contract = self.registry.lookup_public_contract(snapshot.identity.definition_id)
        except Exception:
            return _cancellation_refusal(
                OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
                requested_version=1,
            )
        if snapshot.definition_contract_digest != contract.definition_contract_digest:
            return _cancellation_refusal(
                OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
                requested_version=1,
            )
        if contract.cancellation is OperationCancellation.UNSUPPORTED:
            return _cancellation_refusal(
                OperationCancellationRefusalCode.CANCELLATION_UNSUPPORTED,
                requested_version=1,
            )
        if snapshot.cancellation_deferred or snapshot.lifecycle not in {
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
        try:
            successor = await self.supervisor.request_cancel(
                request.operation_id,
                expected_revision=request.expected_revision,
            )
            if successor.identity.operation_id != request.operation_id or successor.cancellation_requested_at is None:
                raise ValueError("supervisor returned an invalid cancellation state")
            return OperationCancellationSuccessV1(
                operation_id=request.operation_id,
                revision=successor.revision,
                cancellation_acknowledged=successor.cancellation_acknowledged_at is not None,
            )
        except Exception:
            latest = await read_snapshot(self.reader, request.operation_id)
            if isinstance(latest, OperationPersistedSnapshot) and latest.revision != request.expected_revision:
                return _cancellation_refusal(
                    OperationCancellationRefusalCode.STALE_OPERATION_REVISION,
                    requested_version=1,
                )
            return _cancellation_refusal(
                OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE,
                requested_version=1,
            )


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
        if request.detach_version != _SUPPORTED_VERSION:
            return _detach_refusal(
                OperationDetachRefusalCode.UNSUPPORTED_VERSION,
                requested_version=request.detach_version,
            )
        if not isinstance(request, OperationDetachRequestV1):
            return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
        snapshot = await read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _detach_refusal(OperationDetachRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, UnavailableSnapshot):
            return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
        if snapshot.revision != request.expected_revision:
            return _detach_refusal(OperationDetachRefusalCode.STALE_OPERATION_REVISION, requested_version=1)
        try:
            contract = self.registry.lookup_public_contract(snapshot.identity.definition_id)
        except Exception:
            return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
        if snapshot.definition_contract_digest != contract.definition_contract_digest:
            return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
        if contract.close_policy is not OperationClosePolicy.DETACH_ALLOWED:
            return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
        try:
            detached = await self.supervisor.detach(request.operation_id)
            if detached.identity.operation_id != request.operation_id or detached.revision != snapshot.revision:
                raise ValueError("supervisor returned an invalid detach state")
            return OperationDetachSuccessV1(operation_id=request.operation_id, revision=detached.revision)
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


def _review_refusal(
    code: OperationReviewProjectionRefusalCode,
    *,
    requested_version: int | None,
) -> OperationReviewProjectionRefusalV1:
    return OperationReviewProjectionRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


def _refresh_refusal(
    code: OperationWorkspaceRefreshTargetRefusalCode,
    *,
    requested_version: int | None,
) -> OperationWorkspaceRefreshTargetRefusalV1:
    return OperationWorkspaceRefreshTargetRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


def _result_projection_refusal(
    code: OperationResultProjectionRefusalCode,
    *,
    requested_version: int | None,
) -> OperationResultProjectionRefusalV1:
    return OperationResultProjectionRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


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
