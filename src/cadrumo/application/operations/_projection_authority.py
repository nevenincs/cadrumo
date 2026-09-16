"""Runtime-only response authority mechanics for operation projections."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol

from ...core.hashing import content_hash_hex
from ...core.identity.digest import ContentDigest
from .frontend_requests import OperationResponseControlRequestV1
from .interactions import (
    OperationActorReference,
    OperationInteractionId,
    OperationPendingInteraction,
    OperationResponseIntent,
    OperationResponseToken,
)
from .models import OperationId
from .secret_submission import zeroize_secret_buffer

if TYPE_CHECKING:
    from .projection_services import (
        OperationResponseCapability,
    )


class _AuthorityHost:
    if TYPE_CHECKING:
        operation_id: OperationId
        interaction_id: OperationInteractionId
        revision: int
        reviewed_proposal_digest: ContentDigest
        actor_ref: OperationActorReference
        expires_at: datetime | None
        intents: frozenset[OperationResponseIntent]
        clock: Callable[[], datetime]
        _token: bytearray
        _closed: bool

        def __getattr__(self, name: str) -> Any: ...


class _BoundAuthorityHost(Protocol):
    @property
    def operation_id(self) -> OperationId: ...

    @property
    def interaction_id(self) -> OperationInteractionId: ...

    @property
    def revision(self) -> int: ...

    @property
    def reviewed_proposal_digest(self) -> ContentDigest: ...

    @property
    def actor_ref(self) -> OperationActorReference: ...

    @property
    def expires_at(self) -> datetime | None: ...


def response_authority_binding_matches(
    authority: _BoundAuthorityHost,
    request: OperationResponseControlRequestV1,
    pending: OperationPendingInteraction,
) -> bool:
    """Match request and checkpoint coordinates to the bound bearer exactly."""
    return (
        request.operation_id == authority.operation_id
        and request.interaction_id == authority.interaction_id
        and request.revision == authority.revision
        and request.actor_ref == authority.actor_ref
        and pending.request.identity.operation_id == authority.operation_id
        and pending.request.interaction_id == authority.interaction_id
        and pending.request.revision == authority.revision
        and pending.reviewed_proposal_digest == authority.reviewed_proposal_digest
        and pending.request.expires_at == authority.expires_at
    )


class OperationResponseAuthorityBrokerMixin(_AuthorityHost):
    """Implementation of process-local REVIEW bearer custody."""

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
        from .projection_services import OperationResponseCapability

        handle = bytearray(secrets.token_bytes(32))
        digest = content_hash_hex(handle.hex())
        capability = OperationResponseCapability(operation_id, actor_ref, handle, _issuer=self._capability_issuer)
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
    ) -> Any:
        """Transfer one exact live bearer into an actor-bound response service."""
        from .projection_services import (
            BoundOperationSecureResponseAuthority,
            UnavailableOperationSecureResponseAuthority,
        )

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
        if token is None:
            raise ValueError("a bound secure-response authority requires the token its capability issued")
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


__all__ = [
    "OperationResponseAuthorityBrokerMixin",
    "response_authority_binding_matches",
]
