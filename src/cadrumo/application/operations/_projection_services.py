"""Canonical safe projection and public operation-control services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from secrets import compare_digest
from typing import Protocol, cast, runtime_checkable

from pydantic import BaseModel

from ...core import (
    OperationCancellation,
    OperationClosePolicy,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
    content_hash_hex,
)
from ...core.identity import ContentDigest
from ._interactions import (
    OperationActorReference,
    OperationInteractionId,
    OperationPendingInteraction,
    OperationResponseIntent,
    OperationResponseToken,
)
from ._journal import (
    OperationObservationReader,
    OperationObservationUnknownOperationError,
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from ._models import OperationId
from ._public import (
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
    OperationResponseControlRefusalCode,
    OperationResponseControlRefusalV1,
    OperationResponseControlRequestV1,
    OperationResponseControlResultV1,
    OperationResponseControlSuccessV1,
    OperationResponseControlVersionHeader,
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
from ._registry import OperationRegistry, operation_public_schema_reference
from ._secret_submission import zeroize_secret_buffer

_SUPPORTED_VERSION = 1
_READ_LIMIT = 1


@runtime_checkable
class OperationControlSupervisor(Protocol):
    """Narrow mutation port implemented by the canonical operation supervisor."""

    async def request_cancel(
        self,
        operation_id: OperationId,
        *,
        expected_revision: int,
    ) -> OperationPersistedSnapshot: ...

    async def detach(self, operation_id: OperationId) -> OperationPersistedSnapshot: ...


@runtime_checkable
class OperationSecureResponseAuthority(Protocol):
    """Runtime-only authority for separately held REVIEW response capabilities."""

    async def permitted_intents(
        self,
        request: OperationResponseControlRequestV1,
        pending: OperationPendingInteraction,
        /,
    ) -> frozenset[OperationResponseIntent]: ...


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

    def close(self) -> None:
        zeroize_secret_buffer(self._token)
        object.__setattr__(self, "_closed", True)


@dataclass(frozen=True, slots=True)
class OperationReviewProjectionService:
    reader: OperationObservationReader
    registry: OperationRegistry
    operands: OperationSecureReferenceStore
    clock: Callable[[], datetime]

    async def resolve[ReviewProjectionT: BaseModel](
        self,
        request: OperationReviewProjectionVersionHeader | OperationReviewProjectionRequestV1,
    ) -> OperationReviewProjectionResultV1[ReviewProjectionT]:
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
        snapshot = await _read_snapshot(self.reader, reference.operation_id)
        if snapshot is None:
            return _review_refusal(OperationReviewProjectionRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, _UnavailableSnapshot):
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
    reader: OperationObservationReader
    registry: OperationRegistry

    async def resolve[RefreshTargetT: BaseModel](
        self,
        request: OperationWorkspaceRefreshTargetVersionHeader | OperationWorkspaceRefreshTargetRequestV1,
    ) -> OperationWorkspaceRefreshTargetResultV1[RefreshTargetT]:
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
        snapshot = await _read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _refresh_refusal(OperationWorkspaceRefreshTargetRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, _UnavailableSnapshot):
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
class OperationResponseControlService:
    reader: OperationObservationReader
    registry: OperationRegistry
    authority: OperationSecureResponseAuthority

    async def inspect(
        self,
        request: OperationResponseControlVersionHeader | OperationResponseControlRequestV1,
    ) -> OperationResponseControlResultV1:
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
        snapshot = await _read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _response_refusal(OperationResponseControlRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, _UnavailableSnapshot):
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
                permitted_intents=intents,
            )
        except Exception:
            return _response_refusal(
                OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE,
                requested_version=1,
            )


@dataclass(frozen=True, slots=True)
class OperationCancellationService:
    reader: OperationObservationReader
    registry: OperationRegistry
    supervisor: OperationControlSupervisor

    async def request(
        self,
        request: OperationCancellationVersionHeader | OperationCancellationRequestV1,
    ) -> OperationCancellationResultV1:
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
        snapshot = await _read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _cancellation_refusal(OperationCancellationRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, _UnavailableSnapshot):
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
            latest = await _read_snapshot(self.reader, request.operation_id)
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
    reader: OperationObservationReader
    registry: OperationRegistry
    supervisor: OperationControlSupervisor

    async def detach(
        self,
        request: OperationDetachVersionHeader | OperationDetachRequestV1,
    ) -> OperationDetachResultV1:
        if request.detach_version != _SUPPORTED_VERSION:
            return _detach_refusal(
                OperationDetachRefusalCode.UNSUPPORTED_VERSION,
                requested_version=request.detach_version,
            )
        if not isinstance(request, OperationDetachRequestV1):
            return _detach_refusal(OperationDetachRefusalCode.DETACH_NOT_ALLOWED, requested_version=1)
        snapshot = await _read_snapshot(self.reader, request.operation_id)
        if snapshot is None:
            return _detach_refusal(OperationDetachRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        if isinstance(snapshot, _UnavailableSnapshot):
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


class _UnavailableSnapshot:
    pass


async def _read_snapshot(
    reader: OperationObservationReader,
    operation_id: OperationId,
) -> OperationPersistedSnapshot | _UnavailableSnapshot | None:
    try:
        materialization = await reader.read_observation(operation_id, 0, limit=_READ_LIMIT)
        return materialization.snapshot
    except OperationObservationUnknownOperationError:
        return None
    except Exception:
        return _UnavailableSnapshot()


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
    "OperationReviewProjectionService",
    "OperationSecureResponseAuthority",
    "OperationWorkspaceRefreshTargetService",
]
