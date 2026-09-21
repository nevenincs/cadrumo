"""Application contract for safe withholding-observation window mutations.

The two established projection stores deliberately keep their distinct legal
meanings.  This module owns only the command vocabulary and the active-window
authority which makes a coordinated change to those projections safe.
"""

from __future__ import annotations

import json
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import sha256_hex
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from .retenciones import RetencionObservation

ABSENT_WITHHOLDING_GENERATION_ID = "0" * 64
_MAX_APPEND_ATTEMPTS = 4
_MAX_REPLAY_RESOLUTION_ATTEMPTS = 2


class WithholdingMutationMode(StrEnum):
    """Explicit write intent for a withholding window."""

    APPEND = "append"
    REPLACE = "replace"
    CLEAR = "clear"


class WithholdingProjectionRole(StrEnum):
    """The accepted distinct projection meanings retained by this workflow."""

    RETENCION = "retencion"
    PERCEPCION = "percepcion"


class WithholdingObservationMutationError(ValueError):
    """A safe, payload-free refusal at the withholding mutation boundary."""

    def __init__(self, code: str) -> None:
        """Build a payload-free stable refusal."""
        self.code = code
        super().__init__(f"withholding observation mutation refused: {code}")


class WithholdingWindowScope(BaseModel):
    """One logical withholding window; the period is its sole year authority."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    period: Period

    @property
    def token(self) -> str:
        """Return the portable logical scope token."""
        return f"withholding-window:v1:{self.modelo}:{self.period.filing_year}:{self.period.registry_token}"


class WithholdingWindowBaseline(BaseModel):
    """Public logical generation token used by replace and clear."""

    model_config = STRICT_FROZEN_CONFIG

    scope_token: str = Field(min_length=1)
    generation_id: str = Field(min_length=64, max_length=64)


class WithholdingProjectionIdentity(BaseModel):
    """Stable identity of exactly one retained projection row."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: str = Field(min_length=1, max_length=64)
    source_object_id: str = Field(min_length=1, max_length=128)
    source_revision_id: str = Field(min_length=1, max_length=128)
    recognition_event_id: str = Field(min_length=1, max_length=128)
    settlement_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    allocation_id: str = Field(min_length=1, max_length=128)
    projection_role: WithholdingProjectionRole

    @property
    def token(self) -> str:
        """Return the stable liability identity, independent of later settlement."""
        identity = self.model_dump(mode="json", exclude={"settlement_event_id"})
        return sha256_hex(_canonical_json(identity).encode("utf-8"))


class SourceLiabilitySnapshot(BaseModel):
    """The canonical, revision-bound limit for allocations from one source."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: str = Field(min_length=1, max_length=64)
    source_object_id: str = Field(min_length=1, max_length=128)
    source_revision_id: str = Field(min_length=1, max_length=128)
    currency: Literal["EUR"] = "EUR"
    liability_base: Decimal = Field(ge=Decimal("0"))
    liability_withholding: Decimal = Field(ge=Decimal("0"))
    liability_settlement: Decimal = Field(ge=Decimal("0"))

    @property
    def source_token(self) -> str:
        """Return the guard scope, deliberately independent of revisions."""
        return sha256_hex(
            _canonical_json({"source_kind": self.source_kind, "source_object_id": self.source_object_id}).encode(
                "utf-8"
            )
        )


class EconomicAllocation(BaseModel):
    """One economic allocation counted once even when it has several roles."""

    model_config = STRICT_FROZEN_CONFIG

    liability: SourceLiabilitySnapshot
    recognition_event_id: str = Field(min_length=1, max_length=128)
    allocation_id: str = Field(min_length=1, max_length=128)
    allocated_base: Decimal = Field(ge=Decimal("0"))
    allocated_withholding: Decimal = Field(ge=Decimal("0"))
    allocated_settlement: Decimal = Field(ge=Decimal("0"))

    @property
    def guard_identity(self) -> str:
        """Return the allocation identity without revision or settlement IDs."""
        return sha256_hex(
            _canonical_json(
                {
                    "source_kind": self.liability.source_kind,
                    "source_object_id": self.liability.source_object_id,
                    "recognition_event_id": self.recognition_event_id,
                    "allocation_id": self.allocation_id,
                }
            ).encode("utf-8")
        )


class WithholdingProjectionEntry(BaseModel):
    """One active projection, identified independently from recipient grouping."""

    model_config = STRICT_FROZEN_CONFIG

    identity: WithholdingProjectionIdentity
    allocation: EconomicAllocation
    retencion: RetencionObservation | None = None
    percepcion: WithholdingObservation | None = None

    @model_validator(mode="after")
    def _has_exactly_one_projection(self) -> WithholdingProjectionEntry:
        if (self.retencion is None) == (self.percepcion is None):
            raise ValueError("one and only one withholding projection is required")
        if self.retencion is not None:
            expected_role = WithholdingProjectionRole.RETENCION
            source_object_id = self.retencion.source_object_id
        else:
            if self.percepcion is None:
                raise ValueError("one and only one withholding projection is required")
            expected_role = WithholdingProjectionRole.PERCEPCION
            source_object_id = self.percepcion.source_id
        if self.identity.projection_role is not expected_role:
            raise ValueError("projection role must match its payload")
        if source_object_id != self.identity.source_object_id:
            raise ValueError("projection source must match its composite identity")
        if (
            self.allocation.liability.source_kind != self.identity.source_kind
            or self.allocation.liability.source_object_id != self.identity.source_object_id
            or self.allocation.liability.source_revision_id != self.identity.source_revision_id
            or self.allocation.recognition_event_id != self.identity.recognition_event_id
            or self.allocation.allocation_id != self.identity.allocation_id
        ):
            raise ValueError("economic allocation must match its projection identity")
        if self.retencion is not None and (
            self.retencion.taxable_base != self.allocation.allocated_base
            or self.retencion.retencion_amount != self.allocation.allocated_withholding
        ):
            raise ValueError("retencion projection amounts must match economic allocation")
        if self.percepcion is not None and (
            self.percepcion.percibido_dinerario != self.allocation.allocated_base
            or self.percepcion.retencion_practicada != self.allocation.allocated_withholding
        ):
            raise ValueError("percepcion projection amounts must match economic allocation")
        return self


class WithholdingMutationEnvelope(BaseModel):
    """Explicit mutation intent. ``None`` at the service means no mutation."""

    model_config = STRICT_FROZEN_CONFIG

    scope: WithholdingWindowScope
    mode: WithholdingMutationMode
    idempotency_key: str = Field(min_length=1, max_length=128)
    entries: tuple[WithholdingProjectionEntry, ...] = ()
    baseline: WithholdingWindowBaseline | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=500)
    supersedes_generation_id: str | None = Field(default=None, min_length=64, max_length=64)

    @model_validator(mode="after")
    def _validate_shape(self) -> WithholdingMutationEnvelope:
        if self.baseline is not None and self.baseline.scope_token != self.scope.token:
            raise ValueError("withholding baseline belongs to another window")
        if self.mode is WithholdingMutationMode.APPEND:
            if not self.entries or self.baseline is not None:
                raise ValueError("append requires entries and no baseline")
        elif self.mode is WithholdingMutationMode.REPLACE:
            if not self.entries or self.baseline is None:
                raise ValueError("replace requires entries and an exact baseline")
        else:
            if self.entries or self.baseline is None or not self.reason:
                raise ValueError("clear requires a baseline, a reason, and no entries")
        if self.supersedes_generation_id is not None and (
            self.mode is not WithholdingMutationMode.REPLACE or self.baseline is None or not self.reason
        ):
            raise ValueError("a correction requires baseline-guarded replace and a reason")
        if len({entry.identity.token for entry in self.entries}) != len(self.entries):
            raise ValueError("projection identities must be unique within one command")
        return self

    @property
    def command_digest(self) -> str:
        """Return the canonical digest used for idempotency comparison."""
        value = self.model_dump(mode="json")
        value["entries"] = sorted(value["entries"], key=lambda item: _identity_json_token(item["identity"]))
        return sha256_hex(_canonical_json(value).encode("utf-8"))


class WithholdingWindowState(BaseModel):
    """Persisted active set plus an adapter-opaque CAS token."""

    model_config = STRICT_FROZEN_CONFIG

    scope: WithholdingWindowScope
    baseline: WithholdingWindowBaseline
    entries: tuple[WithholdingProjectionEntry, ...] = ()
    generation: int = Field(default=0, ge=0)
    persistence_revision_id: str = Field(min_length=64, max_length=64)


class WithholdingMutationResult(BaseModel):
    """Safe result metadata; it deliberately contains no financial payload."""

    model_config = STRICT_FROZEN_CONFIG

    baseline: WithholdingWindowBaseline
    replayed: bool = False


class WithholdingIdempotencyReplay(BaseModel):
    """Immutable replay claim, including the generation it originally committed."""

    model_config = STRICT_FROZEN_CONFIG

    command_digest: str = Field(min_length=64, max_length=64)
    baseline: WithholdingWindowBaseline


class WithholdingGenerationAudit(BaseModel):
    """A queryable immutable generation record without transport metadata."""

    model_config = STRICT_FROZEN_CONFIG

    baseline: WithholdingWindowBaseline
    parent_generation_id: str = Field(min_length=64, max_length=64)
    mode: WithholdingMutationMode
    reason: str | None = None
    supersedes_generation_id: str | None = None


class WithholdingObservationMutationRepository(Protocol):
    """Atomic persistence capability implemented outside the application layer."""

    def load_window(self, scope: WithholdingWindowScope) -> WithholdingWindowState:
        """Load active evidence and an adapter-opaque CAS token."""
        ...

    def idempotency_replay(self, scope: WithholdingWindowScope, key: str) -> WithholdingIdempotencyReplay | None:
        """Return the immutable result of a previously committed replay key."""
        ...

    def load_generation(self, scope: WithholdingWindowScope, generation_id: str) -> WithholdingGenerationAudit | None:
        """Load one immutable generation audit record for an exact window."""
        ...

    def commit_transition(
        self,
        *,
        predecessor: WithholdingWindowState,
        successor: tuple[WithholdingProjectionEntry, ...],
        envelope: WithholdingMutationEnvelope,
    ) -> WithholdingWindowBaseline:
        """Atomically commit a validated successor state."""
        ...


class WithholdingObservationService:
    """Apply explicit withholding-window mutations through one atomic port."""

    def __init__(self, repository: WithholdingObservationMutationRepository) -> None:
        """Bind this service to its one persistence capability."""
        self._repository = repository

    def apply(self, envelope: WithholdingMutationEnvelope | None) -> WithholdingMutationResult | None:
        """Apply a command, or leave evidence entirely unchanged when omitted."""
        if envelope is None:
            return None
        attempts = (
            _MAX_APPEND_ATTEMPTS if envelope.mode is WithholdingMutationMode.APPEND else _MAX_REPLAY_RESOLUTION_ATTEMPTS
        )
        for attempt in range(attempts):
            state = self._repository.load_window(envelope.scope)
            replay = self._repository.idempotency_replay(envelope.scope, envelope.idempotency_key)
            if replay is not None:
                if replay.command_digest != envelope.command_digest:
                    raise WithholdingObservationMutationError("idempotency_conflict")
                return WithholdingMutationResult(baseline=replay.baseline, replayed=True)
            if envelope.mode is not WithholdingMutationMode.APPEND and envelope.baseline != state.baseline:
                raise WithholdingObservationMutationError("stale_baseline")
            try:
                successor = _successor(state.entries, envelope)
                baseline = self._repository.commit_transition(
                    predecessor=state,
                    successor=successor,
                    envelope=envelope,
                )
                return WithholdingMutationResult(baseline=baseline)
            except WithholdingObservationMutationError as exc:
                if exc.code != "concurrent_write":
                    raise
                if attempt + 1 == attempts:
                    raise
        raise AssertionError("bounded append loop must return or raise")

    def read_window(self, scope: WithholdingWindowScope) -> WithholdingWindowState:
        """Read active evidence without causing a mutation."""
        return self._repository.load_window(scope)

    def read_generation(self, scope: WithholdingWindowScope, generation_id: str) -> WithholdingGenerationAudit | None:
        """Read immutable correction/audit history for an exact window."""
        return self._repository.load_generation(scope, generation_id)


def _successor(
    current: tuple[WithholdingProjectionEntry, ...],
    envelope: WithholdingMutationEnvelope,
) -> tuple[WithholdingProjectionEntry, ...]:
    if envelope.mode is WithholdingMutationMode.CLEAR:
        return ()
    if envelope.mode is WithholdingMutationMode.REPLACE:
        return tuple(sorted(envelope.entries, key=lambda entry: entry.identity.token))
    existing = {entry.identity.token for entry in current}
    introduced = {entry.identity.token for entry in envelope.entries}
    if existing & introduced:
        raise WithholdingObservationMutationError("projection_identity_conflict")
    return tuple(sorted((*current, *envelope.entries), key=lambda entry: entry.identity.token))


def _identity_json_token(value: object) -> str:
    return _canonical_json(value)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


__all__ = [
    "ABSENT_WITHHOLDING_GENERATION_ID",
    "EconomicAllocation",
    "SourceLiabilitySnapshot",
    "WithholdingGenerationAudit",
    "WithholdingIdempotencyReplay",
    "WithholdingMutationEnvelope",
    "WithholdingMutationMode",
    "WithholdingMutationResult",
    "WithholdingObservationMutationError",
    "WithholdingObservationMutationRepository",
    "WithholdingObservationService",
    "WithholdingProjectionEntry",
    "WithholdingProjectionIdentity",
    "WithholdingProjectionRole",
    "WithholdingWindowBaseline",
    "WithholdingWindowScope",
    "WithholdingWindowState",
]
