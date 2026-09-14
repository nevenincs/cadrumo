"""Export evidence policy for ledger-derived calculation revisions.

These tests exercise the application gate over an already assembled revision.
The encrypted calculation-repository round-trip is covered separately at the
profile-persistence adapter seam.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from cadrumo.domain.modelos.work_unit import derive_work_unit_id
from ..export import ModeloExportEvidenceMissingError, _raise_if_ledger_export_evidence_missing

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 3, 16, 0, tzinfo=UTC)
_TX_ID = "a" * 64
_BASE_CASILLA: CasillaId = validated_casilla_id("base", surface="_BASE_CASILLA")
_CUOTA_CASILLA: CasillaId = validated_casilla_id("cuota", surface="_CUOTA_CASILLA")


def _revision(
    *,
    source_transaction_ids: tuple[str, ...],
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None,
) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-operator",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="gate",
    )
    filing_instance_evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "1T"), reference="test:export-evidence-gate"
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        source_transaction_ids=source_transaction_ids,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="gate",
            modelo_year=2026,
            period="1T",
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("export-evidence-gate-test",),
            ),
        ),
        source_transaction_ids=source_transaction_ids,
        ledger_filing_snapshot=ledger_filing_snapshot,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )


def test_export_refuses_ledger_revision_without_bundled_evidence_or_reference() -> None:
    revision = _revision(source_transaction_ids=(_TX_ID,))

    with pytest.raises(ModeloExportEvidenceMissingError):
        _raise_if_ledger_export_evidence_missing(revision)


def test_export_allows_non_ledger_revision_without_evidence() -> None:
    revision = _revision(source_transaction_ids=())

    _raise_if_ledger_export_evidence_missing(revision)


def test_export_allows_ledger_revision_with_snapshot_reference() -> None:
    revision = _revision(
        source_transaction_ids=(_TX_ID,),
        ledger_filing_snapshot=LedgerFilingSnapshot(
            snapshot_fingerprint="f" * 64,
            captured_at=_NOW,
        ),
    )

    _raise_if_ledger_export_evidence_missing(revision)
