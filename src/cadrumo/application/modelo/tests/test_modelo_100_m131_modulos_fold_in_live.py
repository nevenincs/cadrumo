"""M100 objective-estimation income folds in annual Modelo 131 módulos data.

This live application regression proves that stored Modelo 131 quarterly
observations feed the annual Modelo 100 estimación-objetiva módulos chain
through the registry ``relation_prefill`` mechanism. The objective-estimation
case sums Modelo 131 casilla ``01`` into the M100 relation-backed binding for
casilla ``1481`` and carries it through ``1482``/``1484``; the direct-estimation
case keeps that módulos-only binding at the explicit not-applicable zero.

See Also:
    :mod:`~application.modelo`
        Public application facade for work-unit creation and calculation
        revision orchestration.
    :mod:`~application.calculations`
        Observation repository and relation-prefill source facade used by the
        annual fold-in path.
    :mod:`~domain.calculations.registry`
        Registry authority for relation declarations, binding ids, casillas,
        and formula execution.
    ``renta-2024-modelo-131-rendimiento-neto-modulos``
        M100/2024 relation-backed binding populated from Modelo 131 casilla
        ``01``.
    ``renta-2024-rel-131-rendimiento-neto-modulos``
        M100/2024 relation that sums the quarterly Modelo 131 source
        observations.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import BindingId, RegistryModeloObservation
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository
from .. import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics, create_work_unit
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "10013148-0000-4000-8000-000000001481"
_YEAR = 2024
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_M100_ANNUAL_PERIOD = "0A"
_RELATION_PREFILL_SOURCE = "relation_prefill"

_M131_RENDIMIENTO_CASILLA: CasillaId = validated_casilla_id("01", surface="_M131_RENDIMIENTO_CASILLA")
_M131_RESULTADO_CASILLA: CasillaId = validated_casilla_id("15", surface="_M131_RESULTADO_CASILLA")
_M100_EO_RENDIMIENTO_CASILLA: CasillaId = validated_casilla_id("1481", surface="_M100_EO_RENDIMIENTO_CASILLA")
_M100_EO_SUM_CASILLA: CasillaId = validated_casilla_id("1482", surface="_M100_EO_SUM_CASILLA")
_M100_EO_TOTAL_CASILLA: CasillaId = validated_casilla_id("1484", surface="_M100_EO_TOTAL_CASILLA")
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="_M100_PAGOS_CASILLA")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "1391",
    surface="_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA",
)

_M131_RENDIMIENTO_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("1200.00"),
    "2T": Decimal("1300.00"),
    "3T": Decimal("1400.00"),
    "4T": Decimal("1500.00"),
}
_M131_PAGO_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("24.00"),
    "2T": Decimal("26.00"),
    "3T": Decimal("28.00"),
    "4T": Decimal("30.00"),
}
_EXPECTED_M131_RENDIMIENTO_TOTAL = Decimal("5400.00")
_EXPECTED_M131_PAGOS_TOTAL = Decimal("108.00")
_M131_RENDIMIENTO_BINDING: BindingId = "renta-2024-modelo-131-rendimiento-neto-modulos"
_M131_RENDIMIENTO_RELATION = "renta-2024-rel-131-rendimiento-neto-modulos"
_M131_PAGOS_RELATION = "renta-2024-rel-131-pagos-fraccionados"


def _seed_taxpayer_profile(objects: SecureObjectRepository, *, estimation_regime: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Rosa"),
                UserProfileFact(path="identity.surnames", value="Modulos"),
                UserProfileFact(path="activities.description", value="actividad por modulos"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="SIMPLIFICADO"),
                UserProfileFact(path="iva.m303_regime_composition", value="simplified"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value=estimation_regime),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                UserProfileFact(path="renta_taxpayer.sex", value="H"),
                UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
                UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
                UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
                UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _seed_prior_year_m100_zero_carry(objects: SecureObjectRepository) -> None:
    CalculationObservationRepository(objects=objects).save(
        CalculationObservationRepository(objects=objects).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo="100",
                filing_year=_YEAR - 1,
                period=_M100_ANNUAL_PERIOD,
                observations=registry_grounded_observations(
                    modelo="100",
                    filing_year=_YEAR - 1,
                    period=_M100_ANNUAL_PERIOD,
                    casilla_values={_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0")},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )


def _seed_m131_quarters(objects: SecureObjectRepository) -> None:
    obs_repo = CalculationObservationRepository(objects=objects)
    for period, rendimiento in _M131_RENDIMIENTO_BY_PERIOD.items():
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="131",
                    filing_year=_YEAR,
                    period=period,
                    observations=registry_grounded_observations(
                        modelo="131",
                        filing_year=_YEAR,
                        period=period,
                        casilla_values={
                            _M131_RENDIMIENTO_CASILLA: rendimiento,
                            _M131_RESULTADO_CASILLA: _M131_PAGO_BY_PERIOD[period],
                        },
                    ),
                ),
                source_kind=APP_FILING_SOURCE_KIND,
                captured_at=_T0,
            )
        )


def _non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id != "renta-2024-certificado-trabajo-retenciones"
        if binding.source
        not in (
            "profile",
            _RELATION_PREFILL_SOURCE,
            "ledger_renta_income_aggregation",
            "ledger_renta_gastos_estimacion_directa_aggregation",
            "ledger_iva_aggregation",
            "ledger_oss_aggregation",
            "collectible_invoice",
            "payable_invoice",
        )
    }


def _calculate_m100_annual(objects: SecureObjectRepository, *, estimation_regime: str):
    _seed_taxpayer_profile(objects, estimation_regime=estimation_regime)
    _seed_prior_year_m100_zero_carry(objects)
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _M100_ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values=_non_relation_zero_bindings(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def test_objective_estimation_profile_folds_m131_rendimiento_into_m100_modulos(
    secure_objects: SecureObjectRepository,
) -> None:
    _seed_m131_quarters(secure_objects)

    result = _calculate_m100_annual(secure_objects, estimation_regime="objetiva")

    values = result.revision.casilla_values
    assert values[_M100_EO_RENDIMIENTO_CASILLA] == _EXPECTED_M131_RENDIMIENTO_TOTAL
    assert values[_M100_EO_SUM_CASILLA] == _EXPECTED_M131_RENDIMIENTO_TOTAL
    assert values[_M100_EO_TOTAL_CASILLA] == _EXPECTED_M131_RENDIMIENTO_TOTAL
    assert values[_M100_PAGOS_CASILLA] == _EXPECTED_M131_PAGOS_TOTAL
    assert Decimal(result.revision.binding_overrides[_M131_RENDIMIENTO_BINDING]) == _EXPECTED_M131_RENDIMIENTO_TOTAL
    assert Decimal(result.revision.relation_overrides[_M131_RENDIMIENTO_RELATION]) == _EXPECTED_M131_RENDIMIENTO_TOTAL
    assert Decimal(result.revision.relation_overrides[_M131_PAGOS_RELATION]) == _EXPECTED_M131_PAGOS_TOTAL
    assert result.source_diagnostics == (), result.source_diagnostics


def test_direct_estimation_profile_keeps_m131_modulos_binding_at_not_applicable_zero(
    secure_objects: SecureObjectRepository,
) -> None:
    result = _calculate_m100_annual(secure_objects, estimation_regime="directa_normal")

    assert result.revision.casilla_values[_M100_EO_RENDIMIENTO_CASILLA] == Decimal("0")
    assert result.revision.casilla_values[_M100_EO_SUM_CASILLA] == Decimal("0.00")
    assert result.revision.casilla_values[_M100_EO_TOTAL_CASILLA] == Decimal("0.00")
    assert Decimal(result.revision.binding_overrides[_M131_RENDIMIENTO_BINDING]) == Decimal("0")
    assert Decimal(result.revision.relation_overrides[_M131_RENDIMIENTO_RELATION]) == Decimal("0")
