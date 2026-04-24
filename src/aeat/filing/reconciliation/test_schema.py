"""Unit tests for :mod:`aeat.filing.reconciliation._schema`.

Asserts strict / frozen / extra-forbid behaviour for every record and
locks the static :data:`KIND_TO_STATUS` mapping against the ADR table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._schema import FilingDraftStatus
from ._kind import FilingDivergenceKind
from ._schema import (
    KIND_TO_STATUS,
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


def _delta() -> CasillaDelta:
    return CasillaDelta(
        casilla_id="46",
        kind=FilingDivergenceKind.CASILLA_VALUE_MISMATCH,
        local_value="1234.56",
        remote_value="1235.56",
        delta=Decimal("-1.00"),
        narrative={"es": "es", "en": "en", "hu": "hu"},
    )


def test_reconciliation_status_carries_three_members() -> None:
    assert {m.value for m in ReconciliationStatus} == {"match", "divergent", "not_yet_found"}


def test_casilla_delta_is_frozen() -> None:
    delta = _delta()
    with pytest.raises(ValidationError):
        delta.casilla_id = "01"  # type: ignore[misc]


def test_casilla_delta_rejects_extras() -> None:
    with pytest.raises(ValidationError):
        CasillaDelta.model_validate(
            {
                "casilla_id": "46",
                "kind": FilingDivergenceKind.CASILLA_VALUE_MISMATCH,
                "local_value": "1.00",
                "remote_value": "2.00",
                "delta": Decimal("-1.00"),
                "narrative": {"es": "x", "en": "x", "hu": "x"},
                "unexpected": True,
            }
        )


def test_filing_draft_ref_round_trips() -> None:
    ref = _draft_ref()
    assert FilingDraftRef.model_validate(ref.model_dump()) == ref


def test_filing_draft_ref_is_strict_on_status() -> None:
    with pytest.raises(ValidationError):
        FilingDraftRef.model_validate(
            {
                "draft_id": "d",
                "modelo": "303",
                "period": "2026-1T",
                "profile_tax_id": "00000000T",
                "status": "NOT_A_STATUS",
            }
        )


def test_reconciliation_report_round_trips() -> None:
    report = ReconciliationReport(
        status=ReconciliationStatus.DIVERGENT,
        casilla_deltas=(_delta(),),
        remote_ref=None,
        draft_ref=_draft_ref(),
        reconciled_at=_NOW,
        narrative={"es": "es", "en": "en", "hu": "hu"},
    )
    assert ReconciliationReport.model_validate(report.model_dump()) == report


def test_reconciliation_report_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        ReconciliationReport.model_validate(
            {
                "status": ReconciliationStatus.MATCH,
                "casilla_deltas": (),
                "remote_ref": None,
                "draft_ref": _draft_ref(),
                "reconciled_at": datetime(2026, 4, 24, 12, 0),
                "narrative": {"es": "es", "en": "en", "hu": "hu"},
            }
        )


def test_kind_to_status_table_covers_every_kind() -> None:
    expected_keys = set(FilingDivergenceKind)
    actual_keys = set(KIND_TO_STATUS)
    assert actual_keys == expected_keys


def test_kind_to_status_table_matches_adr() -> None:
    assert KIND_TO_STATUS[FilingDivergenceKind.CASILLA_VALUE_MISMATCH] is ReconciliationStatus.DIVERGENT
    assert KIND_TO_STATUS[FilingDivergenceKind.CASILLA_MISSING_LOCAL] is ReconciliationStatus.DIVERGENT
    assert KIND_TO_STATUS[FilingDivergenceKind.CASILLA_EXTRA_LOCAL] is ReconciliationStatus.DIVERGENT
    assert KIND_TO_STATUS[FilingDivergenceKind.FILING_STATUS_DIVERGENCE] is ReconciliationStatus.DIVERGENT
    assert KIND_TO_STATUS[FilingDivergenceKind.ROUNDING_ONLY] is ReconciliationStatus.MATCH
    assert KIND_TO_STATUS[FilingDivergenceKind.FILING_NOT_YET_FOUND] is ReconciliationStatus.NOT_YET_FOUND


def test_kind_to_status_is_immutable() -> None:
    """The mapping is exposed as a :class:`types.MappingProxyType` view."""
    from types import MappingProxyType

    assert isinstance(KIND_TO_STATUS, MappingProxyType)
