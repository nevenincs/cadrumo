"""Persisted export evidence gate coverage for ledger-derived revisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.modelo.export import (
    ModeloExportCommand,
    ModeloExportEvidenceMissingError,
    export_modelo_revision,
)
from cadrumo.application.modelo.export_ports import ModeloExportPorts
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _indexed_authority_for_test,
)
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from cadrumo.domain.modelos.work_unit import derive_work_unit_id

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 6, 3, 16, 0, tzinfo=UTC)
_TX_ID = "a" * 64
_BASE_CASILLA: CasillaId = validated_casilla_id("base", surface="_BASE_CASILLA")
_CUOTA_CASILLA: CasillaId = validated_casilla_id("cuota", surface="_CUOTA_CASILLA")

active_profile = active_profile_isolated_backend_fixture(autouse=False, name="active_profile")


def _inward_export_ports(*, calculation: object) -> ModeloExportPorts:
    """Provide application-owned fakes for authorities unused by this gate."""
    authority = Mock()
    return ModeloExportPorts(
        calculation=calculation,
        work_unit=authority,
        filing=authority,
        verification=authority,
        bucket_event=authority,
        observation=authority,
        iva_compensation_decision=authority,
        justificante=authority,
        prorrata_register=authority,
        bienes_inversion=authority,
        transaction=authority,
        draft_review_ports=Mock(),
    )


def _revision(
    *,
    source_transaction_ids: tuple[str, ...],
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None,
    operation: PinnedAuthorityOperation,
) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-operator",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="gate",
    )
    filing_instance_evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "1T"), reference="test:export-evidence-gate", operation=operation
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


def test_export_service_refuses_ledger_revision_without_evidence_reference(
    active_profile: None, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        revision = _revision(source_transaction_ids=(_TX_ID,), operation=operation)
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
                workflow_profile=TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime("GENERAL")),
                export_ports=_inward_export_ports(calculation=repository),
                operation=_authority_operation_for_test,
            )

        assert not output_path.exists()
