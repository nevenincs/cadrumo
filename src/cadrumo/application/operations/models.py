"""Immutable identity, request, snapshot, revision, and receipt contracts."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import PurePath
from typing import TYPE_CHECKING, Annotated, cast
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import HEX_PATTERN_64, Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...core.time.utc import validate_utc_aware
from ._model_contract import require_strict_frozen_operation_model_graph

if TYPE_CHECKING:
    from .provenance import OperationAdmissionProvenance

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

type OperationFailureErrorCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]+$")]
"""Upper-case machine error code a terminal failure reports."""

type OperationReference = Annotated[str, Field(min_length=1, max_length=256)]
"""Opaque safe reference to an application-owned record or subject."""

_DIAGNOSTIC_REFERENCE_PATTERN = rf"^sha256:(?:[0-9a-f]{{12}}|{HEX_PATTERN_64.removeprefix('^').removesuffix('$')})$"

type OperationDiagnosticReference = Annotated[
    str,
    Field(pattern=_DIAGNOSTIC_REFERENCE_PATTERN),
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


@dataclass(frozen=True, slots=True)
class OperationStoredInvocation:
    """Owner-only stored operands for fresh authorization, never a public projection."""

    identity: OperationIdentity
    request: OperationRequest[BaseModel] = field(repr=False)
    lifecycle: OperationLifecycle
    provenance: OperationAdmissionProvenance | None = field(default=None, repr=False)


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
    refusal_detail_ref: ContentDigest | None = None
    failure_error_code: OperationFailureErrorCode | None = None
    diagnostic_ref: OperationDiagnosticReference | None = None
    #: Encrypted public detail of the error that stopped a refused or failed executor.
    error_detail_ref: ContentDigest | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_terminal_references(self) -> OperationTerminalReceipt:
        validate_utc_aware(self.settled_at)
        if self.refusal_detail_ref is not None and self.condition is not OperationTerminalCondition.REFUSED:
            raise ValueError("refusal detail is valid only for a refused operation")
        if self.error_detail_ref is not None and (
            self.condition not in {OperationTerminalCondition.REFUSED, OperationTerminalCondition.FAILED}
            or self.refusal_detail_ref is not None
        ):
            raise ValueError("error detail is valid only for a refused or failed operation without refusal detail")
        validate_terminal_reference_meaning(
            condition=self.condition,
            result_ref=self.result_ref,
            refusal_ref=self.refusal_ref,
            failure_error_code=self.failure_error_code,
        )
        return self


def _validate_terminal_reference_relationship(
    *,
    condition: OperationTerminalCondition,
    result_ref: OperationReference | None,
    refusal_ref: OperationReference | None,
    failure_error_code: str | None,
) -> None:
    if condition is OperationTerminalCondition.SUCCEEDED:
        _validate_succeeded_terminal_references(result_ref=result_ref, refusal_ref=refusal_ref)
    elif condition is OperationTerminalCondition.REFUSED:
        _validate_refused_terminal_references(
            result_ref=result_ref,
            refusal_ref=refusal_ref,
            failure_error_code=failure_error_code,
        )
    elif refusal_ref is not None:
        raise ValueError("refusal reference is valid only for a refused operation")


def _validate_succeeded_terminal_references(
    *,
    result_ref: OperationReference | None,
    refusal_ref: OperationReference | None,
) -> None:
    if result_ref is None or refusal_ref is not None:
        raise ValueError("succeeded operation requires one result reference and forbids a refusal reference")


def _validate_refused_terminal_references(
    *,
    result_ref: OperationReference | None,
    refusal_ref: OperationReference | None,
    failure_error_code: str | None,
) -> None:
    if refusal_ref is None or result_ref is not None or failure_error_code is not None:
        raise ValueError("refused operation requires one refusal reference and forbids a result reference")


def _validate_terminal_failure_code(
    *,
    condition: OperationTerminalCondition,
    failure_error_code: str | None,
) -> None:
    if condition is not OperationTerminalCondition.FAILED and failure_error_code is not None:
        raise ValueError("failure error code is valid only for a failed operation")
    if failure_error_code is not None:
        from ...core.errors.error_codes import get_registered_error_code_by_code

        get_registered_error_code_by_code(failure_error_code)


def terminal_receipt_matches(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    subject_ref: str,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
) -> bool:
    """Return whether ``receipt`` settled this exact target with this condition and effect.

    Receipt validation already fixes which result, refusal and failure references
    accompany ``condition``. This adds only what the receipt cannot know: the
    invocation identity, the declared effect and the absence of a failure diagnostic.
    """
    return (
        receipt.identity.definition_id == definition_id
        and receipt.identity.subject_ref == subject_ref
        and receipt.condition is condition
        and receipt.effect is effect
        and receipt.diagnostic_ref is None
    )


def require_terminal_receipt_match(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    subject_ref: str,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    message: str,
) -> None:
    """Raise ``ValueError(message)`` unless :func:`terminal_receipt_matches` holds.

    The caller owns ``message`` because each projection names its own result in
    the refusal it surfaces.
    """
    if not terminal_receipt_matches(
        receipt,
        definition_id=definition_id,
        subject_ref=subject_ref,
        condition=condition,
        effect=effect,
    ):
        raise ValueError(message)


def require_terminal_receipt_match_any_effect(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    subject_ref: str,
    condition: OperationTerminalCondition,
    effects: frozenset[OperationEffect],
    message: str,
) -> None:
    """Raise ``ValueError(message)`` unless ``receipt`` matches with one of ``effects``.

    For an outcome whose published effect is not unique, such as a capture that
    stored nothing new yet refreshed the provider session.
    """
    if receipt.effect not in effects:
        raise ValueError(message)
    require_terminal_receipt_match(
        receipt,
        definition_id=definition_id,
        subject_ref=subject_ref,
        condition=condition,
        effect=receipt.effect,
        message=message,
    )


def require_succeeded_receipt_references(receipt: OperationTerminalReceipt, *, message: str) -> None:
    """Raise ``ValueError(message)`` unless ``receipt`` carries exactly a succeeded result's references.

    A succeeded receipt names its result and no refusal, refusal detail or
    failure code. Receipt validation already enforces this; checking it again
    keeps a receipt copied without validation from releasing a result.
    """
    if (
        receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
    ):
        raise ValueError(message)


def require_succeeded_terminal_receipt(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    subject_ref: str,
    effect: OperationEffect,
    message: str,
) -> None:
    """Raise ``ValueError(message)`` unless ``receipt`` is this target's succeeded settlement with ``effect``.

    Combines :func:`require_terminal_receipt_match` for the succeeded condition
    with :func:`require_succeeded_receipt_references`, so one refusal message
    covers both the receipt's identity and its result references.
    """
    require_terminal_receipt_match(
        receipt,
        definition_id=definition_id,
        subject_ref=subject_ref,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        message=message,
    )
    require_succeeded_receipt_references(receipt, message=message)


def refused_receipt_references_hold(receipt: OperationTerminalReceipt) -> bool:
    """Return whether ``receipt`` carries exactly a refused operation's references.

    A refused receipt names its refusal and no result or failure code, and never
    pairs refusal detail with error detail. Receipt validation already enforces
    this; checking it again keeps a receipt copied without validation from
    releasing a refusal.
    """
    return (
        receipt.refusal_ref is not None
        and receipt.result_ref is None
        and receipt.failure_error_code is None
        and (receipt.refusal_detail_ref is None or receipt.error_detail_ref is None)
    )


def validate_terminal_reference_meaning(
    *,
    condition: OperationTerminalCondition,
    result_ref: OperationReference | None,
    refusal_ref: OperationReference | None,
    failure_error_code: str | None = None,
) -> None:
    """Enforce the canonical terminal result/refusal relationship."""
    _validate_terminal_reference_relationship(
        condition=condition,
        result_ref=result_ref,
        refusal_ref=refusal_ref,
        failure_error_code=failure_error_code,
    )
    _validate_terminal_failure_code(condition=condition, failure_error_code=failure_error_code)


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
    @pydantic_validation_boundary
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
    "OperationFailureErrorCode",
    "OperationId",
    "OperationIdentity",
    "OperationReconciliationOutcome",
    "OperationReference",
    "OperationRequest",
    "OperationRevision",
    "OperationSnapshot",
    "OperationTerminalReceipt",
    "new_operation_id",
    "require_succeeded_receipt_references",
    "require_succeeded_terminal_receipt",
    "require_terminal_receipt_match",
    "require_terminal_receipt_match_any_effect",
    "terminal_receipt_matches",
]
