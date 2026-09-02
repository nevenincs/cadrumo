"""Application-owned durable operation lease contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, cast

from pydantic import BaseModel, Field, model_validator

from ....core.hashing import content_hash_hex
from ....core.hex import Hex64Str
from ....core.identity import ContentDigest
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.time.utc import validate_utc_aware
from ..models import OperationId

type OperationConflictScopeReference = Hex64Str


def operation_conflict_scope_reference(*, definition_id: str, subject_ref: str) -> OperationConflictScopeReference:
    """Derive the domain-separated definition-and-subject lease scope."""
    return content_hash_hex(
        {
            "schema_version": 1,
            "authority": "cadrumo.operation.conflict_scope",
            "definition_id": definition_id,
            "subject_ref": subject_ref,
        }
    )


type OperationLeaseToken = Hex64Str

_EVIDENCE_REF_PENDING = "0" * 64


def _raise_if(condition: bool, message: str) -> None:
    if condition:
        raise ValueError(message)


class OperationLeaseObservationDisposition(StrEnum):
    """Authoritative state of one operation lease at an observed instant."""

    ABSENT = "absent"
    ACTIVE = "active"
    EXPIRED = "expired"


class OperationLeaseDisposition(StrEnum):
    """Outcome of one durable operation-owner lease transition."""

    ACQUIRED = "acquired"
    RENEWED = "renewed"
    RELEASED = "released"
    CONFLICT = "conflict"
    EXPIRED = "expired"
    TAKEN_OVER = "taken_over"
    OWNER_LOST = "owner_lost"


class OperationOwnerLease(BaseModel):
    """Immutable proof that one supervisor owns an operation for a UTC window."""

    model_config = STRICT_FROZEN_CONFIG

    operation_id: OperationId
    scope_ref: OperationConflictScopeReference
    owner_id: Hex64Str
    token: OperationLeaseToken
    acquired_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _validate_window(self) -> OperationOwnerLease:
        validate_utc_aware(self.acquired_at)
        validate_utc_aware(self.expires_at)
        _raise_if(self.expires_at <= self.acquired_at, "operation owner lease must expire after acquisition")
        return self


def _lease_payload(lease: OperationOwnerLease | None) -> dict[str, object] | None:
    """Project one lease into the fixed JSON shape used for evidence identities."""
    return None if lease is None else cast(dict[str, object], lease.model_dump(mode="json"))


def _validate_evidence_ref(*, supplied: ContentDigest, expected: ContentDigest) -> None:
    """Reject caller-supplied evidence that does not name the transition payload."""
    _raise_if(
        supplied != _EVIDENCE_REF_PENDING and supplied != expected,
        "operation lease evidence reference does not match the canonical transition payload",
    )


class OperationLeaseObservation(BaseModel):
    """Stable, targetable lease state observed at the caller-supplied UTC instant."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    scope_ref: OperationConflictScopeReference
    operation_id: OperationId
    disposition: OperationLeaseObservationDisposition
    observed_at: datetime
    current: OperationOwnerLease | None = None
    evidence_ref: ContentDigest = Field(default=_EVIDENCE_REF_PENDING)

    @model_validator(mode="after")
    def _validate_observation(self) -> OperationLeaseObservation:
        validate_utc_aware(self.observed_at)
        _validate_observation_witness(self)
        expected = content_hash_hex(
            {
                "schema_version": self.schema_version,
                "transition": "operation_lease_observation",
                "scope_ref": self.scope_ref,
                "operation_id": self.operation_id,
                "disposition": self.disposition.value,
                "observed_at": self.observed_at.isoformat(),
                "current": _lease_payload(self.current),
            }
        )
        _validate_evidence_ref(supplied=self.evidence_ref, expected=expected)
        object.__setattr__(self, "evidence_ref", expected)
        return self


def _validate_observation_witness(observation: OperationLeaseObservation) -> None:
    """Bind an observation disposition to its optional exact lease witness."""
    current = observation.current
    if observation.disposition is OperationLeaseObservationDisposition.ABSENT:
        _raise_if(current is not None, "absent lease observation forbids a current lease")
        return
    if current is None:
        raise ValueError(f"{observation.disposition.value} lease observation requires a current lease")
    _raise_if(
        current.scope_ref != observation.scope_ref, "lease observation current lease does not match the conflict scope"
    )
    _raise_if(
        current.acquired_at > observation.observed_at, "lease observation cannot precede current lease acquisition"
    )
    if observation.disposition is OperationLeaseObservationDisposition.ACTIVE:
        _raise_if(
            current.expires_at <= observation.observed_at,
            "active lease observation requires an unexpired current lease",
        )
        return
    _raise_if(
        current.expires_at > observation.observed_at, "expired lease observation requires an expired current lease"
    )


class OperationLeaseResult(BaseModel):
    """Stable evidence for every durable lease transition or refusal."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    scope_ref: OperationConflictScopeReference
    operation_id: OperationId
    disposition: OperationLeaseDisposition
    observed_at: datetime
    predecessor: OperationOwnerLease | None = None
    current: OperationOwnerLease | None = None
    evidence_ref: ContentDigest = Field(default=_EVIDENCE_REF_PENDING)

    @model_validator(mode="after")
    def _validate_shape(self) -> OperationLeaseResult:
        validate_utc_aware(self.observed_at)
        _validate_result_witnesses(self)
        _validate_result_transition(self)
        expected = content_hash_hex(
            {
                "schema_version": self.schema_version,
                "transition": "operation_lease_result",
                "scope_ref": self.scope_ref,
                "operation_id": self.operation_id,
                "disposition": self.disposition.value,
                "observed_at": self.observed_at.isoformat(),
                "predecessor": _lease_payload(self.predecessor),
                "current": _lease_payload(self.current),
            }
        )
        _validate_evidence_ref(supplied=self.evidence_ref, expected=expected)
        object.__setattr__(self, "evidence_ref", expected)
        return self


_RESULT_CURRENT_REQUIRED = frozenset(
    {
        OperationLeaseDisposition.ACQUIRED,
        OperationLeaseDisposition.RENEWED,
        OperationLeaseDisposition.CONFLICT,
        OperationLeaseDisposition.TAKEN_OVER,
    }
)
_RESULT_PREDECESSOR_REQUIRED = frozenset(
    {
        OperationLeaseDisposition.RENEWED,
        OperationLeaseDisposition.RELEASED,
        OperationLeaseDisposition.EXPIRED,
        OperationLeaseDisposition.TAKEN_OVER,
        OperationLeaseDisposition.OWNER_LOST,
    }
)
_RESULT_PREDECESSOR_FORBIDDEN = frozenset({OperationLeaseDisposition.ACQUIRED, OperationLeaseDisposition.CONFLICT})
_RESULT_CURRENT_FORBIDDEN = frozenset({OperationLeaseDisposition.RELEASED, OperationLeaseDisposition.EXPIRED})


def _validate_result_witnesses(result: OperationLeaseResult) -> None:
    """Validate disposition witness presence and target every witness to one operation."""
    _validate_result_witness_presence(result)
    _validate_result_witness_identity(result)


def _validate_result_witness_presence(result: OperationLeaseResult) -> None:
    disposition = result.disposition.value
    _raise_if(
        result.disposition in _RESULT_CURRENT_REQUIRED and result.current is None,
        f"{disposition} lease result requires the current lease",
    )
    _raise_if(
        result.disposition in _RESULT_PREDECESSOR_REQUIRED and result.predecessor is None,
        f"{disposition} lease result requires predecessor evidence",
    )
    _raise_if(
        result.disposition in _RESULT_PREDECESSOR_FORBIDDEN and result.predecessor is not None,
        f"{disposition} lease result forbids predecessor evidence",
    )
    _raise_if(
        result.disposition in _RESULT_CURRENT_FORBIDDEN and result.current is not None,
        f"{disposition} lease result forbids a current lease",
    )


def _validate_result_witness_identity(result: OperationLeaseResult) -> None:
    for witness in (result.predecessor, result.current):
        if witness is None:
            continue
        _raise_if(witness.scope_ref != result.scope_ref, "lease transition witness does not match the conflict scope")
        _raise_if(
            witness.acquired_at > result.observed_at, "lease transition cannot precede a lease witness acquisition"
        )


def _validate_result_transition(result: OperationLeaseResult) -> None:
    """Validate the exact transition law named by one result disposition."""
    match result.disposition:
        case OperationLeaseDisposition.ACQUIRED:
            _validate_acquisition(result)
        case OperationLeaseDisposition.RENEWED:
            _validate_renewal(result)
        case OperationLeaseDisposition.CONFLICT:
            _validate_active_current(result)
        case OperationLeaseDisposition.EXPIRED:
            _validate_expired_predecessor(result)
        case OperationLeaseDisposition.TAKEN_OVER:
            _validate_takeover(result)
        case OperationLeaseDisposition.OWNER_LOST:
            _validate_owner_loss(result)
        case OperationLeaseDisposition.RELEASED:
            _validate_release(result)


def _required_current(result: OperationLeaseResult) -> OperationOwnerLease:
    """Return the current lease witness this disposition requires.

    ``OperationLeaseResult`` leaves both witnesses optional because a given
    disposition carries only the ones it proves. A disposition that reaches its
    validator without its witness is a malformed result, so it is refused --
    not asserted, because ``assert`` is stripped under ``python -O`` and the
    lease invariant would then go unchecked in an optimised run.
    """
    if result.current is None:
        raise ValueError(f"{result.disposition.value} lease result requires a current lease witness")
    return result.current


def _required_predecessor(result: OperationLeaseResult) -> OperationOwnerLease:
    """Return the predecessor lease witness this disposition requires."""
    if result.predecessor is None:
        raise ValueError(f"{result.disposition.value} lease result requires a predecessor lease witness")
    return result.predecessor


def _validate_acquisition(result: OperationLeaseResult) -> None:
    """Ensure an absent-only acquisition starts and remains live at observation."""
    current = _required_current(result)
    _raise_if(current.operation_id != result.operation_id, "acquired lease must match the operation identity")
    _raise_if(current.acquired_at != result.observed_at, "acquired lease must begin at its observed time")
    _validate_active_current(result)


def _validate_renewal(result: OperationLeaseResult) -> None:
    """Ensure a renewal preserves exact ownership before the predecessor expires."""
    predecessor, current = _required_predecessor(result), _required_current(result)
    _raise_if(
        predecessor.operation_id != result.operation_id or current.operation_id != result.operation_id,
        "lease renewal must preserve the operation identity",
    )
    _raise_if(
        (current.owner_id, current.token, current.acquired_at)
        != (predecessor.owner_id, predecessor.token, predecessor.acquired_at),
        "lease renewal must preserve operation, owner, token, and acquisition identity",
    )
    _raise_if(result.observed_at >= predecessor.expires_at, "lease renewal must occur before predecessor expiry")
    _raise_if(current.expires_at <= predecessor.expires_at, "lease renewal must extend the expiry")


def _validate_active_current(result: OperationLeaseResult) -> None:
    """Ensure the current witness remains live at the observed instant."""
    _raise_if(
        _required_current(result).expires_at <= result.observed_at,
        "lease result requires an active current lease",
    )


def _validate_expired_predecessor(result: OperationLeaseResult) -> None:
    """Ensure expiry evidence carries a predecessor expired at observation."""
    _raise_if(
        _required_predecessor(result).expires_at > result.observed_at,
        "lease result requires an expired predecessor",
    )


def _validate_takeover(result: OperationLeaseResult) -> None:
    """Ensure takeover uses a proved expired predecessor and a new live owner."""
    predecessor, current = _required_predecessor(result), _required_current(result)
    _raise_if(current.operation_id != result.operation_id, "lease takeover successor must match the operation identity")
    _validate_expired_predecessor(result)
    _raise_if(
        current.owner_id == predecessor.owner_id or current.token == predecessor.token,
        "lease takeover requires a new owner and token",
    )
    _raise_if(current.acquired_at != result.observed_at, "lease takeover successor must begin at its observed time")
    _validate_active_current(result)


def _validate_owner_loss(result: OperationLeaseResult) -> None:
    """Require a stale predecessor and, when present, a distinct replacement witness."""
    predecessor = _required_predecessor(result)
    _raise_if(
        predecessor.operation_id != result.operation_id,
        "owner-lost predecessor must match the operation identity",
    )
    _raise_if(
        result.current is not None and result.current == predecessor,
        "owner-lost result cannot report the exact predecessor as current",
    )


def _validate_release(result: OperationLeaseResult) -> None:
    """Bind a release refusal or transition to the exact releasing operation."""
    _raise_if(
        _required_predecessor(result).operation_id != result.operation_id,
        "released predecessor must match the operation identity",
    )


__all__ = [
    "OperationConflictScopeReference",
    "OperationLeaseDisposition",
    "OperationLeaseObservation",
    "OperationLeaseObservationDisposition",
    "OperationLeaseResult",
    "OperationLeaseToken",
    "OperationOwnerLease",
    "operation_conflict_scope_reference",
]
