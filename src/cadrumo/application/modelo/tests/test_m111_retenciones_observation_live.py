"""M111 retenciones observations feed the live bucket calculation path."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import AggregationCaptureKind, BindingSourceKind, Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    RetencionObservation,
    RetencionObservationRepository,
    RetencionScheme,
)
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from .._work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000111"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, 10, 0, tzinfo=UTC)


def _professional_observation() -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="professional-payment-001",
        perceptor_nif="12345678Z",
        perceptor_name="Profesional Ejemplo",
        scheme=RetencionScheme.PROFESSIONAL,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("150.00"),
        accrued_on="2026-03-15",
    )


def _administrador_observation() -> RetencionObservation:
    """An administrador/consejero retención at the LIRPF art. 101.2 fixed rate (35 %)."""
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="administrador-payment-001",
        perceptor_nif="87654321X",
        perceptor_name="Administrador Ejemplo",
        scheme=RetencionScheme.WORK_INCOME_DIRECTOR,
        taxable_base=Decimal("2000.00"),
        retencion_amount=Decimal("700.00"),  # 2000.00 * 0.35 (art. 101.2 general rate)
        accrued_on="2026-03-15",
    )


def _administrador_wrong_rate_observation() -> RetencionObservation:
    """An administrador retención withheld at 25 % — neither the 35 % nor the 19 % art. 101.2 rate."""
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="administrador-payment-002",
        perceptor_nif="87654321X",
        perceptor_name="Administrador Ejemplo",
        scheme=RetencionScheme.WORK_INCOME_DIRECTOR,
        taxable_base=Decimal("2000.00"),
        retencion_amount=Decimal("500.00"),  # 25 % — matches no art. 101.2 fixed rate
        accrued_on="2026-03-15",
    )


def _seed_ready_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="withholding operator activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                # Modelo 111 refuses a defaulted colegio-concertado declaration: the fichero
                # carries the row as filer data, so it must be stated rather than assumed.
                # False is the truthful value for this natural-person filer.
                UserProfileFact(path="withholding.colegio_concertado", value=False),
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
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        snapshot = bundled_authority().snapshot("111", filing_year=2026, period="1T")
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


def test_m111_administrador_retencion_observation_folds_into_trabajo_boxes(tmp_path: Path) -> None:
    """An administrador (clave E, art. 101.2) retención drives the trabajo boxes 01/02/03 and totals 28/30.

    Modelo 111 carries a single rendimientos-del-trabajo block, so the administrador/consejero
    retención reports there alongside ordinary empleados (the clave A/E split is only on Modelo
    190). The 700.00 withheld is the art. 101.2 fixed 35 % of the 2.000,00 base.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 retenciones") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(objects)
        period = Period.from_year_and_code(2026, "1T")
        RetencionObservationRepository().replace_observations(
            modelo="111",
            filing_year=2026,
            period=period,
            observations=[_administrador_observation()],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        snapshot = bundled_authority().snapshot("111", filing_year=2026, period="1T")
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
    assert values["01"] == Decimal("1")
    assert values["02"] == Decimal("2000.00")
    assert values["03"] == Decimal("700.00")
    assert values["28"] == Decimal("700.00")
    assert values["30"] == Decimal("700.00")
    assert result.source_diagnostics == ()


def test_m111_administrador_wrong_rate_surfaces_calculate_advisory(tmp_path: Path) -> None:
    """An administrador retención at a non-art.-101.2 rate surfaces a non-blocking calculate advisory.

    The withheld 500.00 on a 2.000,00 base is 25 %, which matches neither the fixed 35 %
    general rate nor the 19 % reduced rate of LIRPF art. 101.2. The trabajo boxes still fold
    the operator-supplied amounts (the advisory never overrides values), but the engine surfaces
    an ``administrador_retencion_rate_mismatch`` diagnostic so the operator can confirm the rate
    before filing (``no-silent-under-declaration``).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M111 retenciones") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(objects)
        period = Period.from_year_and_code(2026, "1T")
        RetencionObservationRepository().replace_observations(
            modelo="111",
            filing_year=2026,
            period=period,
            observations=[_administrador_wrong_rate_observation()],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        snapshot = bundled_authority().snapshot("111", filing_year=2026, period="1T")
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
    assert values["02"] == Decimal("2000.00")
    assert values["03"] == Decimal("500.00")
    mismatch = [d for d in result.source_diagnostics if d.reason == "administrador_retencion_rate_mismatch"]
    assert len(mismatch) == 1
    assert "87654321X" in mismatch[0].message
