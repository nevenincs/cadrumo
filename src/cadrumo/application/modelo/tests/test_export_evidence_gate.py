"""Export evidence gate coverage for ledger-derived calculation revisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    LedgerFilingSnapshot,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
)
from ....tests import general_m303_filing_evidence
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from .._export import (
    ModeloExportCommand,
    ModeloExportEvidenceMissingError,
    _raise_if_ledger_export_evidence_missing,
    export_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 3, 16, 0, tzinfo=UTC)
_TX_ID = "a" * 64
_BASE_CASILLA: CasillaId = validated_casilla_id("base", surface="_BASE_CASILLA")
_CUOTA_CASILLA: CasillaId = validated_casilla_id("cuota", surface="_CUOTA_CASILLA")

active_profile = active_profile_isolated_backend_fixture(autouse=False, name="active_profile")


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


def test_export_service_refuses_ledger_revision_without_evidence_reference(
    active_profile: None,
    tmp_path: Path,
) -> None:
    revision = _revision(source_transaction_ids=(_TX_ID,))
    repository = CalculationRevisionCatalogueRepository()
    repository.save(upsert_calculation_revision(repository.load(), revision))
    output_path = tmp_path / "modelo-303.txt"

    with pytest.raises(ModeloExportEvidenceMissingError):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision.calculation_revision_id,
                output_path=output_path,
                actor="operator",
            ),
            workflow_profile=TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL),
            calculation_repository=repository,
        )

    assert not output_path.exists()


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
