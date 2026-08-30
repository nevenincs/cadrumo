"""Post-roundtrip snapshot-vs-evidence coverage validator.

``assert_revision_snapshot_evidence_coverage`` cross-checks that a loaded
revision's ``ledger_filing_snapshot.rows`` and ``ledger_filing_evidence.rows``
cover the same contributor set. A deliberate mismatch (a contributor present in
the fingerprint snapshot but dropped from the evidence) must raise a typed
:class:`LedgerFilingCoverageError` that names the missing contributor.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from ..calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    LedgerFilingCoverageError,
    assert_revision_snapshot_evidence_coverage,
    derive_calculation_revision_id,
)
from ..ledger_filing_snapshot import (
    LedgerEvidenceRow,
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    LedgerRowFingerprint,
    snapshot_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_T0 = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)


def _hex(seed: str) -> str:
    return (seed * 64)[:64]


_TX_A = _hex("a")
_TX_B = _hex("b")
_FP = _hex("f")
_EVIDENCE_INPUT_CASILLA: CasillaId = validated_casilla_id(
    "0001",
    surface="snapshot evidence coverage input casilla",
)
_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("boe-modelo-303-2025-form",)


def _evidence_row(transaction_id: str) -> LedgerEvidenceRow:
    return LedgerEvidenceRow(
        transaction_id=transaction_id,
        fingerprint=_FP,
        booked_date="2024-06-15",
        amount=Decimal("100.00"),
        currency="EUR",
        direction="incoming",
        business_classification="business",
        lifecycle_state="confirmed",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _revision(*, snapshot_ids: tuple[str, ...], evidence_ids: tuple[str, ...]) -> CalculationRevision:
    work_unit_id = _hex("9")
    rows = tuple(LedgerRowFingerprint(transaction_id=tid, fingerprint=_FP) for tid in snapshot_ids)
    fingerprint = snapshot_fingerprint(rows)
    snapshot = LedgerFilingSnapshot(rows=rows, snapshot_fingerprint=fingerprint, captured_at=_T0)
    evidence = LedgerFilingEvidence(
        snapshot_fingerprint=fingerprint,
        rows=tuple(_evidence_row(tid) for tid in evidence_ids),
        captured_at=_T0,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_EVIDENCE_INPUT_CASILLA: "1"},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=snapshot_ids,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_EVIDENCE_INPUT_CASILLA: "1"},
        source_transaction_ids=snapshot_ids,
        ledger_filing_snapshot=snapshot,
        ledger_filing_evidence=evidence,
        created_at=_T0,
        updated_at=_T0,
        verified_at=_T0,
        verified_by="aeat.cli.modelo.verify",
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_matching_coverage_passes() -> None:
    """A revision whose snapshot and evidence cover the same contributors passes."""
    revision = _revision(snapshot_ids=(_TX_A, _TX_B), evidence_ids=(_TX_A, _TX_B))
    assert_revision_snapshot_evidence_coverage(revision)  # does not raise


def test_missing_contributor_in_evidence_raises_naming_it() -> None:
    """A contributor in the fingerprint snapshot but absent from evidence raises."""
    revision = _revision(snapshot_ids=(_TX_A, _TX_B), evidence_ids=(_TX_A,))
    with pytest.raises(LedgerFilingCoverageError) as raised:
        assert_revision_snapshot_evidence_coverage(revision)
    assert _TX_B in str(raised.value)
    assert "missing_from_evidence" in str(raised.value)


def test_extra_contributor_in_evidence_raises_naming_it() -> None:
    """A contributor in evidence but absent from the fingerprint snapshot raises."""
    revision = _revision(snapshot_ids=(_TX_A,), evidence_ids=(_TX_A, _TX_B))
    with pytest.raises(LedgerFilingCoverageError) as raised:
        assert_revision_snapshot_evidence_coverage(revision)
    assert _TX_B in str(raised.value)
    assert "extra_in_evidence" in str(raised.value)


def test_non_ledger_revision_passes_trivially() -> None:
    """A revision with neither snapshot nor evidence passes the coverage gate."""
    work_unit_id = _hex("9")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_EVIDENCE_INPUT_CASILLA: "1"},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_EVIDENCE_INPUT_CASILLA: "1"},
        created_at=_T0,
        updated_at=_T0,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert_revision_snapshot_evidence_coverage(revision)  # does not raise
