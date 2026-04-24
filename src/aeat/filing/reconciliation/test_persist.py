"""Unit tests for :mod:`aeat.filing.reconciliation._persist`.

Asserts that the persistence adapter projects every non-rounding
:class:`CasillaDelta` onto its discriminated payload variant, that
``MATCH`` reports produce zero records, that record ids are stable
and content-addressed, and that the wrapping record carries the
existing :class:`aeat.sync.DivergenceClassification` and
:class:`aeat.sync.ResolutionState` enums verbatim.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...sync import DivergenceClassification, ResolutionState
from .._schema import FilingDraftStatus
from ._kind import FilingDivergenceKind
from ._persist import (
    CasillaExtraLocalPayload,
    CasillaMissingLocalPayload,
    CasillaValueMismatchPayload,
    FilingNotYetFoundPayload,
    FilingReconciliationDivergenceRecord,
    FilingStatusDivergencePayload,
    reconciliation_records,
)
from ._schema import (
    CasillaDelta,
    FilingDraftRef,
    ReconciliationReport,
    ReconciliationStatus,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_NOW = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)


def _draft_ref() -> FilingDraftRef:
    return FilingDraftRef(
        draft_id="draft-1",
        modelo="303",
        period="2026-1T",
        profile_tax_id="00000000T",
        status=FilingDraftStatus.APPROVED,
    )


def _delta(
    *,
    casilla_id: str = "46",
    kind: FilingDivergenceKind = FilingDivergenceKind.CASILLA_VALUE_MISMATCH,
    local_value: str | None = "1234.56",
    remote_value: str | None = "1235.56",
    delta: Decimal | None = Decimal("-1.00"),
) -> CasillaDelta:
    return CasillaDelta(
        casilla_id=casilla_id,
        kind=kind,
        local_value=local_value,
        remote_value=remote_value,
        delta=delta,
        narrative={"es": "x", "en": "x", "hu": "x"},
    )


def _report(
    *,
    status: ReconciliationStatus,
    deltas: tuple[CasillaDelta, ...],
) -> ReconciliationReport:
    return ReconciliationReport(
        status=status,
        casilla_deltas=deltas,
        remote_ref=None,
        draft_ref=_draft_ref(),
        reconciled_at=_NOW,
        narrative={"es": "x", "en": "x", "hu": "x"},
    )


def test_match_reports_produce_zero_records() -> None:
    report = _report(status=ReconciliationStatus.MATCH, deltas=())
    assert reconciliation_records(report) == ()


def test_rounding_only_deltas_are_skipped_on_divergent_records() -> None:
    """``ROUNDING_ONLY`` entries are non-blocking and not persisted."""
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(
            _delta(kind=FilingDivergenceKind.ROUNDING_ONLY, casilla_id="46", delta=Decimal("0.01")),
            _delta(kind=FilingDivergenceKind.CASILLA_VALUE_MISMATCH, casilla_id="71"),
        ),
    )
    records = reconciliation_records(report)
    assert len(records) == 1
    assert records[0].payload.kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH


def test_value_mismatch_payload_carries_signed_delta_string() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(_delta(kind=FilingDivergenceKind.CASILLA_VALUE_MISMATCH),),
    )
    records = reconciliation_records(report)
    assert len(records) == 1
    payload = records[0].payload
    assert isinstance(payload, CasillaValueMismatchPayload)
    assert payload.casilla_id == "46"
    assert payload.local_value == "1234.56"
    assert payload.remote_value == "1235.56"
    assert payload.delta == "-1.00"


def test_casilla_missing_local_payload() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(
            _delta(
                kind=FilingDivergenceKind.CASILLA_MISSING_LOCAL,
                casilla_id="07",
                local_value=None,
                remote_value="500.00",
                delta=None,
            ),
        ),
    )
    record = reconciliation_records(report)[0]
    assert isinstance(record.payload, CasillaMissingLocalPayload)
    assert record.payload.casilla_id == "07"
    assert record.payload.remote_value == "500.00"


def test_casilla_extra_local_payload() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(
            _delta(
                kind=FilingDivergenceKind.CASILLA_EXTRA_LOCAL,
                casilla_id="07",
                local_value="500.00",
                remote_value=None,
                delta=None,
            ),
        ),
    )
    record = reconciliation_records(report)[0]
    assert isinstance(record.payload, CasillaExtraLocalPayload)
    assert record.payload.local_value == "500.00"


def test_filing_status_divergence_payload() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(
            _delta(
                kind=FilingDivergenceKind.FILING_STATUS_DIVERGENCE,
                casilla_id="*",
                local_value="APPROVED",
                remote_value="rechazada",
                delta=None,
            ),
        ),
    )
    record = reconciliation_records(report)[0]
    assert isinstance(record.payload, FilingStatusDivergencePayload)
    assert record.payload.local_status == "APPROVED"
    assert record.payload.remote_status == "rechazada"


def test_filing_not_yet_found_payload() -> None:
    report = _report(
        status=ReconciliationStatus.NOT_YET_FOUND,
        deltas=(
            _delta(
                kind=FilingDivergenceKind.FILING_NOT_YET_FOUND,
                casilla_id="*",
                local_value=None,
                remote_value=None,
                delta=None,
            ),
        ),
    )
    record = reconciliation_records(report)[0]
    assert isinstance(record.payload, FilingNotYetFoundPayload)
    assert record.payload.expected_modelo == "303"
    assert record.payload.expected_period == "2026-1T"


def test_records_are_classified_as_breaking() -> None:
    """Filing-instance value divergence is by construction not auto-heal-safe."""
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(_delta(),),
    )
    record = reconciliation_records(report)[0]
    assert record.classification is DivergenceClassification.BREAKING


def test_records_default_resolution_state_is_pending() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(_delta(),),
    )
    record = reconciliation_records(report)[0]
    assert record.resolution_state is ResolutionState.PENDING


def test_record_id_is_stable_across_runs() -> None:
    """Same draft + same kind + same casilla yields the same record id."""
    delta = _delta()
    record_a = reconciliation_records(_report(status=ReconciliationStatus.DIVERGENT, deltas=(delta,)))[0]
    record_b = reconciliation_records(_report(status=ReconciliationStatus.DIVERGENT, deltas=(delta,)))[0]
    assert record_a.record_id == record_b.record_id


def test_record_id_changes_with_kind() -> None:
    """A different kind for the same casilla yields a different record id."""
    delta_value = _delta(kind=FilingDivergenceKind.CASILLA_VALUE_MISMATCH)
    delta_missing = _delta(
        kind=FilingDivergenceKind.CASILLA_MISSING_LOCAL,
        local_value=None,
        delta=None,
    )
    rec_a = reconciliation_records(_report(status=ReconciliationStatus.DIVERGENT, deltas=(delta_value,)))[0]
    rec_b = reconciliation_records(_report(status=ReconciliationStatus.DIVERGENT, deltas=(delta_missing,)))[0]
    assert rec_a.record_id != rec_b.record_id


def test_record_round_trips_via_model_dump() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(_delta(),),
    )
    record = reconciliation_records(report)[0]
    assert FilingReconciliationDivergenceRecord.model_validate(record.model_dump()) == record


def test_record_is_frozen() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(_delta(),),
    )
    record = reconciliation_records(report)[0]
    with pytest.raises(ValidationError):
        record.modelo = "999"  # type: ignore[misc]


def test_record_carries_modelo_and_period_from_draft_ref() -> None:
    report = _report(
        status=ReconciliationStatus.DIVERGENT,
        deltas=(_delta(),),
    )
    record = reconciliation_records(report)[0]
    assert record.modelo == "303"
    assert record.period == "2026-1T"
    assert record.draft_ref == report.draft_ref
