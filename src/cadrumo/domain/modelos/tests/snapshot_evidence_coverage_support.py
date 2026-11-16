"""Revisions whose ledger filing snapshot and evidence cover chosen contributors, for coverage-gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ....core.casilla_id import CasillaId, validated_casilla_id
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...calculations.registry.tests.published_authority import published_selected_revision_id
from ..calculation_revision import CalculationRevision, CalculationRevisionState, derive_calculation_revision_id
from ..ledger_filing_snapshot import (
    LedgerEvidenceRow,
    LedgerFilingEvidence,
    LedgerFilingSnapshot,
    LedgerRowFingerprint,
    snapshot_fingerprint,
)

FILING_YEAR = filing_year_envelope().horizon
CAPTURED_AT = datetime(FILING_YEAR, 7, 1, 9, 0, 0, tzinfo=UTC)


def hex_seed(seed: str) -> str:
    """A 64-character hexadecimal-looking identifier built from ``seed``."""
    return (seed * 64)[:64]


TX_A = hex_seed("a")
TX_B = hex_seed("b")
ROW_FINGERPRINT = hex_seed("f")
EVIDENCE_INPUT_CASILLA: CasillaId = validated_casilla_id(
    "0001",
    surface="snapshot evidence coverage input casilla",
)
REGISTRY_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="303",
    revision_id=published_selected_revision_id("303", filing_year=FILING_YEAR, period="2T"),
    modelo_year=FILING_YEAR,
    period="2T",
)
_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("boe-modelo-303-form",)


def _evidence_row(transaction_id: str) -> LedgerEvidenceRow:
    return LedgerEvidenceRow(
        transaction_id=transaction_id,
        fingerprint=ROW_FINGERPRINT,
        booked_date=(CAPTURED_AT - timedelta(days=16)).date().isoformat(),
        amount=Decimal("100.00"),
        currency="EUR",
        direction="incoming",
        business_classification="business",
        lifecycle_state="confirmed",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def ledger_filing_revision(*, snapshot_ids: tuple[str, ...], evidence_ids: tuple[str, ...]) -> CalculationRevision:
    """A verified revision whose snapshot lists ``snapshot_ids`` and whose evidence lists ``evidence_ids``."""
    work_unit_id = hex_seed("9")
    rows = tuple(LedgerRowFingerprint(transaction_id=tid, fingerprint=ROW_FINGERPRINT) for tid in snapshot_ids)
    fingerprint = snapshot_fingerprint(rows)
    snapshot = LedgerFilingSnapshot(rows=rows, snapshot_fingerprint=fingerprint, captured_at=CAPTURED_AT)
    evidence = LedgerFilingEvidence(
        snapshot_fingerprint=fingerprint,
        rows=tuple(_evidence_row(tid) for tid in evidence_ids),
        captured_at=CAPTURED_AT,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={EVIDENCE_INPUT_CASILLA: "1"},
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=snapshot_ids,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=REGISTRY_SNAPSHOT_REF,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={EVIDENCE_INPUT_CASILLA: "1"},
        source_transaction_ids=snapshot_ids,
        ledger_filing_snapshot=snapshot,
        ledger_filing_evidence=evidence,
        created_at=CAPTURED_AT,
        updated_at=CAPTURED_AT,
        verified_at=CAPTURED_AT,
        verified_by="aeat.cli.modelo.verify",
        filing_instance_evidence=None,
        source_provenance=(),
    )
