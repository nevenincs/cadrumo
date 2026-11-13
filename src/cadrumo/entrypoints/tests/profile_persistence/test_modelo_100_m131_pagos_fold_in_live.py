"""M100 settles the Modelo 131 pagos fraccionados, never its módulos estimate.

This live application regression proves that stored Modelo 131 quarterly
observations reach the annual Modelo 100 only as pagos fraccionados: casilla
``15`` of each quarter folds into casilla ``0604`` through the registry
``relation_prefill`` mechanism. Casilla ``01`` restates each quarter the annual
net yield estimated from the datos-base of 1 January (RD 439/2007 art. 110.1.b),
which is not the year's rendimiento neto reducido, so it never reaches casilla
``1481`` or the ``1482``/``1484`` totals; the direct-estimation case calculates
without any Modelo 131 filing.

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
    ``renta-modelo-131-pagos-fraccionados``
        M100 relation that sums the quarterly Modelo 131 results into 0604.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from .file_flow_test_support import calculation_ports_for_test
from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .observation_seeding_support import save_stamped_observation
from .unchecked_credit_note_support import assert_only_unchecked_credit_notes

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

BUCKET_ID = "10013148-0000-4000-8000-000000001481"


__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


_YEAR = 2024
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_M100_ANNUAL_PERIOD = "0A"
_RELATION_PREFILL_SOURCE = "relation_prefill"

_M131_RENDIMIENTO_CASILLA: CasillaId = validated_casilla_id("01", surface="_M131_RENDIMIENTO_CASILLA")
_M131_RESULTADO_CASILLA: CasillaId = validated_casilla_id("15", surface="_M131_RESULTADO_CASILLA")
# Casilla 14 holds what earlier autoliquidaciones of the quarter already paid; an
# original filing has none, so it is zero.
_M131_PRIOR_RESULT_CASILLA: CasillaId = validated_casilla_id("14", surface="_M131_PRIOR_RESULT_CASILLA")
_M100_EO_RENDIMIENTO_CASILLA: CasillaId = validated_casilla_id("1481", surface="_M100_EO_RENDIMIENTO_CASILLA")
_M100_EO_SUM_CASILLA: CasillaId = validated_casilla_id("1482", surface="_M100_EO_SUM_CASILLA")
_M100_EO_TOTAL_CASILLA: CasillaId = validated_casilla_id("1484", surface="_M100_EO_TOTAL_CASILLA")
_M100_PAGOS_CASILLA: CasillaId = validated_casilla_id("0604", surface="_M100_PAGOS_CASILLA")
_M100_ANEXO_C_CARRY_CASILLAS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(box, surface="_M100_ANEXO_C_CARRY_CASILLAS") for box in ("1384", "1387", "1390", "1391")
)

#: Casilla 01 restates the same annual estimate every quarter.
_M131_ANNUAL_RENDIMIENTO_ESTIMATE = Decimal("5400.00")
_M131_PAGO_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("24.00"),
    "2T": Decimal("26.00"),
    "3T": Decimal("28.00"),
    "4T": Decimal("30.00"),
}
_EXPECTED_M131_PAGOS_TOTAL = Decimal("108.00")
_M131_PAGOS_RELATION: BindingId = "renta-modelo-131-pagos-fraccionados"


def _seed_taxpayer_profile(objects: SecureObjectRepository, *, estimation_regime: str) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="identity.name", value="Rosa"),
                    UserProfileFact(path="identity.surnames", value="Modulos"),
                    UserProfileFact(path="activities.description", value="actividad por modulos"),
                    # An IAE epigraph outside group 861, so no urban rental is carried on as an activity.
                    UserProfileFact(path="activities.iae_epigraph", value="844"),
                    UserProfileFact(path="iva.regime", value="SIMPLIFICADO"),
                    UserProfileFact(path="iva.m303_regime_composition", value="simplified"),
                    UserProfileFact(path="irpf.estimation_regime", value=estimation_regime),
                    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                    *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
                )
            ),
            created_at=_T0,
            updated_at=_T0,
            context=profile_creation_context_for_test(),
        ),
    )


def _seed_prior_year_m100_zero_carry(objects: SecureObjectRepository) -> None:
    save_stamped_observation(
        CalculationObservationRepository(objects=objects),
        RegistryModeloObservation(
            modelo="100",
            filing_year=_YEAR - 1,
            period=_M100_ANNUAL_PERIOD,
            observations=registry_grounded_observations(
                modelo="100",
                filing_year=_YEAR - 1,
                period=_M100_ANNUAL_PERIOD,
                casilla_values=dict.fromkeys(_M100_ANEXO_C_CARRY_CASILLAS, Decimal("0")),
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def seed_m131_quarters(objects: SecureObjectRepository) -> None:
    obs_repo = CalculationObservationRepository(objects=objects)
    for period, pago in _M131_PAGO_BY_PERIOD.items():
        save_stamped_observation(
            obs_repo,
            RegistryModeloObservation(
                modelo="131",
                filing_year=_YEAR,
                period=period,
                observations=registry_grounded_observations(
                    modelo="131",
                    filing_year=_YEAR,
                    period=period,
                    casilla_values={
                        _M131_RENDIMIENTO_CASILLA: _M131_ANNUAL_RENDIMIENTO_ESTIMATE,
                        _M131_RESULTADO_CASILLA: pago,
                        _M131_PRIOR_RESULT_CASILLA: Decimal("0"),
                    },
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )


def non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
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
            "retencion_soportada",
            *BUCKET_AGGREGATION_LOCK_SOURCES,
        )
    }


def calculate_m100_annual(
    objects: SecureObjectRepository, *, estimation_regime: str, operation: PinnedAuthorityOperation
):
    _seed_taxpayer_profile(objects, estimation_regime=estimation_regime)
    _seed_prior_year_m100_zero_carry(objects)
    wu_repo = WorkUnitCatalogueRepository(objects=objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=objects)
    bucket_event_repo = BucketEventHistoryRepository(objects=objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
    snapshot = published_authority_operation().snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _M100_ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bucket_event_repo),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bucket_event_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_262:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values=non_relation_zero_bindings(),
            ports=_calculation_ports_262,
            clock=_T1,
        )


def test_objective_estimation_profile_folds_m131_pagos_but_not_its_rendimiento_estimate(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    seed_m131_quarters(secure_objects)

    result = calculate_m100_annual(secure_objects, estimation_regime="objetiva", operation=operation)

    values = result.revision.casilla_values
    assert values[_M100_PAGOS_CASILLA] == _EXPECTED_M131_PAGOS_TOTAL
    assert Decimal(result.revision.binding_overrides[_M131_PAGOS_RELATION]) == _EXPECTED_M131_PAGOS_TOTAL
    # No quarterly Modelo 131 estimate reaches the year's rendimiento neto reducido.
    assert values[_M100_EO_RENDIMIENTO_CASILLA] == Decimal("0")
    assert values[_M100_EO_SUM_CASILLA] == Decimal("0")
    assert values[_M100_EO_TOTAL_CASILLA] == Decimal("0")
    assert_only_unchecked_credit_notes(result.source_diagnostics)


def test_direct_estimation_profile_calculates_without_modelo_131_filings(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    result = calculate_m100_annual(secure_objects, estimation_regime="directa_normal", operation=operation)

    assert result.revision.casilla_values[_M100_EO_RENDIMIENTO_CASILLA] == Decimal("0")
    assert result.revision.casilla_values[_M100_EO_SUM_CASILLA] == Decimal("0")
    assert result.revision.casilla_values[_M100_EO_TOTAL_CASILLA] == Decimal("0")
