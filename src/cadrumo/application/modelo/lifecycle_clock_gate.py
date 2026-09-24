"""Refusal for a lifecycle clock that precedes an instant the written records keep.

Every modelo lifecycle action stamps one clock onto the records it rewrites: a
calculation revision's ``updated_at``, a work unit's ``updated_at`` or
``discarded_at``, and a superseded filing record's ``superseded_at``. The
loaders of those catalogues reject a record whose stamp precedes the instant it
is ordered after (``created_at`` for a revision or work unit, ``filed_at`` for a
superseded filing record). A write that stamped an earlier clock would
therefore persist a catalogue its own loader refuses, leaving the bucket's
modelo history unreadable.

Each action names the instants its writes are ordered after through one of the
``*_ordering_instants`` helpers below and runs the gate before it persists
anything, so an out-of-order clock is refused as a typed operator-facing error
instead of being discovered on the next load.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.filing_record import ModeloRecord, ModeloRecordStatus
from ...domain.modelos.work_unit import WorkUnit


class ModeloLifecycleClockPrecedesError(ModeloError):
    """Raised when a lifecycle clock precedes an instant a rewritten record must not predate."""


class ModeloLifecycleClockOperation(StrEnum):
    """Lifecycle action whose clock the gate orders."""

    CALCULATE = "calculate"
    VERIFY = "verify"
    FILE = "file"
    AMEND = "amend"
    RENAME = "rename"
    DISCARD = "discard"


@dataclass(frozen=True, slots=True)
class LifecycleOrderingInstant:
    """One persisted instant that the action's clock must not precede.

    Attributes:
        subject: Stable identifier of the record field the clock is ordered
            after, such as ``calculation_revision.created_at``.
        record_id: Identifier of the record carrying the instant.
        instant: The persisted instant itself.
    """

    subject: str
    record_id: str
    instant: datetime


def work_unit_ordering_instants(work_unit: WorkUnit) -> tuple[LifecycleOrderingInstant, ...]:
    """Return the instant a rewrite of ``work_unit`` stamps its clock after.

    The work-unit loader orders both ``updated_at`` and ``discarded_at`` after
    ``created_at``, so this one instant covers calculate, rename, discard and
    every pointer advance.
    """
    return (
        LifecycleOrderingInstant(
            subject="work_unit.created_at",
            record_id=work_unit.work_unit_id,
            instant=work_unit.created_at,
        ),
    )


def _revision_created_at(revision: CalculationRevision) -> LifecycleOrderingInstant:
    return LifecycleOrderingInstant(
        subject="calculation_revision.created_at",
        record_id=revision.calculation_revision_id,
        instant=revision.created_at,
    )


def _superseded_record_filed_at(record: ModeloRecord) -> LifecycleOrderingInstant:
    return LifecycleOrderingInstant(
        subject="filing_record.filed_at",
        record_id=record.filing_record_id,
        instant=record.filed_at,
    )


def verification_ordering_instants(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
) -> tuple[LifecycleOrderingInstant, ...]:
    """Return the instants a granting verification stamps its clock after.

    The verified revision takes the clock as ``updated_at`` and a work unit
    whose current pointer is repaired takes it as ``updated_at``; both loaders
    order that stamp after ``created_at``.
    """
    return (_revision_created_at(revision), *work_unit_ordering_instants(work_unit))


def filing_ordering_instants(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    prior_current: ModeloRecord | None,
    prior_revision: CalculationRevision | None,
) -> tuple[LifecycleOrderingInstant, ...]:
    """Return the instants a local filing stamps its clock after.

    Besides the filed revision and the advanced work unit, a filing that
    supersedes ``prior_current`` stamps that record's ``superseded_at``, which
    its loader orders after ``filed_at``, and advances a still ``PRESENTADO``
    ``prior_revision``, whose ``updated_at`` is ordered after ``created_at``.
    """
    instants = list(verification_ordering_instants(revision=revision, work_unit=work_unit))
    if prior_current is not None:
        instants.append(_superseded_record_filed_at(prior_current))
    if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
        instants.append(_revision_created_at(prior_revision))
    return tuple(instants)


def amendment_ordering_instants(
    *,
    work_unit: WorkUnit,
    baseline: ModeloRecord,
    in_force: ModeloRecord,
) -> tuple[LifecycleOrderingInstant, ...]:
    """Return the instants an amendment stamps its clock after.

    The amendment revision is created at the clock, so it orders itself. The
    advanced work unit takes the clock as ``updated_at``. A still ``VIGENTE``
    ``baseline`` is superseded at the clock, and a pending ``in_force`` entry
    other than the baseline is retired at the clock; the filing-record loader
    orders each ``superseded_at`` after that record's ``filed_at``.
    """
    instants = list(work_unit_ordering_instants(work_unit))
    if baseline.status is ModeloRecordStatus.VIGENTE:
        instants.append(_superseded_record_filed_at(baseline))
    if in_force.filing_record_id != baseline.filing_record_id:
        instants.append(_superseded_record_filed_at(in_force))
    return tuple(instants)


def require_lifecycle_clock_not_before(
    clock: datetime,
    *,
    operation: ModeloLifecycleClockOperation,
    instants: Iterable[LifecycleOrderingInstant],
) -> None:
    """Refuse ``clock`` when it precedes any instant the action's writes are ordered after.

    Raises:
        ModeloLifecycleClockPrecedesError: ``clock`` is earlier than one of
            ``instants``; the first such instant is named in the context.
    """
    for ordering in instants:
        if clock < ordering.instant:
            raise ModeloLifecycleClockPrecedesError(
                translated_message="errors.refused.canonical_modelo_lifecycle_clock_precedes",
                context={
                    "operation": operation.value,
                    "clock": clock.isoformat(),
                    "subject": ordering.subject,
                    "record_id": ordering.record_id,
                    "instant": ordering.instant.isoformat(),
                },
            )
