"""Reconciliation records carry canonical identity, UTC instants, and grounding.

Two contracts the persisted reconciliation records documented but did not
enforce:

* ``bucket_event_id`` / ``event_id`` name the co-written
  :class:`~domain.buckets.BucketEvent`, whose identity is lowercase hex-64, and
  ``reconciled_at`` is documented as a canonical UTC history. Both were plain
  bounded strings and bare ``datetime``, so ``'bad'``, uppercase and non-hex
  identifiers and naive / ``+01:00`` instants were accepted — the identity could
  not join back to its event, and two reconciliations of one work unit could not
  be ordered.

* A ``total`` or ``casilla`` diff is documented as carrying the reconciling
  expectation's or casilla's ``legal_refs`` / ``source_refs``, but both tuples
  defaulted empty and unconstrained, so an ungrounded value divergence persisted
  and read back as if it were grounded. Header diffs compare filing identity
  rather than a regulated amount and legitimately carry none.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....core import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import derive_work_unit_id
from ..reconciliation_records import (
    ModeloReconciliationDiff,
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationHistoryEntry,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "7c7c7c7c-7c7c-47c7-87c7-7c7c7c7c7c7c"
_EVENT_ID = "a" * 64
_UTC_INSTANT = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id=_BUCKET_ID,
    modelo=ModeloCode("303"),
    filing_year=2026,
    period=Period.from_year_and_code(2026, "1T"),
    revision_id="2025-y-siguientes",
)
_GROUNDED_DIFF = ModeloReconciliationDiff(
    field_name="total_ingresar",
    work_unit_value="100.00",
    evidence_value="120.00",
    kind="total_ingresar_mismatch",
    diff_kind=ModeloReconciliationDiffKind.TOTAL,
    legal_refs=("ley-37-1992:art-92",),
    source_refs=("aeat-iva-2025",),
)


def _record(**overrides: object) -> ModeloReconciliationRecord:
    fields: dict[str, object] = {
        "bucket_event_id": _EVENT_ID,
        "bucket_id": _BUCKET_ID,
        "work_unit_id": _WORK_UNIT_ID,
        "source_kind": ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        "verdict": ModeloReconciliationVerdict.MISMATCHES,
        "diffs": (_GROUNDED_DIFF,),
        "actor": "aeat.cli.modelo.reconcile",
        "reconciled_at": _UTC_INSTANT,
    }
    fields.update(overrides)
    return ModeloReconciliationRecord.model_validate(fields)


def _history_entry(**overrides: object) -> ModeloReconciliationHistoryEntry:
    fields: dict[str, object] = {
        "event_id": _EVENT_ID,
        "bucket_id": _BUCKET_ID,
        "work_unit_id": _WORK_UNIT_ID,
        "source_kind": ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        "source_path": "justificante.pdf",
        "verdict": ModeloReconciliationVerdict.MISMATCHES,
        "diff_count": 1,
        "diffs": (_GROUNDED_DIFF,),
        "actor": "aeat.cli.modelo.reconcile",
        "reconciled_at": _UTC_INSTANT,
    }
    fields.update(overrides)
    return ModeloReconciliationHistoryEntry.model_validate(fields)


def test_valid_record_and_history_entry_construct() -> None:
    """The coherent shape the reconcile service writes is accepted.

    Positive control: without it every refusal below would also pass with the
    base fixture simply broken.
    """
    record = _record()
    entry = _history_entry()

    assert record.bucket_event_id == _EVENT_ID
    assert record.reconciled_at == _UTC_INSTANT
    assert entry.event_id == _EVENT_ID
    assert entry.diffs == (_GROUNDED_DIFF,)


@pytest.mark.parametrize("event_id", ["bad", "A" * 64, "z" * 64, "a" * 63, "a" * 65])
def test_record_refuses_a_non_canonical_event_identity(event_id: str) -> None:
    """The id must be the canonical lowercase hex-64 bucket-event identity."""
    with pytest.raises(ValidationError):
        _record(bucket_event_id=event_id)


@pytest.mark.parametrize("event_id", ["bad", "A" * 64, "z" * 64])
def test_history_entry_refuses_a_non_canonical_event_identity(event_id: str) -> None:
    """The projection is bound to the same identity contract as the record."""
    with pytest.raises(ValidationError):
        _history_entry(event_id=event_id)


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 5, 3, 12, 0),  # naive: the shape under test
        datetime(2026, 5, 3, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_record_refuses_a_non_utc_instant(instant: datetime) -> None:
    """A naive or offset instant cannot be ordered against a UTC history."""
    with pytest.raises(ValidationError):
        _record(reconciled_at=instant)


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 5, 3, 12, 0),  # naive: the shape under test
        datetime(2026, 5, 3, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_history_entry_refuses_a_non_utc_instant(instant: datetime) -> None:
    """The read-back projection holds the same UTC contract as the record."""
    with pytest.raises(ValidationError):
        _history_entry(reconciled_at=instant)


@pytest.mark.parametrize(
    "diff_kind",
    [ModeloReconciliationDiffKind.TOTAL, ModeloReconciliationDiffKind.CASILLA],
)
def test_value_diff_refuses_missing_grounding(diff_kind: ModeloReconciliationDiffKind) -> None:
    """A value-bearing divergence must carry its legal and source grounding."""
    with pytest.raises(ValidationError, match=r"must carry legal_refs and source_refs"):
        ModeloReconciliationDiff(
            field_name="27",
            work_unit_value="100.00",
            evidence_value="120.00",
            kind="casilla_value_mismatch",
            diff_kind=diff_kind,
        )


@pytest.mark.parametrize(
    ("legal_refs", "source_refs"),
    [
        ((), ("aeat-iva-2025",)),
        (("ley-37-1992:art-92",), ()),
    ],
)
def test_value_diff_refuses_half_grounding(
    legal_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
) -> None:
    """Both axes are required: one alone is not grounding."""
    with pytest.raises(ValidationError, match=r"must carry legal_refs and source_refs"):
        ModeloReconciliationDiff(
            field_name="27",
            work_unit_value="100.00",
            evidence_value="120.00",
            kind="casilla_value_mismatch",
            diff_kind=ModeloReconciliationDiffKind.CASILLA,
            legal_refs=legal_refs,
            source_refs=source_refs,
        )


def test_value_diff_refuses_malformed_reference_tokens() -> None:
    """References are the canonical registry aliases, not free text."""
    with pytest.raises(ValidationError):
        ModeloReconciliationDiff(
            field_name="27",
            work_unit_value="100.00",
            evidence_value="120.00",
            kind="casilla_value_mismatch",
            diff_kind=ModeloReconciliationDiffKind.CASILLA,
            legal_refs=("bad ref",),
            source_refs=("bad ref",),
        )


def test_header_diff_keeps_empty_grounding() -> None:
    """A header diff compares filing identity, not a regulated amount."""
    diff = ModeloReconciliationDiff(
        field_name="modelo",
        work_unit_value="303",
        evidence_value="130",
        kind="modelo_mismatch",
        diff_kind=ModeloReconciliationDiffKind.HEADER_FIELD,
    )

    assert diff.legal_refs == ()
    assert diff.source_refs == ()
