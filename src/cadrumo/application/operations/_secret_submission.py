"""Runtime-only, exact-bound ephemeral secret submission contracts and broker."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime, timedelta
from threading import RLock
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.time import validate_utc_aware
from ._interactions import OperationInteractionId
from ._models import OperationId, OperationIdentity, OperationRevision

OperationSecretKind = Annotated[
    str,
    Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"),
]

_MAX_SECRET_BYTES = 65_536


class OperationEphemeralSecretDeclaration(BaseModel):
    """Registry declaration for one bounded pre-executor secret requirement."""

    model_config = STRICT_FROZEN_CONFIG

    secret_kind: OperationSecretKind
    lifetime: timedelta

    @model_validator(mode="after")
    def _validate_lifetime(self) -> OperationEphemeralSecretDeclaration:
        if self.lifetime <= timedelta() or self.lifetime > timedelta(hours=1):
            raise ValueError("ephemeral secret lifetime must be positive and no longer than one hour")
        return self


class OperationSecretRequirement(BaseModel):
    """Credential-free durable identity of one exact runtime-only secret wait."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    interaction_id: OperationInteractionId
    revision: OperationRevision
    secret_kind: OperationSecretKind
    expires_at: datetime

    @model_validator(mode="after")
    def _validate_expiry(self) -> OperationSecretRequirement:
        validate_utc_aware(self.expires_at)
        return self


@runtime_checkable
class EphemeralSecretSubmission(Protocol):
    """Public one-shot submission port implemented by the owning supervisor."""

    async def submit_ephemeral_secret(
        self,
        requirement: OperationSecretRequirement,
        secret: bytearray,
    ) -> None:
        """Transfer one mutable secret buffer into exact-bound runtime custody."""
        ...


@runtime_checkable
class OperationEphemeralSecretAccess(Protocol):
    """Executor-only scoped access to the submitted secret for its definition."""

    @property
    def requirement(self) -> OperationSecretRequirement:
        """Return the exact durable requirement bound to this executor."""
        ...

    def consume(self) -> AbstractAsyncContextManager[memoryview]:
        """Yield the secret once and wipe its backing storage on scope exit."""
        ...


class EphemeralSecretBroker:
    """Supervisor-private mutable custody with no serialization surface."""

    def __init__(self) -> None:
        self._entries: dict[OperationId, tuple[OperationSecretRequirement, bytearray]] = {}
        self._active: dict[OperationId, bytearray] = {}
        self._consumed: set[OperationId] = set()
        self._closed = False
        self._lock = RLock()

    def submit(
        self,
        requirement: OperationSecretRequirement,
        secret: bytearray,
        *,
        observed_at: datetime,
    ) -> None:
        if type(secret) is not bytearray:
            raise TypeError("ephemeral secret submission requires a mutable bytearray")
        owned: bytearray | None = None
        try:
            with self._lock:
                if self._closed:
                    raise ValueError("ephemeral secret submission channel is closed")
                if not secret or len(secret) > _MAX_SECRET_BYTES:
                    raise ValueError("ephemeral secret submission has an invalid length")
                if observed_at >= requirement.expires_at:
                    raise ValueError("ephemeral secret requirement is expired")
                operation_id = requirement.identity.operation_id
                if operation_id in self._consumed:
                    raise ValueError("ephemeral secret requirement is already consumed")
                if operation_id in self._entries or operation_id in self._active:
                    raise ValueError("ephemeral secret requirement already has a submission")
                owned = bytearray(secret)
                self._entries[operation_id] = (requirement, owned)
                owned = None
        finally:
            zeroize_secret_buffer(secret)
            if owned is not None:
                zeroize_secret_buffer(owned)

    def has_exact(self, requirement: OperationSecretRequirement, *, observed_at: datetime) -> bool:
        with self._lock:
            if self._closed:
                return False
            entry = self._entries.get(requirement.identity.operation_id)
            if entry is None:
                return False
            if observed_at >= requirement.expires_at:
                self._discard_unlocked(requirement.identity.operation_id)
                return False
            return entry[0] == requirement

    @asynccontextmanager
    async def consume(
        self,
        requirement: OperationSecretRequirement,
        *,
        observed_at: datetime,
    ) -> AsyncGenerator[memoryview]:
        operation_id = requirement.identity.operation_id
        with self._lock:
            if self._closed:
                raise ValueError("ephemeral secret submission channel is closed")
            entry = self._entries.pop(operation_id, None)
            if entry is None:
                if operation_id in self._consumed:
                    raise ValueError("ephemeral secret requirement is already consumed")
                raise ValueError("ephemeral secret requirement has no submission")
            bound_requirement, secret = entry
            if bound_requirement != requirement:
                zeroize_secret_buffer(secret)
                raise ValueError("ephemeral secret submission does not match the executor requirement")
            if observed_at >= requirement.expires_at:
                zeroize_secret_buffer(secret)
                raise ValueError("ephemeral secret requirement is expired")
            self._consumed.add(operation_id)
            self._active[operation_id] = secret
        view = memoryview(secret)
        try:
            yield view
        finally:
            view.release()
            with self._lock:
                self._active.pop(operation_id, None)
                zeroize_secret_buffer(secret)

    def discard(self, operation_id: OperationId) -> None:
        with self._lock:
            self._discard_unlocked(operation_id)

    def _discard_unlocked(self, operation_id: OperationId) -> None:
        entry = self._entries.pop(operation_id, None)
        if entry is not None:
            zeroize_secret_buffer(entry[1])
        active = self._active.pop(operation_id, None)
        if active is not None:
            zeroize_secret_buffer(active)
        self._consumed.discard(operation_id)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            operation_ids = self._entries.keys() | self._active.keys()
            for operation_id in tuple(operation_ids):
                self._discard_unlocked(operation_id)
            self._consumed.clear()


class BoundEphemeralSecretAccess:
    def __init__(
        self,
        *,
        requirement: OperationSecretRequirement | None,
        broker: EphemeralSecretBroker,
        clock: Callable[[], datetime],
    ) -> None:
        self._requirement = requirement
        self._broker = broker
        self._clock = clock

    @property
    def requirement(self) -> OperationSecretRequirement:
        if self._requirement is None:
            raise ValueError("operation definition does not declare an ephemeral secret")
        return self._requirement

    def consume(self) -> AbstractAsyncContextManager[memoryview]:
        return self._broker.consume(self.requirement, observed_at=self._clock())


def zeroize_secret_buffer(buffer: bytearray) -> None:
    buffer[:] = b"\x00" * len(buffer)


__all__ = [
    "EphemeralSecretSubmission",
    "OperationEphemeralSecretAccess",
    "OperationEphemeralSecretDeclaration",
    "OperationSecretKind",
    "OperationSecretRequirement",
]
