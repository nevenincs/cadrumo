"""Immutable identity, request, snapshot, revision, and receipt contracts."""

from __future__ import annotations

import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import PurePath
from typing import Annotated, cast
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.time import validate_utc_aware
from ._model_contract import require_strict_frozen_operation_model_graph

type OperationId = Hex64Str
"""Opaque 256-bit identity of one operation invocation."""

type OperationRevision = Annotated[int, Field(ge=0)]
"""Optimistic, monotonically increasing snapshot revision."""

type OperationDefinitionId = Annotated[
    str,
    Field(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    ),
]
"""Stable registered operation-definition identity."""

type OperationReference = Annotated[str, Field(min_length=1, max_length=256)]
"""Opaque safe reference to an application-owned record or subject."""

type OperationDiagnosticReference = Annotated[
    str,
    Field(pattern=r"^sha256:(?:[0-9a-f]{12}|[0-9a-f]{64})$"),
]
"""Opaque correlation fingerprint; never diagnostic prose or identity content."""


class OperationReconciliationOutcome(StrEnum):
    """Closed durable classifications emitted only by the supervisor at restart."""

    RECOVERED = "recovered"
    RESUMED = "resumed"
    INTERRUPTED = "interrupted"
    ORPHANED = "orphaned"


class OperationIdentity(BaseModel):
    """Immutable invocation identity, distinct from recovery-action identity."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: OperationId
    definition_id: OperationDefinitionId
    subject_ref: OperationReference


class CredentialFreeOperationRequest(BaseModel):
    """Explicit opt-in base for request payloads safe to retain without credentials."""

    model_config = STRICT_FROZEN_CONFIG


class OperationRequest[RequestPayloadT: BaseModel](BaseModel):
    """Validated typed operand submitted to one registered operation definition."""

    model_config = STRICT_FROZEN_CONFIG

    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    payload: RequestPayloadT
    idempotency_key: Annotated[str, Field(min_length=1, max_length=256)] | None = None

    @model_validator(mode="after")
    def _validate_payload_immutability(self) -> OperationRequest[RequestPayloadT]:
        require_strict_frozen_operation_model_graph(
            type(self.payload),
            path="request payload",
            reject_mutable_annotations=False,
            require_validated_defaults=False,
        )
        _require_deeply_immutable_payload(self.payload, path="payload", visiting=set())
        return self


class OperationTerminalReceipt(BaseModel):
    """Settled terminal fact that cannot precede resource cleanup."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    revision: OperationRevision
    condition: OperationTerminalCondition
    effect: OperationEffect
    settled_at: datetime
    result_ref: OperationReference | None = None
    refusal_ref: OperationReference | None = None
    diagnostic_ref: OperationDiagnosticReference | None = None

    @model_validator(mode="after")
    def _validate_terminal_references(self) -> OperationTerminalReceipt:
        validate_utc_aware(self.settled_at)
        validate_terminal_reference_meaning(
            condition=self.condition,
            result_ref=self.result_ref,
            refusal_ref=self.refusal_ref,
        )
        return self


def validate_terminal_reference_meaning(
    *,
    condition: OperationTerminalCondition,
    result_ref: OperationReference | None,
    refusal_ref: OperationReference | None,
) -> None:
    """Enforce the canonical terminal result/refusal relationship."""
    if condition is OperationTerminalCondition.SUCCEEDED:
        if result_ref is None or refusal_ref is not None:
            raise ValueError("succeeded operation requires one result reference and forbids a refusal reference")
    elif condition is OperationTerminalCondition.REFUSED:
        if refusal_ref is None or result_ref is not None:
            raise ValueError("refused operation requires one refusal reference and forbids a result reference")
    elif refusal_ref is not None:
        raise ValueError("refusal reference is valid only for a refused operation")


class OperationSnapshot[RequestPayloadT: BaseModel](BaseModel):
    """One immutable, revisioned observation of authoritative operation state."""

    model_config = STRICT_FROZEN_CONFIG

    identity: OperationIdentity
    request: OperationRequest[RequestPayloadT]
    revision: OperationRevision
    lifecycle: OperationLifecycle
    terminal_condition: OperationTerminalCondition | None = None
    effect: OperationEffect = OperationEffect.NONE
    phase_code: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    updated_at: datetime
    event_cursor: Annotated[int, Field(ge=0)] = 0
    terminal_receipt: OperationTerminalReceipt | None = None

    @model_validator(mode="after")
    def _validate_snapshot(self) -> OperationSnapshot[RequestPayloadT]:
        validate_utc_aware(self.updated_at)
        self._validate_request_identity()
        self._validate_terminal_state()
        return self

    def _validate_request_identity(self) -> None:
        if self.request.definition_id != self.identity.definition_id:
            raise ValueError("operation request definition does not match invocation identity")
        if self.request.subject_ref != self.identity.subject_ref:
            raise ValueError("operation request subject does not match invocation identity")

    def _validate_terminal_state(self) -> None:
        terminal = self.lifecycle is OperationLifecycle.TERMINAL
        if terminal != (self.terminal_condition is not None):
            raise ValueError("terminal lifecycle requires exactly one terminal condition")
        if terminal != (self.terminal_receipt is not None):
            raise ValueError("terminal lifecycle requires exactly one terminal receipt")
        if self.terminal_receipt is None:
            return
        receipt = self.terminal_receipt
        if receipt.identity != self.identity:
            raise ValueError("terminal receipt identity does not match operation snapshot")
        if receipt.revision != self.revision:
            raise ValueError("terminal receipt revision does not match operation snapshot")
        if receipt.condition is not self.terminal_condition:
            raise ValueError("terminal receipt condition does not match operation snapshot")
        if receipt.effect is not self.effect:
            raise ValueError("terminal receipt effect does not match operation snapshot")
        if receipt.settled_at != self.updated_at:
            raise ValueError("terminal receipt settlement time does not match operation snapshot")


def new_operation_id() -> str:
    """Mint a cryptographically random operation invocation identity."""
    return secrets.token_hex(32)


_IMMUTABLE_SCALARS = (str, bytes, int, float, bool, Decimal, UUID, date, datetime, time, timedelta, PurePath, Enum)


def _require_deeply_immutable_payload(value: object, *, path: str, visiting: set[int]) -> None:
    """Refuse payload state that can change after request validation."""
    if value is None or isinstance(value, _IMMUTABLE_SCALARS):
        return
    identity = id(value)
    if identity in visiting:
        raise ValueError(f"operation request {path} contains a cyclic reference")
    if isinstance(value, BaseModel):
        require_strict_frozen_operation_model_graph(
            type(value),
            path=f"request {path}",
            reject_mutable_annotations=False,
            require_validated_defaults=False,
        )
        visiting.add(identity)
        try:
            for field_name in type(value).model_fields:
                _require_deeply_immutable_payload(
                    getattr(value, field_name),
                    path=f"{path}.{field_name}",
                    visiting=visiting,
                )
        finally:
            visiting.remove(identity)
        return
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
    elif isinstance(value, frozenset):
        items = cast(frozenset[object], value)
    else:
        raise ValueError(f"operation request {path} contains mutable or unsupported {type(value).__name__}")
    visiting.add(identity)
    try:
        for index, item in enumerate(items):
            _require_deeply_immutable_payload(item, path=f"{path}[{index}]", visiting=visiting)
    finally:
        visiting.remove(identity)


__all__ = [
    "CredentialFreeOperationRequest",
    "OperationDefinitionId",
    "OperationDiagnosticReference",
    "OperationId",
    "OperationIdentity",
    "OperationReconciliationOutcome",
    "OperationReference",
    "OperationRequest",
    "OperationRevision",
    "OperationSnapshot",
    "OperationTerminalReceipt",
    "new_operation_id",
]
