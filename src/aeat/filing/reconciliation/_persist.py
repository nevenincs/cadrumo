"""Persistence adapter: ``ReconciliationReport`` → divergence record.

The accepted ``aeat-verify`` ADR mandates that ``DIVERGENT`` and
``NOT_YET_FOUND`` reconciliation reports flow through the existing
Kent-facing divergence queue alongside schema-level sync divergences.
The non-negotiable constraint is that the existing
:class:`aeat.sync._divergence.DivergenceKind` enum and
:data:`aeat.sync._divergence.DivergencePayload` discriminated union are
**not** widened — they govern the schema-level auto-heal-safety
contract and reasoning about a second axis (filing-instance value
divergence) on the same enum would silently widen that contract.

The existing :class:`aeat.sync._divergence.DivergencePayload` union is
closed, so we cannot inject a new payload variant from outside the
``aeat.sync`` subpackage without a structural modification. The plan's
fork-rationale paragraph governs this case: the persistence adapter
emits a wrapping record (``FilingReconciliationDivergenceRecord``)
that mirrors the shape of :class:`aeat.sync.DivergenceRecord` (record
id + detected_at + classification + payload + resolution_state +
notes) without re-using the closed payload union. The Phase-5
sync-run integration is responsible for routing the wrapping record
to the same Kent-facing queue as the schema-level records.

The wrapping record carries the
:class:`aeat.sync._divergence.DivergenceClassification` and
:class:`aeat.sync._divergence.ResolutionState` enums verbatim so the
queue surface stays uniform; only the payload union is forked, never
the shells around it.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ...sync import DivergenceClassification, ResolutionState
from ._errors import ReconciliationError
from ._kind import FilingDivergenceKind
from ._schema import (
    CasillaDelta,
    FilingDraftRef,
    ReconciliationReport,
    ReconciliationStatus,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class _ReconciliationPayloadBase(BaseModel):
    """Shared config for every concrete reconciliation payload variant."""

    model_config = _STRICT_FROZEN


class CasillaValueMismatchPayload(_ReconciliationPayloadBase):
    """Per-casilla payload for a :attr:`FilingDivergenceKind.CASILLA_VALUE_MISMATCH` delta."""

    kind: Literal[FilingDivergenceKind.CASILLA_VALUE_MISMATCH] = FilingDivergenceKind.CASILLA_VALUE_MISMATCH
    casilla_id: str = Field(min_length=1, max_length=16)
    local_value: str | None
    remote_value: str | None
    delta: str | None
    """Signed monetary delta as a stable decimal-string projection."""


class CasillaMissingLocalPayload(_ReconciliationPayloadBase):
    """Payload for a casilla AEAT reports but the local draft does not."""

    kind: Literal[FilingDivergenceKind.CASILLA_MISSING_LOCAL] = FilingDivergenceKind.CASILLA_MISSING_LOCAL
    casilla_id: str = Field(min_length=1, max_length=16)
    remote_value: str | None


class CasillaExtraLocalPayload(_ReconciliationPayloadBase):
    """Payload for a casilla the local draft carries but AEAT does not."""

    kind: Literal[FilingDivergenceKind.CASILLA_EXTRA_LOCAL] = FilingDivergenceKind.CASILLA_EXTRA_LOCAL
    casilla_id: str = Field(min_length=1, max_length=16)
    local_value: str | None


class FilingStatusDivergencePayload(_ReconciliationPayloadBase):
    """Payload for a filing-scope status divergence."""

    kind: Literal[FilingDivergenceKind.FILING_STATUS_DIVERGENCE] = FilingDivergenceKind.FILING_STATUS_DIVERGENCE
    local_status: str = Field(min_length=1, max_length=64)
    remote_status: str = Field(min_length=1, max_length=64)


class RoundingOnlyPayload(_ReconciliationPayloadBase):
    """Payload for a casilla within the rounding tolerance.

    Rounding-only entries do not flip a report away from
    :attr:`ReconciliationStatus.MATCH`, so the persistence adapter
    never produces a record carrying *only* this kind. The variant
    exists so a future contributor surfacing rounding-only entries on
    a divergent record (e.g. as supporting context) has a typed shape
    to land them in.
    """

    kind: Literal[FilingDivergenceKind.ROUNDING_ONLY] = FilingDivergenceKind.ROUNDING_ONLY
    casilla_id: str = Field(min_length=1, max_length=16)
    local_value: str | None
    remote_value: str | None
    delta: str | None


class FilingNotYetFoundPayload(_ReconciliationPayloadBase):
    """Payload for a filing AEAT has no record of yet."""

    kind: Literal[FilingDivergenceKind.FILING_NOT_YET_FOUND] = FilingDivergenceKind.FILING_NOT_YET_FOUND
    expected_modelo: str = Field(min_length=1, max_length=8)
    expected_period: str = Field(min_length=1, max_length=16)


FilingReconciliationPayload = Annotated[
    CasillaValueMismatchPayload
    | CasillaMissingLocalPayload
    | CasillaExtraLocalPayload
    | FilingStatusDivergencePayload
    | RoundingOnlyPayload
    | FilingNotYetFoundPayload,
    Field(discriminator="kind"),
]
"""Closed discriminated union of every persistable reconciliation delta payload.

Disjoint from :data:`aeat.sync._divergence.DivergencePayload` per the
``aeat-verify`` ADR rationale. Adding a variant requires a loud,
explicit change to this module; the discriminator keys this union off
:class:`FilingDivergenceKind` so the existing schema-level union is
unaffected.
"""


class FilingReconciliationDivergenceRecord(BaseModel):
    """Persistable wrapping record for one reconciliation delta.

    Mirrors the shape of :class:`aeat.sync.DivergenceRecord`
    (``record_id`` + ``detected_at`` + ``classification`` + ``payload``
    + ``resolution_state`` + ``notes``) so the same Kent-facing queue
    surface can carry both schema-level and filing-level divergences.
    The payload field is keyed off the local
    :data:`FilingReconciliationPayload` discriminated union; the
    ``classification`` and ``resolution_state`` enums are re-used from
    :mod:`aeat.sync` verbatim.

    Attributes:
        record_id: Stable, content-addressed identifier the queue uses
            to deduplicate repeat reconciliation runs.
        detected_at: UTC timestamp at which the originating
            :class:`ReconciliationReport` was emitted.
        modelo: AEAT modelo code the record refers to.
        period: Period identifier the record refers to.
        draft_ref: Lightweight reference to the local
            :class:`aeat.filing.FilingDraft` that produced the record.
        classification: :class:`aeat.sync.DivergenceClassification`
            bucket. Reconciliation records always classify as
            :attr:`aeat.sync.DivergenceClassification.BREAKING` —
            filing-instance value divergence is by construction
            never auto-heal-safe.
        payload: One concrete :data:`FilingReconciliationPayload`
            variant describing the delta.
        resolution_state: Operator-facing resolution state. Defaults
            to :attr:`aeat.sync.ResolutionState.PENDING`.
        notes: Optional free-text annotation for the operator.
    """

    model_config = _STRICT_FROZEN

    record_id: str = Field(min_length=1, max_length=128)
    detected_at: AwareDatetime
    modelo: str = Field(min_length=1, max_length=8)
    period: str = Field(min_length=1, max_length=16)
    draft_ref: FilingDraftRef
    classification: DivergenceClassification
    payload: FilingReconciliationPayload
    resolution_state: ResolutionState = ResolutionState.PENDING
    notes: str | None = Field(default=None, max_length=2048)


def _decimal_text(delta: object | None) -> str | None:
    """Render the report's signed delta as a stable decimal string."""
    if delta is None:
        return None
    return str(delta)


def _payload_for_delta(
    delta: CasillaDelta,
    *,
    report: ReconciliationReport,
) -> FilingReconciliationPayload | None:
    """Project a :class:`CasillaDelta` onto the persistable payload union."""
    kind = delta.kind
    if kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH:
        return CasillaValueMismatchPayload(
            casilla_id=delta.casilla_id,
            local_value=delta.local_value,
            remote_value=delta.remote_value,
            delta=_decimal_text(delta.delta),
        )
    if kind is FilingDivergenceKind.CASILLA_MISSING_LOCAL:
        return CasillaMissingLocalPayload(
            casilla_id=delta.casilla_id,
            remote_value=delta.remote_value,
        )
    if kind is FilingDivergenceKind.CASILLA_EXTRA_LOCAL:
        return CasillaExtraLocalPayload(
            casilla_id=delta.casilla_id,
            local_value=delta.local_value,
        )
    if kind is FilingDivergenceKind.FILING_STATUS_DIVERGENCE:
        return FilingStatusDivergencePayload(
            local_status=delta.local_value or "",
            remote_status=delta.remote_value or "",
        )
    if kind is FilingDivergenceKind.ROUNDING_ONLY:
        return RoundingOnlyPayload(
            casilla_id=delta.casilla_id,
            local_value=delta.local_value,
            remote_value=delta.remote_value,
            delta=_decimal_text(delta.delta),
        )
    if kind is FilingDivergenceKind.FILING_NOT_YET_FOUND:
        return FilingNotYetFoundPayload(
            expected_modelo=report.draft_ref.modelo,
            expected_period=report.draft_ref.period,
        )
    raise ReconciliationError(f"Unhandled FilingDivergenceKind {kind!r}")


def _record_id(
    *,
    draft_id: str,
    casilla_id: str,
    kind: FilingDivergenceKind,
) -> str:
    """Compute the content-addressed record id for one delta."""
    payload = f"{draft_id}|{kind.value}|{casilla_id}".encode()
    return hashlib.sha256(payload).hexdigest()[:32]


def reconciliation_records(
    report: ReconciliationReport,
) -> tuple[FilingReconciliationDivergenceRecord, ...]:
    """Project a :class:`ReconciliationReport` into divergence records.

    :attr:`ReconciliationStatus.MATCH` reports — including reports
    whose only deltas are :attr:`FilingDivergenceKind.ROUNDING_ONLY` —
    produce an empty tuple: there is nothing for the Kent-facing
    queue to surface. :attr:`ReconciliationStatus.DIVERGENT` and
    :attr:`ReconciliationStatus.NOT_YET_FOUND` reports produce one
    record per non-rounding delta.

    Args:
        report: The :class:`ReconciliationReport` produced by
            :func:`reconcile`.

    Returns:
        A possibly-empty tuple of
        :class:`FilingReconciliationDivergenceRecord` instances ready
        for the Kent-facing divergence sink. Each record carries a
        stable, content-addressed ``record_id`` so a repeat
        reconciliation run does not surface duplicates.
    """
    if report.status is ReconciliationStatus.MATCH:
        return ()

    records: list[FilingReconciliationDivergenceRecord] = []
    for delta in report.casilla_deltas:
        if delta.kind is FilingDivergenceKind.ROUNDING_ONLY:
            continue
        payload = _payload_for_delta(delta, report=report)
        if payload is None:  # pragma: no cover - guarded by exhaustive _payload_for_delta
            continue
        records.append(
            FilingReconciliationDivergenceRecord(
                record_id=_record_id(
                    draft_id=report.draft_ref.draft_id,
                    casilla_id=delta.casilla_id,
                    kind=delta.kind,
                ),
                detected_at=report.reconciled_at,
                modelo=report.draft_ref.modelo,
                period=report.draft_ref.period,
                draft_ref=report.draft_ref,
                classification=DivergenceClassification.BREAKING,
                payload=payload,
            )
        )
    return tuple(records)


__all__ = [
    "CasillaExtraLocalPayload",
    "CasillaMissingLocalPayload",
    "CasillaValueMismatchPayload",
    "FilingNotYetFoundPayload",
    "FilingReconciliationDivergenceRecord",
    "FilingReconciliationPayload",
    "FilingStatusDivergencePayload",
    "RoundingOnlyPayload",
    "reconciliation_records",
]
