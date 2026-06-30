"""M111 retenciones observations feed the live bucket calculation path."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation._retencion_observations_repository import RetencionObservationRepository
from ...aggregation._retenciones import RetencionObservation, RetencionScheme
from ...user_profile import UserProfileLifecycleRepository
from .. import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics, create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000111"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)


def _professional_observation() -> RetencionObservation:
    return RetencionObservation(
        source_kind="ledger_transaction",
        source_object_id="professional-payment-001",
        perceptor_nif="12345678Z",
        perceptor_name="Profesional Ejemplo",
        scheme=RetencionScheme.PROFESSIONAL,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("150.00"),
        accrued_on="2026-03-15",
    )


def _seed_ready_profile(objects: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="M111 retenciones",
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="withholding operator activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def test_m111_professional_retencion_observation_calculates_activity_boxes(tmp_path: Path) -> None:
    """A persisted professional retención observation drives 07/08/09 and totals 28/30."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 retenciones") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(objects)
        period = Period.from_year_and_code(2026, "1T")
        RetencionObservationRepository().replace_observations(
            modelo="111",
            filing_year=2026,
            period=period,
            observations=[_professional_observation()],
            source_kind="aggregate_pull",
        )
        snapshot = resources().modelos.authority.snapshot("111", filing_year=2026, period="1T")
        wu_repo = WorkUnitCatalogueRepository(objects=objects)
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="111",
            filing_year=2026,
            period=period,
            revision_id=snapshot.revision.id,
            repository=wu_repo,
            clock=_T0,
        )

        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            work_unit_repository=wu_repo,
            calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            invoice_repository=InvoiceCatalogueRepository(objects=objects),
            clock=_T1,
        )

    values = result.revision.casilla_values
    assert values["07"] == Decimal("1")
    assert values["08"] == Decimal("1000.00")
    assert values["09"] == Decimal("150.00")
    assert values["28"] == Decimal("150.00")
    assert values["30"] == Decimal("150.00")
    assert result.source_diagnostics == ()
