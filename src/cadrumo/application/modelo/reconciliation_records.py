"""What a modelo reconciliation IS, and where it is stored.

The nouns of reconciliation, separated from the verb. This module owns the
persisted :class:`ModeloReconciliationRecord`, the encrypted store it lives in,
the key that admits N records per work unit, and the typed read-back the
operator sees. :mod:`~application.modelo.reconciliation` owns the act of
reconciling — parsing the evidence, comparing it against the work unit, and
producing a report — and persists its outcome through the store here.

The split is what keeps either half nameable. The reconcile service is a
comparison; this is a persisted format, with its own key grammar, its own
durability enrolment, and its own roundtrip obligations.

See Also:
    :mod:`~application.modelo.reconciliation`:
        The reconcile service that writes these records, co-emitting each with
        its bucket event in one unit of work.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import BucketId, WorkUnitId
from ...core.time import validate_utc_aware
from ...domain.buckets import BucketEvent, BucketEventId
from ...domain.calculations.registry.ids import (
    LegalRefId,
    SourceRefId,
)
from ...domain.modelos.filing_text import ModeloActorLabel


class ModeloReconciliationEvidenceKind(StrEnum):
    """Closed external-evidence labels accepted by reconciliation commands.

    ``DECLARATION`` performs casilla-level reconciliation for modelos in
    :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`; other modelos raise
    :class:`ReconciliationDeclaracionSourceUnsupportedError`.
    """

    JUSTIFICANTE = "justificante"
    DECLARATION = "declaration"


class ModeloReconciliationVerdict(StrEnum):
    """Closed verdict catalogue for :class:`ModeloReconciliationReport`.

    Closed set: ``matches`` / ``mismatches``. A reconcile that reaches a report
    has already parsed its evidence; an unparseable justificante is surfaced as
    the typed ``ReconciliationEvidenceInvalidError`` refusal
    (``REFUSED_RECONCILIATION_EVIDENCE_INVALID``) before any report is built, so
    there is no ``evidence_invalid`` verdict shell. Any expansion requires a
    design decision and must not add shells.
    """

    MATCHES = "matches"
    MISMATCHES = "mismatches"


class ModeloReconciliationDiffKind(StrEnum):
    """Closed category for a :class:`ModeloReconciliationDiff`.

    ``header_field`` — a receipt-identity disagreement (modelo, ejercicio,
    period, tax id). ``total`` — a filed-amount disagreement between the
    receipt total and the canonical computed result casilla. ``casilla`` — a
    per-casilla value disagreement between the persisted computed revision and
    a filed declaración, emitted for modelos enrolled in
    :data:`_DECLARATION_CASILLA_RECONCILE_MODELOS`
    (:func:`application.modelo._reconcile_casilla.detect_casilla_divergences`).
    """

    HEADER_FIELD = "header_field"
    TOTAL = "total"
    CASILLA = "casilla"


class ModeloReconciliationDiff(BaseModel):
    """One disagreement between work unit / profile / computed state and evidence.

    ``diff_kind`` is the closed category (header field, filed total, or
    per-casilla). ``kind`` remains the specific mismatch token
    (``modelo_mismatch``, ``total_ingresar_mismatch``,
    ``casilla_value_mismatch``, ``casilla_missing_in_filed``,
    ``casilla_extra_in_filed``, …). A ``total`` or ``casilla`` diff carries the
    reconciling verification expectation's / casilla's ``legal_refs`` /
    ``source_refs`` so the divergence surfaces with its legal grounding
    (``aeat-calculation-grounding``); header diffs carry empty grounding. For a
    ``casilla`` diff, ``field_name`` is the casilla id and ``work_unit_value`` /
    ``evidence_value`` carry the computed / filed decimal strings (empty when
    the corresponding side carried no value, per
    :class:`~application.modelo._reconcile_casilla.CasillaDivergenceKind`).
    """

    model_config = _STRICT_FROZEN

    field_name: str = Field(min_length=1)
    work_unit_value: str = ""
    evidence_value: str = ""
    kind: str = Field(min_length=1)
    diff_kind: ModeloReconciliationDiffKind = ModeloReconciliationDiffKind.HEADER_FIELD
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()

    @model_validator(mode="after")
    def _enforce_value_diff_grounding(self) -> ModeloReconciliationDiff:
        """Require legal and source grounding on every value-bearing diff.

        The docstring above promises a ``total`` or ``casilla`` diff carries the
        reconciling expectation's or casilla's registry grounding, but both
        tuples defaulted empty and unconstrained, so an ungrounded — or
        free-text — value divergence persisted and read back as if it were
        grounded. The producers already hold the refs (the total target and the
        registry casilla each declare them), so an empty tuple here means the
        grounding was lost on the way, not that none exists.

        Header diffs (modelo, ejercicio, period, tax_id) compare filing identity
        rather than a regulated amount and carry no casilla grounding by design;
        they keep the empty tuples.
        """
        if self.diff_kind is ModeloReconciliationDiffKind.HEADER_FIELD:
            return self
        if not self.legal_refs or not self.source_refs:
            raise ValueError(
                f"{self.diff_kind.value} diff {self.field_name!r} must carry legal_refs and "
                f"source_refs grounding; got legal_refs={self.legal_refs!r}, "
                f"source_refs={self.source_refs!r}",
            )
        return self


class ModeloReconciliationAdvisory(BaseModel):
    """One non-blocking reconciliation advisory (surfaced as a CLI ``Notice``).

    Carries a stable ``code`` (``totals_not_reconciled`` /
    ``identity_anchor_unverified``), an operator-facing ``message``, and
    structured ``context`` (the reason, the anchor, the modelo). The CLI folds
    each advisory into a typed :class:`~core.json_contract.Notice` on the
    envelope's ``notices`` channel per
    ``aeat-cli-contract`` — an advisory is never a
    bespoke result field. Advisories never flip the verdict: they disclose that
    a comparison could not be performed (so identity-only ``matches`` is never a
    silent false green), not that a value diverged.
    """

    model_config = _STRICT_FROZEN

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    context: Mapping[str, str] = Field(default_factory=dict)


class ModeloReconciliationRecord(BaseModel):
    """One persisted reconciliation outcome, in full.

    The durable, auditable copy of a reconciliation: verdict, evidence kind and
    reference, work unit, the grounded diffs, the advisories, the instant and
    the actor. It is written to the encrypted profile-scoped reconciliation
    store selected by :class:`ModeloReconciliationPersistencePort` in the same
    unit of work as the ``MODELO_RECONCILED``
    :class:`~domain.buckets.BucketEvent` whose id it carries, so the event log
    and the detail store cannot disagree about what was reconciled.

    Grounding is **stored, not re-derived**. Each :class:`ModeloReconciliationDiff`
    keeps the ``legal_refs`` / ``source_refs`` that were in force when the
    reconciliation ran. Re-deriving them at read time would resolve the snapshot
    from modelo, filing year and period per ``aeat-registry-authority-flow``,
    so a routine re-grounding sweep that moved a casilla's ``legal_refs`` without
    moving the revision id would silently rewrite the legal basis of a historical
    reconciliation — and one that did move the revision id would make the history
    unreadable. Historical evidence stays self-describing.

    ``source_ref`` is the evidence reference as supplied: an operator filesystem
    path, or the secure-storage handle on the bytes path. It is stored here at
    full length; only the bucket-event copy is shortened to fit the payload cap.
    """

    model_config = _STRICT_FROZEN

    bucket_event_id: BucketEventId
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_ref: str = ""
    verdict: ModeloReconciliationVerdict
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    advisories: tuple[ModeloReconciliationAdvisory, ...] = ()
    actor: ModeloActorLabel
    reconciled_at: datetime

    @field_validator("reconciled_at")
    @classmethod
    def _reconciled_at_is_utc(cls, value: datetime) -> datetime:
        """Hold the persisted instant to the canonical UTC-aware contract.

        The record documents a canonical UTC history, but a bare ``datetime``
        accepted a naive or ``+01:00`` value, so two reconciliations of the same
        work unit could not be ordered against each other and a Madrid-local
        instant read back as if it were UTC.
        """
        return validate_utc_aware(value)


class ModeloReconciliationHistoryEntry(BaseModel):
    """One past reconciliation read back from the reconciliation record store.

    ``modelo_reconcile`` DOES persist a stored record. Each run writes a
    :class:`ModeloReconciliationRecord` into the encrypted profile-scoped
    reconciliation store selected by :class:`ModeloReconciliationPersistencePort`,
    in the same unit of work as the slim ``MODELO_RECONCILED``
    :class:`~domain.buckets.BucketEvent` it emits. This typed entry projects one
    such record so the operator can enumerate past reconciliation verdicts, and
    the grounded divergences behind them, without re-parsing any evidence.

    The dedicated store exists because a bucket-event payload value is capped at
    500 characters while a single grounded Modelo 100 casilla diff encodes to a
    median 303, so serialising the detail into the event made a genuinely
    divergent Modelo 100 reconciliation unpersistable — the write raised before
    anything was saved. The event keeps the verdict and the divergence count;
    the record keeps the detail. ``event_id`` is the id of that co-written
    event, which is also the record's own storage key, so the two surfaces are
    joined by identity rather than by a field that could drift.

    ``diffs`` carries the grounding that was in force when the reconciliation
    ran, read straight from the record and never re-derived from the current
    registry — see :class:`ModeloReconciliationRecord`.
    """

    model_config = _STRICT_FROZEN

    event_id: BucketEventId
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    source_kind: ModeloReconciliationEvidenceKind
    source_path: str
    verdict: ModeloReconciliationVerdict
    diff_count: int = Field(ge=0)
    diffs: tuple[ModeloReconciliationDiff, ...] = ()
    actor: ModeloActorLabel
    reconciled_at: datetime

    @field_validator("reconciled_at")
    @classmethod
    def _reconciled_at_is_utc(cls, value: datetime) -> datetime:
        """Project the record's UTC instant under the same canonical contract."""
        return validate_utc_aware(value)


class ModeloReconciliationPersistencePort(Protocol):
    """Persistence boundary for history reads and atomic event co-commit."""

    def persist_with_event(self, record: ModeloReconciliationRecord, event: BucketEvent) -> None:
        """Atomically persist ``record`` and its matching bucket event."""
        ...

    def iter_records(self) -> Iterator[ModeloReconciliationRecord]:
        """Iterate authenticated records for the active profile."""
        ...


class ModeloReconciliationPersistenceFactory(Protocol):
    """Construct reconciliation persistence for one host context."""

    def __call__(self) -> ModeloReconciliationPersistencePort:
        """Return the active reconciliation persistence adapter."""
        ...


_BOUND_MODELO_RECONCILIATION_PERSISTENCE_FACTORY: ContextVar[ModeloReconciliationPersistenceFactory] = ContextVar(
    "cadrumo_modelo_reconciliation_persistence_factory"
)


@contextmanager
def bind_modelo_reconciliation_persistence_factory(
    factory: ModeloReconciliationPersistenceFactory,
) -> Generator[ModeloReconciliationPersistenceFactory]:
    """Bind the outward persistence factory for one host lifetime."""
    token = _BOUND_MODELO_RECONCILIATION_PERSISTENCE_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_MODELO_RECONCILIATION_PERSISTENCE_FACTORY.reset(token)


def modelo_reconciliation_persistence() -> ModeloReconciliationPersistencePort:
    """Resolve the explicitly composed reconciliation persistence adapter."""
    try:
        factory = _BOUND_MODELO_RECONCILIATION_PERSISTENCE_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("modelo reconciliation persistence has not been composed") from error
    return factory()


def list_modelo_reconciliations(
    *,
    bucket_id: BucketId,
    work_unit_id: WorkUnitId | None = None,
) -> tuple[ModeloReconciliationHistoryEntry, ...]:
    """Return every recorded reconciliation in ``bucket_id`` as typed entries.

    Reads the encrypted store the bound :class:`ModeloReconciliationPersistencePort`
    co-writes with each ``MODELO_RECONCILED``
    :class:`~domain.buckets.BucketEvent`, filtered to ``bucket_id`` and ordered
    oldest-first by the reconciliation instant. Each record is projected onto a
    typed :class:`ModeloReconciliationHistoryEntry` — verdict, source kind, diff
    count, the grounded diffs themselves, actor, and reconciliation instant are
    preserved, never collapsed to a flat ``dict[str, Any]``.

    The entry's ``event_id`` is the id of the bucket event written in the same
    unit of work, so an operator reading this history can join straight back to
    the event log without either side carrying a cross-reference field that
    could drift.

    An optional ``work_unit_id`` narrows the result to one work unit's
    reconciliation history. An empty result (no reconciliations recorded, or
    none for the requested work unit) returns an empty tuple — the clean "no
    reconciliations recorded yet" signal, not an error.
    """
    records = [
        record
        for record in modelo_reconciliation_persistence().iter_records()
        if record.bucket_id == bucket_id and (work_unit_id is None or record.work_unit_id == work_unit_id)
    ]
    # Storage order is the object-key digest order, not the reconciliation
    # order; the event id breaks a tie between two runs sharing an instant so
    # the listing is stable across reads.
    records.sort(key=lambda record: (record.reconciled_at, record.bucket_event_id))
    return tuple(
        ModeloReconciliationHistoryEntry(
            event_id=record.bucket_event_id,
            bucket_id=record.bucket_id,
            work_unit_id=record.work_unit_id,
            source_kind=record.source_kind,
            source_path=record.source_ref,
            verdict=record.verdict,
            diff_count=len(record.diffs),
            diffs=record.diffs,
            actor=record.actor,
            reconciled_at=record.reconciled_at,
        )
        for record in records
    )


__all__ = [
    "ModeloReconciliationHistoryEntry",
    "ModeloReconciliationPersistenceFactory",
    "ModeloReconciliationPersistencePort",
    "ModeloReconciliationRecord",
    "bind_modelo_reconciliation_persistence_factory",
    "list_modelo_reconciliations",
    "modelo_reconciliation_persistence",
]
