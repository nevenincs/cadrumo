"""Atomic encrypted persistence adapter for withholding observation windows."""

from __future__ import annotations

import json
from collections.abc import Iterable
from decimal import Decimal

from pydantic import BaseModel, Field

from ....application.aggregation.withholding_observation_service import (
    ABSENT_WITHHOLDING_GENERATION_ID,
    EconomicAllocation,
    SourceLiabilitySnapshot,
    WithholdingGenerationAudit,
    WithholdingIdempotencyReplay,
    WithholdingMutationEnvelope,
    WithholdingMutationMode,
    WithholdingObservationMutationError,
    WithholdingProjectionEntry,
    WithholdingWindowBaseline,
    WithholdingWindowScope,
    WithholdingWindowState,
)
from ....core.aggregation import AggregationCaptureKind
from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID, SecureObjectWrite
from ....core.time.clock import now
from ..storage.envelope.contract import parameterized_envelope_type
from ..storage.errors import SecureObjectRevisionConflictError, StorageError
from ..storage.secure_object_namespaces import WITHHOLDING_WORKFLOW_NAMESPACE
from ..storage.sql.secure_object_records import SecureObjectDeletion
from ..storage.sql.secure_objects import SecureObjectRepository
from .percepciones_observations import PercepcionObservationRepositoryAdapter
from .retencion_observations import RetencionObservationRepositoryAdapter


class _WindowHead(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    scope: WithholdingWindowScope
    generation: int = Field(ge=1)
    generation_id: str = Field(min_length=64, max_length=64)
    parent_generation_id: str = Field(min_length=64, max_length=64)
    entries: tuple[WithholdingProjectionEntry, ...] = ()
    projection_digest: str = Field(min_length=64, max_length=64)


class _GenerationRecord(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    scope: WithholdingWindowScope
    generation: int = Field(ge=1)
    generation_id: str = Field(min_length=64, max_length=64)
    parent_generation_id: str = Field(min_length=64, max_length=64)
    command_digest: str = Field(min_length=64, max_length=64)
    mode: str = Field(min_length=1)
    reason: str | None = None
    supersedes_generation_id: str | None = None
    entries: tuple[WithholdingProjectionEntry, ...] = ()
    projection_digest: str = Field(min_length=64, max_length=64)


class _IdempotencyRecord(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    scope_token: str = Field(min_length=1)
    key_digest: str = Field(min_length=64, max_length=64)
    command_digest: str = Field(min_length=64, max_length=64)
    generation_id: str = Field(min_length=64, max_length=64)


class _SourceLiabilityGuard(BaseModel):
    """CAS-protected derived index of all active source allocations."""

    model_config = STRICT_FROZEN_CONFIG

    source_token: str = Field(min_length=64, max_length=64)
    liability: SourceLiabilitySnapshot
    allocations: tuple[EconomicAllocation, ...] = ()


class WithholdingObservationWorkflowAdapter:
    """Co-batch immutable workflow control rows and both accepted projections."""

    def __init__(
        self,
        *,
        objects: SecureObjectRepository,
        retenciones: RetencionObservationRepositoryAdapter,
        percepciones: PercepcionObservationRepositoryAdapter,
    ) -> None:
        """Bind all workflow rows to one secure-object transaction boundary."""
        if retenciones.secure_object_repository is not objects or percepciones.secure_object_repository is not objects:
            raise ValueError("withholding workflow projections must share one secure-object repository")
        self._objects = objects
        self._retenciones = retenciones
        self._percepciones = percepciones

    def load_window(self, scope: WithholdingWindowScope) -> WithholdingWindowState:
        """Load and cross-check an active window and its projection rows."""
        record = self._objects.load(
            WITHHOLDING_WORKFLOW_NAMESPACE.namespace,
            _head_key(scope),
            expected_class=WITHHOLDING_WORKFLOW_NAMESPACE.sensitivity,
            max_supported_version=WITHHOLDING_WORKFLOW_NAMESPACE.schema_version,
        )
        if record is None:
            if tuple(self._projection_payloads(scope)):
                raise WithholdingObservationMutationError("unsupported_mixed_legacy_state")
            return WithholdingWindowState(
                scope=scope,
                baseline=WithholdingWindowBaseline(
                    scope_token=scope.token,
                    generation_id=ABSENT_WITHHOLDING_GENERATION_ID,
                ),
                persistence_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
            )
        head = _read_envelope(record.payload, _WindowHead)
        if head.scope != scope:
            raise WithholdingObservationMutationError("window_head_identity_mismatch")
        expected = {entry.identity.token: entry for entry in head.entries}
        actual = tuple(self._projection_payloads(scope))
        if len(actual) != len(expected):
            raise WithholdingObservationMutationError("projection_integrity_failure")
        for token, retencion, percepcion in actual:
            entry = expected.get(token)
            if entry is None or entry.retencion != retencion or entry.percepcion != percepcion:
                raise WithholdingObservationMutationError("projection_integrity_failure")
        if _entries_digest(head.entries) != head.projection_digest:
            raise WithholdingObservationMutationError("projection_integrity_failure")
        return WithholdingWindowState(
            scope=scope,
            baseline=WithholdingWindowBaseline(scope_token=scope.token, generation_id=head.generation_id),
            entries=head.entries,
            generation=head.generation,
            persistence_revision_id=record.revision_id,
        )

    def idempotency_replay(self, scope: WithholdingWindowScope, key: str) -> WithholdingIdempotencyReplay | None:
        """Return the immutable committed result for a replay key, if present."""
        record = self._objects.load(
            WITHHOLDING_WORKFLOW_NAMESPACE.namespace,
            _idempotency_key(scope, key),
            expected_class=WITHHOLDING_WORKFLOW_NAMESPACE.sensitivity,
            max_supported_version=WITHHOLDING_WORKFLOW_NAMESPACE.schema_version,
        )
        if record is None:
            return None
        idempotency = _read_envelope(record.payload, _IdempotencyRecord)
        if idempotency.scope_token != scope.token:
            raise WithholdingObservationMutationError("idempotency_identity_mismatch")
        return WithholdingIdempotencyReplay(
            command_digest=idempotency.command_digest,
            baseline=WithholdingWindowBaseline(
                scope_token=scope.token,
                generation_id=idempotency.generation_id,
            ),
        )

    def load_generation(self, scope: WithholdingWindowScope, generation_id: str) -> WithholdingGenerationAudit | None:
        """Load one immutable generation record, refusing a foreign scope."""
        record = self._objects.load(
            WITHHOLDING_WORKFLOW_NAMESPACE.namespace,
            _generation_key(scope, generation_id),
            expected_class=WITHHOLDING_WORKFLOW_NAMESPACE.sensitivity,
            max_supported_version=WITHHOLDING_WORKFLOW_NAMESPACE.schema_version,
        )
        if record is None:
            return None
        generation = _read_envelope(record.payload, _GenerationRecord)
        if generation.scope != scope or generation.generation_id != generation_id:
            raise WithholdingObservationMutationError("generation_identity_mismatch")
        return WithholdingGenerationAudit(
            baseline=WithholdingWindowBaseline(scope_token=scope.token, generation_id=generation.generation_id),
            parent_generation_id=generation.parent_generation_id,
            mode=WithholdingMutationMode(generation.mode),
            reason=generation.reason,
            supersedes_generation_id=generation.supersedes_generation_id,
        )

    def commit_transition(
        self,
        *,
        predecessor: WithholdingWindowState,
        successor: tuple[WithholdingProjectionEntry, ...],
        envelope: WithholdingMutationEnvelope,
    ) -> WithholdingWindowBaseline:
        """Commit the successor head, audit records, and projections in one batch."""
        if predecessor.scope != envelope.scope:
            raise WithholdingObservationMutationError("window_scope_mismatch")
        if (
            envelope.supersedes_generation_id is not None
            and self.load_generation(envelope.scope, envelope.supersedes_generation_id) is None
        ):
            raise WithholdingObservationMutationError("unknown_superseded_generation")
        generation = predecessor.generation + 1
        digest = _entries_digest(successor)
        generation_id = sha256_hex(
            f"{predecessor.baseline.generation_id}:{envelope.command_digest}:{digest}".encode(UTF_8_ENCODING),
        )
        head = _WindowHead(
            scope=envelope.scope,
            generation=generation,
            generation_id=generation_id,
            parent_generation_id=predecessor.baseline.generation_id,
            entries=successor,
            projection_digest=digest,
        )
        generation_record = _GenerationRecord(
            scope=envelope.scope,
            generation=generation,
            generation_id=generation_id,
            parent_generation_id=predecessor.baseline.generation_id,
            command_digest=envelope.command_digest,
            mode=envelope.mode.value,
            reason=envelope.reason,
            supersedes_generation_id=envelope.supersedes_generation_id,
            entries=successor,
            projection_digest=digest,
        )
        idempotency = _IdempotencyRecord(
            scope_token=envelope.scope.token,
            key_digest=_digest(envelope.idempotency_key),
            command_digest=envelope.command_digest,
            generation_id=generation_id,
        )
        guard_writes = self._guard_writes(predecessor.entries, successor)
        writes = [
            _control_write(_head_key(envelope.scope), head, predecessor.persistence_revision_id),
            _control_write(
                _generation_key(envelope.scope, generation_id),
                generation_record,
                ABSENT_SECURE_OBJECT_REVISION_ID,
            ),
            _control_write(
                _idempotency_key(envelope.scope, envelope.idempotency_key),
                idempotency,
                ABSENT_SECURE_OBJECT_REVISION_ID,
            ),
            *guard_writes,
        ]
        deletions: list[SecureObjectDeletion] = []
        for entry in successor:
            if entry.retencion is not None:
                writes.append(
                    self._retenciones.to_secure_object_write(
                        self._retenciones.build_observation_payload(
                            modelo=envelope.scope.modelo,
                            filing_year=envelope.scope.period.filing_year,
                            period=envelope.scope.period,
                            observation=entry.retencion,
                            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
                            projection_identity=entry.identity.token,
                        ),
                    ),
                )
            if entry.percepcion is not None:
                writes.append(
                    self._percepciones.to_secure_object_write(
                        self._percepciones.build_observation_payload(
                            modelo=envelope.scope.modelo,
                            filing_year=envelope.scope.period.filing_year,
                            period=envelope.scope.period,
                            observation=entry.percepcion,
                            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
                            projection_identity=entry.identity.token,
                        ),
                    ),
                )
        successor_ids = {entry.identity.token for entry in successor}
        for entry in predecessor.entries:
            if entry.identity.token in successor_ids:
                continue
            if entry.retencion is not None:
                deletions.append(
                    self._retenciones.to_secure_object_deletion(self._retencion_key(envelope.scope, entry))
                )
            if entry.percepcion is not None:
                deletions.append(
                    self._percepciones.to_secure_object_deletion(self._percepcion_key(envelope.scope, entry))
                )
        try:
            self._objects.apply_batch(tuple(writes), tuple(deletions))
        except SecureObjectRevisionConflictError as exc:
            raise WithholdingObservationMutationError("concurrent_write") from exc
        except StorageError as exc:
            raise WithholdingObservationMutationError("persistence_failure") from exc
        return WithholdingWindowBaseline(scope_token=envelope.scope.token, generation_id=generation_id)

    def _guard_writes(
        self,
        predecessor: tuple[WithholdingProjectionEntry, ...],
        successor: tuple[WithholdingProjectionEntry, ...],
    ) -> tuple[SecureObjectWrite, ...]:
        """Prepare every affected source guard with the same batch CAS as its head.

        A guard is a derived encrypted workflow index, never an independent
        authority.  Removing the current window's active economic allocations
        before adding its successor makes replace/clear release capacity while
        keeping all other windows in the same source total.
        """
        old_by_source = _allocations_by_source(predecessor)
        new_by_source = _allocations_by_source(successor)
        writes: list[SecureObjectWrite] = []
        for source_token in sorted(set(old_by_source) | set(new_by_source)):
            record = self._objects.load(
                WITHHOLDING_WORKFLOW_NAMESPACE.namespace,
                _guard_key(source_token),
                expected_class=WITHHOLDING_WORKFLOW_NAMESPACE.sensitivity,
                max_supported_version=WITHHOLDING_WORKFLOW_NAMESPACE.schema_version,
            )
            old = old_by_source.get(source_token, ())
            introduced = new_by_source.get(source_token, ())
            if record is None:
                if old:
                    raise WithholdingObservationMutationError("liability_guard_integrity_failure")
                prior_allocations: tuple[EconomicAllocation, ...] = ()
                prior_liability = _single_liability(introduced)
                expected_revision_id = ABSENT_SECURE_OBJECT_REVISION_ID
            else:
                guard = _read_envelope(record.payload, _SourceLiabilityGuard)
                if guard.source_token != source_token:
                    raise WithholdingObservationMutationError("liability_guard_integrity_failure")
                _validate_guard_allocations(guard)
                prior_allocations = guard.allocations
                prior_liability = guard.liability
                expected_revision_id = record.revision_id

            old_by_identity = {item.guard_identity: item for item in old}
            active_by_identity = {item.guard_identity: item for item in prior_allocations}
            for identity, allocation in old_by_identity.items():
                if active_by_identity.get(identity) != allocation:
                    raise WithholdingObservationMutationError("liability_guard_integrity_failure")
                del active_by_identity[identity]

            next_liability = prior_liability
            if introduced:
                introduced_liability = _single_liability(introduced)
                if active_by_identity and introduced_liability != prior_liability:
                    raise WithholdingObservationMutationError("contradictory_liability_snapshot")
                next_liability = introduced_liability
                for allocation in introduced:
                    existing = active_by_identity.get(allocation.guard_identity)
                    if existing is not None and existing != allocation:
                        raise WithholdingObservationMutationError("economic_allocation_conflict")
                    active_by_identity[allocation.guard_identity] = allocation

            active = tuple(sorted(active_by_identity.values(), key=lambda item: item.guard_identity))
            _require_within_liability(next_liability, active)
            writes.append(
                _control_write(
                    _guard_key(source_token),
                    _SourceLiabilityGuard(
                        source_token=source_token,
                        liability=next_liability,
                        allocations=active,
                    ),
                    expected_revision_id,
                )
            )
        return tuple(writes)

    def _projection_payloads(self, scope: WithholdingWindowScope) -> Iterable[tuple[str, object | None, object | None]]:
        for payload in self._retenciones.iter_modelo(scope.modelo):
            if (
                payload.filing_year == scope.period.filing_year
                and payload.period.registry_token == scope.period.registry_token
            ):
                if payload.projection_identity is None:
                    raise WithholdingObservationMutationError("unsupported_mixed_legacy_state")
                yield payload.projection_identity, payload.observation, None
        for payload in self._percepciones.iter_modelo(scope.modelo):
            if (
                payload.filing_year == scope.period.filing_year
                and payload.period.registry_token == scope.period.registry_token
            ):
                if payload.projection_identity is None:
                    raise WithholdingObservationMutationError("unsupported_mixed_legacy_state")
                yield payload.projection_identity, None, payload.observation

    def _retencion_key(self, scope: WithholdingWindowScope, entry: WithholdingProjectionEntry) -> str:
        if entry.retencion is None:
            raise WithholdingObservationMutationError("projection_identity_mismatch")
        return self._retenciones.extract_identifier(
            self._retenciones.build_observation_payload(
                modelo=scope.modelo,
                filing_year=scope.period.filing_year,
                period=scope.period,
                observation=entry.retencion,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
                projection_identity=entry.identity.token,
            ),
        )

    def _percepcion_key(self, scope: WithholdingWindowScope, entry: WithholdingProjectionEntry) -> str:
        if entry.percepcion is None:
            raise WithholdingObservationMutationError("projection_identity_mismatch")
        return self._percepciones.extract_identifier(
            self._percepciones.build_observation_payload(
                modelo=scope.modelo,
                filing_year=scope.period.filing_year,
                period=scope.period,
                observation=entry.percepcion,
                source_kind=AggregationCaptureKind.AGGREGATE_PULL,
                projection_identity=entry.identity.token,
            ),
        )


def _entries_digest(entries: Iterable[WithholdingProjectionEntry]) -> str:
    values = sorted(
        (entry.model_dump(mode="json") for entry in entries),
        key=lambda value: _canonical_json(value["identity"]),
    )
    return sha256_hex(_canonical_json(values).encode(UTF_8_ENCODING))


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: str) -> str:
    return sha256_hex(value.encode(UTF_8_ENCODING))


def _head_key(scope: WithholdingWindowScope) -> str:
    return f"window:{_digest(scope.token)}"


def _generation_key(scope: WithholdingWindowScope, generation_id: str) -> str:
    return f"generation:{_digest(scope.token)}:{generation_id}"


def _idempotency_key(scope: WithholdingWindowScope, key: str) -> str:
    return f"idempotency:{_digest(scope.token)}:{_digest(key)}"


def _guard_key(source_token: str) -> str:
    """Return the encrypted derived-index key for one source liability."""
    return f"guard:{source_token}"


def _allocations_by_source(
    entries: Iterable[WithholdingProjectionEntry],
) -> dict[str, tuple[EconomicAllocation, ...]]:
    """Deduplicate allocation evidence across projection roles by guard identity."""
    grouped: dict[str, dict[str, EconomicAllocation]] = {}
    for entry in entries:
        allocation = entry.allocation
        source = allocation.liability.source_token
        bucket = grouped.setdefault(source, {})
        current = bucket.get(allocation.guard_identity)
        if current is not None and current != allocation:
            raise WithholdingObservationMutationError("economic_allocation_conflict")
        bucket[allocation.guard_identity] = allocation
    return {
        source: tuple(sorted(allocations.values(), key=lambda item: item.guard_identity))
        for source, allocations in grouped.items()
    }


def _single_liability(allocations: Iterable[EconomicAllocation]) -> SourceLiabilitySnapshot:
    """Require one revision-bound canonical liability for one source mutation."""
    values = tuple(allocations)
    if not values:
        raise WithholdingObservationMutationError("missing_liability_snapshot")
    liability = values[0].liability
    if any(item.liability != liability for item in values[1:]):
        raise WithholdingObservationMutationError("contradictory_liability_snapshot")
    return liability


def _validate_guard_allocations(guard: _SourceLiabilityGuard) -> None:
    """Refuse a tampered or incompatible derived guard before it can be used."""
    identities: set[str] = set()
    for allocation in guard.allocations:
        if allocation.liability != guard.liability or allocation.guard_identity in identities:
            raise WithholdingObservationMutationError("liability_guard_integrity_failure")
        identities.add(allocation.guard_identity)


def _require_within_liability(
    liability: SourceLiabilitySnapshot,
    allocations: Iterable[EconomicAllocation],
) -> None:
    """Fail closed for each incomparable source-liability monetary dimension."""
    values = tuple(allocations)
    base = sum((item.allocated_base for item in values), Decimal("0"))
    withholding = sum((item.allocated_withholding for item in values), Decimal("0"))
    settlement = sum((item.allocated_settlement for item in values), Decimal("0"))
    if base > liability.liability_base:
        raise WithholdingObservationMutationError("liability_base_exceeded")
    if withholding > liability.liability_withholding:
        raise WithholdingObservationMutationError("liability_withholding_exceeded")
    if settlement > liability.liability_settlement:
        raise WithholdingObservationMutationError("liability_settlement_exceeded")


def _control_write(key: str, payload: BaseModel, expected_revision_id: str) -> SecureObjectWrite:
    envelope_type = parameterized_envelope_type(type(payload))
    envelope = envelope_type(
        schema_version=WITHHOLDING_WORKFLOW_NAMESPACE.schema_version,
        written_at=now(),
        classification=WITHHOLDING_WORKFLOW_NAMESPACE.sensitivity,
        payload=payload,
    )
    return SecureObjectWrite(
        namespace=WITHHOLDING_WORKFLOW_NAMESPACE.namespace,
        object_key=key,
        classification=WITHHOLDING_WORKFLOW_NAMESPACE.sensitivity,
        schema_version=WITHHOLDING_WORKFLOW_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        expected_revision_id=expected_revision_id,
    )


def _read_envelope[EnvelopePayload: BaseModel](payload: bytes, model: type[EnvelopePayload]) -> EnvelopePayload:
    """Hydrate one encrypted control payload with its exact typed model."""
    envelope_type = parameterized_envelope_type(model)
    envelope = envelope_type.model_validate_json(payload.decode(UTF_8_ENCODING))
    return envelope.payload


__all__ = ["WithholdingObservationWorkflowAdapter"]
