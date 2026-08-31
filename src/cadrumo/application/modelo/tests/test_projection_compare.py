"""Application compare-service provenance regression tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from .._projection import ModeloCompareDeltaRow, ModeloProjectionCasillaObservation, compare_modelo_years
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 25, 9, 0, tzinfo=UTC)
_BUCKET_ID = "13013013-0130-4130-8130-130130130130"
_M130_REVISION_ID = "2019-y-siguientes"


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="projection compare test casilla id")


def _m130_ingresos_registry_provenance() -> tuple[tuple[str, ...], tuple[str, ...]]:
    registry_casilla = next(
        item
        for item in bundled_authority().snapshot("130", filing_year=2026, period="1T").revision.casillas
        if item.id == _M130_INGRESOS_CASILLA
    )
    return tuple(registry_casilla.legal_refs), tuple(registry_casilla.source_refs)


def _seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    filing_year: int,
    clock: datetime,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "1T"),
        revision_id=_M130_REVISION_ID,
        repository=repository,
        clock=clock,
    )


def _seed_revision(
    repository: CalculationRevisionCatalogueRepository,
    *,
    work_unit: WorkUnit,
    value: Decimal,
    clock: datetime,
) -> CalculationRevision:
    values = {_M130_INGRESOS_CASILLA: value}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_M130_INGRESOS_CASILLA: str(value)},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_M130_INGRESOS_CASILLA: str(value)},
        binding_overrides={},
        casilla_values=values,
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=values,
        ),
        created_at=clock,
        updated_at=clock,
        verified_at=clock,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision


def test_compare_uses_revision_observation_rows_from_registry_snapshot(tmp_path: Path) -> None:
    """Comparison rows must not lose registry-grounded provenance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
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
                    UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
                ),
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_2025 = _seed_work_unit(
            work_repository,
            bucket_id=profile.bucket_id,
            filing_year=2025,
            clock=_T0,
        )
        work_2026 = _seed_work_unit(
            work_repository,
            bucket_id=profile.bucket_id,
            filing_year=2026,
            clock=_T0 + timedelta(minutes=1),
        )
        revision_2025 = _seed_revision(
            calculation_repository,
            work_unit=work_2025,
            value=Decimal("1000.00"),
            clock=_T0 + timedelta(minutes=2),
        )
        revision_2026 = _seed_revision(
            calculation_repository,
            work_unit=work_2026,
            value=Decimal("1500.00"),
            clock=_T0 + timedelta(minutes=3),
        )

        assert revision_2025.observations
        assert revision_2026.observations
        result = compare_modelo_years(modelo="130", years=(2025, 2026))

    row = next(item for item in result.delta_rows if item.casilla_id == _M130_INGRESOS_CASILLA)
    registry_casilla = next(
        item
        for item in bundled_authority().snapshot("130", filing_year=2026, period="1T").revision.casillas
        if item.id == _M130_INGRESOS_CASILLA
    )
    assert row.delta == Decimal("500.00")
    assert row.legal_refs == tuple(registry_casilla.legal_refs)
    assert row.source_refs == tuple(registry_casilla.source_refs)
    assert row.legal_refs, "comparison rows must not emit blank legal_refs"
    assert row.source_refs, "comparison rows must not emit blank source_refs"


def test_compare_reports_a_one_cent_delta_exactly_with_no_tolerance_absorption(tmp_path: Path) -> None:
    """The revision-vs-revision delta is the application's own arithmetic on both sides.

    Modelo 130's 2026 1T revision publishes a real, non-zero tolerance
    (``0.01``) for the OTHER per-casilla comparators that compare against
    AEAT, where rounding is an artefact. This comparator must NOT read that
    same tolerance: two of the app's OWN revisions differing by exactly that
    published cent differ by a cent, and absorbing it would hide a real
    change. Pinned against the real published value rather than a hardcoded
    literal, so this proves the comparator is genuinely exact rather than
    merely never having been fed a value small enough to matter.
    """
    published_tolerance = (
        bundled_authority().snapshot("130", filing_year=2026, period="1T").verification_policy().tolerance
    )
    assert published_tolerance == Decimal("0.01"), (
        "test precondition: modelo 130 2026 1T must publish a real, non-zero tolerance "
        "for this proof to demonstrate the delta comparator does NOT absorb it"
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
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
                    UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
                ),
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        work_2025 = _seed_work_unit(
            work_repository,
            bucket_id=profile.bucket_id,
            filing_year=2025,
            clock=_T0,
        )
        work_2026 = _seed_work_unit(
            work_repository,
            bucket_id=profile.bucket_id,
            filing_year=2026,
            clock=_T0 + timedelta(minutes=1),
        )
        _seed_revision(
            calculation_repository,
            work_unit=work_2025,
            value=Decimal("1000.00"),
            clock=_T0 + timedelta(minutes=2),
        )
        _seed_revision(
            calculation_repository,
            work_unit=work_2026,
            value=Decimal("1000.00") + published_tolerance,
            clock=_T0 + timedelta(minutes=3),
        )

        result = compare_modelo_years(modelo="130", years=(2025, 2026))

    row = next(item for item in result.delta_rows if item.casilla_id == _M130_INGRESOS_CASILLA)
    assert row.delta == published_tolerance, (
        "the delta comparator absorbed a genuine one-cent change, which the tree's other "
        "comparators are correct to do against AEAT-sourced data but which this comparator "
        "must never do against the application's own arithmetic on both sides"
    )


def test_projection_rows_reject_blank_registry_provenance_entries() -> None:
    """Projection result models must not accept whitespace provenance."""
    legal_refs, source_refs = _m130_ingresos_registry_provenance()

    with pytest.raises(ValidationError):
        ModeloProjectionCasillaObservation(
            casilla_id=_M130_INGRESOS_CASILLA,
            value=Decimal("1"),
            legal_refs=(" ",),
            source_refs=source_refs,
        )

    with pytest.raises(ValidationError):
        ModeloProjectionCasillaObservation(
            casilla_id=_M130_INGRESOS_CASILLA,
            value=Decimal("1"),
            legal_refs=legal_refs,
            source_refs=("",),
        )

    with pytest.raises(ValidationError):
        ModeloCompareDeltaRow(
            casilla_id=_M130_INGRESOS_CASILLA,
            label="Ingresos",
            section="Actividades economicas",
            year_a_value=Decimal("1"),
            year_b_value=Decimal("2"),
            delta=Decimal("1"),
            pct_change=Decimal("100.00"),
            formula_id=" ",
            legal_refs=legal_refs,
            source_refs=source_refs,
        )

    with pytest.raises(ValidationError):
        ModeloCompareDeltaRow(
            casilla_id=_M130_INGRESOS_CASILLA,
            label="Ingresos",
            section="Actividades economicas",
            year_a_value=Decimal("1"),
            year_b_value=Decimal("2"),
            delta=Decimal("1"),
            pct_change=Decimal("100.00"),
            legal_refs=legal_refs,
            source_refs=(" ",),
        )
