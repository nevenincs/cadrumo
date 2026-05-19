"""One calculation attempt under a modelo work unit.

A work unit owns many calculation revisions. Each ``calculate``
invocation produces a fresh, content-addressed
:class:`CalculationRevision`. The work unit carries pointer fields
that disambiguate which revision is the most recent (``current``)
and which one is the filed answer (``filed``). Without those
pointers, multiple drafts under the same work unit have no canonical
selection — every consumer (year-aggregation, amendment delta,
forward-period carry-forward) needs to know which one is THE
revision.

Lifecycle states:

* ``BORRADOR`` — newly calculated; mutable in the sense that
  re-running ``calculate`` creates a new revision rather than
  editing this one. Multiple borradores can coexist.
* ``VERIFICADO_COMPLETO`` — ``verify`` ran cleanly: all required
  casillas resolved, zero blocking findings, source trace
  persisted. The revision is immutable from this point on; any
  recalculation produces a fresh borrador instead.
* ``PRESENTADO`` — paired with a :class:`ModeloRecord`. The revision
  is the currently-effective filed answer for its (bucket, modelo,
  year, period) tuple. Exactly one presentado revision per tuple at
  any time.
* ``PRESENTADO_SUPERSEDIDO`` — a later verified revision was filed
  against the same tuple. The revision and its filing record remain
  in the audit trail.
* ``DESCARTADO`` — operator abandoned the revision before filing.

Two CalculationRevisions can never share a ``calculation_revision_id``;
the id is the SHA-256 of the inputs + binding overrides + computed
casilla values (plus the parent work_unit_id), so structurally
identical re-runs produce the same id and re-running ``calculate``
with the same data is naturally idempotent.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..calculations.registry._bindings import CasillaObservation
from ._errors import ModeloValidationError


class CalculationRevisionState(StrEnum):
    """Closed enumeration of calculation-revision lifecycle states."""

    BORRADOR = "borrador"
    VERIFICADO_COMPLETO = "verificado_completo"
    PRESENTADO = "presentado"
    PRESENTADO_SUPERSEDIDO = "presentado_supersedido"
    DESCARTADO = "descartado"


class CalculationRevisionAmendmentKind(StrEnum):
    """Closed catalogue of amendment kinds a revision may carry.

    Aligned with Spanish tax law's legally-distinct amendment shapes:

    * ``COMPLEMENTARIA`` — corrective filing that adds to the prior
      filing's tax due. Filed when the operator discovers an error
      that under-reported tax.
    * ``SUSTITUTIVA`` — substitute filing that replaces the prior
      filing entirely. Used for material restatements.
    """

    COMPLEMENTARIA = "complementaria"
    SUSTITUTIVA = "sustitutiva"


_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

_CalculationRevisionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
_WorkUnitId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
_ActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
_DiscardReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_CasillaKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


def _canonical_decimal(value: Decimal) -> str:
    """Stable string form of a Decimal for hash inputs."""

    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")


def derive_calculation_revision_id(
    *,
    work_unit_id: str,
    inputs_snapshot: Mapping[str, str],
    binding_overrides: Mapping[str, str],
    casilla_values: Mapping[str, Decimal],
    source_transaction_ids: Sequence[str] = (),
    borrador_snapshot_id: str | None = None,
    bindings_sourced_from_borrador: Sequence[str] = (),
) -> str:
    """Return the deterministic SHA-256 id for a calculation attempt.

    The id is content-addressed by the parent work unit plus the
    three payload mappings: input casilla values, operator-supplied
    binding overrides, and computed casilla outputs. Two
    structurally identical re-runs produce the same id; the
    catalogue's content-addressing invariant then makes a second
    ``calculate`` call idempotent (the existing revision is
    returned, no duplicate is persisted).
    """

    payload = {
        "work_unit_id": work_unit_id.strip(),
        "inputs": dict(sorted((k.strip(), v.strip()) for k, v in inputs_snapshot.items())),
        "overrides": dict(sorted((k.strip(), v.strip()) for k, v in binding_overrides.items())),
        "outputs": dict(sorted((k.strip(), _canonical_decimal(v)) for k, v in casilla_values.items())),
        "source_transaction_ids": tuple(sorted(item.strip() for item in source_transaction_ids)),
    }
    normalized_borrador_snapshot_id = borrador_snapshot_id.strip() if borrador_snapshot_id else None
    normalized_borrador_bindings = tuple(sorted(item.strip() for item in bindings_sourced_from_borrador))
    if normalized_borrador_snapshot_id is not None:
        payload["borrador_snapshot_id"] = normalized_borrador_snapshot_id
    if normalized_borrador_bindings:
        payload["bindings_sourced_from_borrador"] = normalized_borrador_bindings
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CalculationRevision(BaseModel):
    """One calculation attempt attached to a work unit.

    Attributes:
        calculation_revision_id: Lowercase 64-char SHA-256 derived
            from the parent work_unit_id plus the inputs, overrides,
            and casilla outputs. Content-addressed: structurally
            identical re-runs produce the same id.
        work_unit_id: Parent work unit id (also content-addressed).
        state: Lifecycle state from
            :class:`CalculationRevisionState`.
        inputs_snapshot: Mapping of canonical input casilla values
            captured at calculation time. The string values are
            decimal strings or short literals from the registry
            input contract.
        binding_overrides: Mapping of operator-supplied binding
            overrides applied during this calculation. Empty when
            no overrides were used.
        source_transaction_ids: Stable ledger transaction ids that
            contributed to this revision through bucket-local
            aggregation. Empty for calculations that did not consume
            ledger transactions.
        casilla_values: Mapping of computed casilla values (decimal
            output). The values that would be exported to AEAT if
            this revision were filed.
        created_at: UTC timestamp of revision creation.
        updated_at: UTC timestamp of the most recent state transition.
            Equals ``created_at`` on a fresh draft.
        verified_at: UTC timestamp at which the revision transitioned
            to ``VERIFICADO_COMPLETO``. ``None`` for non-verified
            revisions.
        verified_by: Actor label captured at verification time.
            ``None`` for non-verified revisions.
        filed_at: UTC timestamp at which the revision was filed.
            ``None`` for non-filed revisions.
        filed_by: Actor label captured at filing time. ``None``
            for non-filed revisions.
        superseded_at: UTC timestamp at which a later filed revision
            superseded this one. ``None`` unless ``state is
            PRESENTADO_SUPERSEDIDO``.
        discarded_at, discarded_by, discard_reason: audit metadata
            captured when the revision is moved to ``DESCARTADO``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    calculation_revision_id: _CalculationRevisionId
    work_unit_id: _WorkUnitId
    state: CalculationRevisionState
    inputs_snapshot: Mapping[str, str] = Field(default_factory=dict)
    binding_overrides: Mapping[str, str] = Field(default_factory=dict)
    source_transaction_ids: tuple[_CalculationRevisionId, ...] = Field(default_factory=tuple)
    borrador_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    bindings_sourced_from_borrador: tuple[str, ...] = Field(default_factory=tuple)
    casilla_values: Mapping[str, Decimal] = Field(default_factory=dict)
    # Typed envelope carrying formula provenance for every computed
    # casilla. Defaults to () so already-persisted revisions remain
    # loadable. New revisions populate this from the engine's typed
    # entries so the operand_refs / operand_values / legal_refs /
    # source_refs trace survives the domain boundary that previously
    # dropped them when only ``casilla_values`` was persisted.
    observations: tuple[CasillaObservation, ...] = Field(default_factory=tuple)
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None = None
    verified_by: _ActorLabel | None = None
    filed_at: datetime | None = None
    filed_by: _ActorLabel | None = None
    superseded_at: datetime | None = None
    discarded_at: datetime | None = None
    discarded_by: _ActorLabel | None = None
    discard_reason: _DiscardReason | None = None
    amendment_kind: CalculationRevisionAmendmentKind | None = None
    amends_filing_record_id: _CalculationRevisionId | None = None
    amendment_reason: _DiscardReason | None = None

    @model_validator(mode="after")
    def _enforce_invariants(self) -> CalculationRevision:
        derived = derive_calculation_revision_id(
            work_unit_id=self.work_unit_id,
            inputs_snapshot=self.inputs_snapshot,
            binding_overrides=self.binding_overrides,
            casilla_values=self.casilla_values,
            source_transaction_ids=self.source_transaction_ids,
            borrador_snapshot_id=self.borrador_snapshot_id,
            bindings_sourced_from_borrador=self.bindings_sourced_from_borrador,
        )
        if derived != self.calculation_revision_id:
            raise ModeloValidationError(
                f"calculation_revision_id {self.calculation_revision_id!r} does not match "
                f"the derived id {derived!r} for work_unit_id={self.work_unit_id!r}"
            )
        if self.updated_at < self.created_at:
            raise ModeloValidationError(
                f"updated_at {self.updated_at.isoformat()} precedes created_at {self.created_at.isoformat()}"
            )
        # State-specific audit-metadata invariants.
        if self.state is CalculationRevisionState.BORRADOR:
            self._require_none(
                "verified_at",
                "verified_by",
                "filed_at",
                "filed_by",
                "superseded_at",
                "discarded_at",
                "discarded_by",
                "discard_reason",
            )
        elif self.state is CalculationRevisionState.VERIFICADO_COMPLETO:
            self._require_set("verified_at", "verified_by")
            self._require_none(
                "filed_at", "filed_by", "superseded_at", "discarded_at", "discarded_by", "discard_reason"
            )
        elif self.state is CalculationRevisionState.PRESENTADO:
            self._require_set("verified_at", "verified_by", "filed_at", "filed_by")
            self._require_none("superseded_at", "discarded_at", "discarded_by", "discard_reason")
        elif self.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO:
            self._require_set("verified_at", "verified_by", "filed_at", "filed_by", "superseded_at")
            self._require_none("discarded_at", "discarded_by", "discard_reason")
        elif self.state is CalculationRevisionState.DESCARTADO:
            self._require_set("discarded_at", "discarded_by")
            self._require_none("verified_at", "verified_by", "filed_at", "filed_by", "superseded_at")
        # Amendment-metadata invariants. ``amendment_kind``,
        # ``amends_filing_record_id``, and ``amendment_reason`` must
        # be all-set-or-all-None: an amendment carries every field;
        # a non-amendment carries none.
        amendment_set = (
            self.amendment_kind is not None,
            self.amends_filing_record_id is not None,
            self.amendment_reason is not None,
        )
        if any(amendment_set) and not all(amendment_set):
            raise ModeloValidationError(
                "amendment_kind, amends_filing_record_id, and amendment_reason must all be set together or all be None"
            )
        return self

    @field_validator("source_transaction_ids", mode="before")
    @classmethod
    def _freeze_source_transaction_ids(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, Sequence) or isinstance(value, str | bytes):
            raise ModeloValidationError("source_transaction_ids must be a sequence")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ModeloValidationError("source_transaction_ids must contain strings")
            normalized.append(item)
        return tuple(normalized)

    @field_validator("source_transaction_ids")
    @classmethod
    def _normalise_source_transaction_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(item.strip().lower() for item in value))
        if len(set(normalized)) != len(normalized):
            raise ModeloValidationError("source_transaction_ids must not contain duplicates")
        return normalized

    def _require_set(self, *names: str) -> None:
        for name in names:
            if getattr(self, name) is None:
                raise ModeloValidationError(f"calculation revision in state {self.state.value!r} must carry {name!r}")

    def _require_none(self, *names: str) -> None:
        for name in names:
            if getattr(self, name) is not None:
                raise ModeloValidationError(
                    f"calculation revision in state {self.state.value!r} must not carry {name!r}"
                )


class CalculationRevisionCatalogue(BaseModel):
    """Immutable catalogue of every calculation revision in storage."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    revisions: Mapping[str, CalculationRevision] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> CalculationRevisionCatalogue:
        for key, revision in self.revisions.items():
            if key != revision.calculation_revision_id:
                raise ModeloValidationError(
                    f"catalogue key {key!r} does not match calculation_revision_id {revision.calculation_revision_id!r}"
                )
        return self

    def get(self, calculation_revision_id: str) -> CalculationRevision | None:
        return self.revisions.get(calculation_revision_id)

    def values(self):
        return self.revisions.values()

    def for_work_unit(self, work_unit_id: str) -> tuple[CalculationRevision, ...]:
        """Return every revision attached to one work unit."""
        return tuple(rev for rev in self.revisions.values() if rev.work_unit_id == work_unit_id)

    def __iter__(self) -> Iterator[CalculationRevision]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
        return iter(self.revisions.values())

    def __len__(self) -> int:
        return len(self.revisions)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, CalculationRevision):
            return key.calculation_revision_id in self.revisions
        if isinstance(key, str):
            return key in self.revisions
        return False


__all__ = [
    "CalculationRevision",
    "CalculationRevisionAmendmentKind",
    "CalculationRevisionCatalogue",
    "CalculationRevisionState",
    "derive_calculation_revision_id",
]
