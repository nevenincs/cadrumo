"""Filing-grade Modelo gates for cross-period clean-state proof."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.resources import resources
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogueRepository,
    CalculationRevisionState,
    derive_calculation_revision_id,
    upsert_calculation_revision,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    ModeloCrossPeriodCleanStateError,
    ModeloExportCommand,
    create_work_unit,
    export_modelo_revision,
    file_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _seed_verified_m390_revision(*, bucket_id: str) -> str:
    snapshot = resources().modelos.authority.snapshot("390", filing_year=2025, period="0A")
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="390",
        filing_year=2025,
        period="0A",
        revision_id=snapshot.revision.id,
        clock=_CLOCK,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        verified_at=_CLOCK,
        verified_by="operator-test",
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(upsert_calculation_revision(repo.load(), revision))
    return revision_id


def test_export_refuses_verified_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-export") as profile:
        revision_id = _seed_verified_m390_revision(bucket_id=profile.bucket_id)

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=revision_id,
                    output_path=tmp_path / "modelo-390.txt",
                    actor="operator-test",
                ),
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"


def test_file_refuses_verified_cross_period_revision_without_clean_sources(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cross-period-file") as profile:
        revision_id = _seed_verified_m390_revision(bucket_id=profile.bucket_id)

        with pytest.raises(ModeloCrossPeriodCleanStateError) as exc_info:
            file_modelo_revision(
                revision_id,
                actor="operator-test",
                workflow_profile=_workflow_profile(),
                clock=_CLOCK,
            )

    assert exc_info.value.translated_message == "application.modelo.errors.cross_period_clean_state_incomplete"
