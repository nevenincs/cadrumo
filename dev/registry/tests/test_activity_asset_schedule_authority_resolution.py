"""Real-source resolution of 2025 activity-asset amortization elections.

Every expected amount is an independent hand calculation from the cited
provision, written out beside the assertion; none is copied from a run of the
code under test.  Proration follows the accepted day-count contract (service
days over 365 for 2025).
"""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from functools import cache
from itertools import pairwise

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetClaimState
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations, SupersedingClaimRequest
from cadrumo.application.actividad_asset.schedule_walk import PlanFigureAbsence
from cadrumo.application.actividad_asset.tests.ledger_support import MemoryLedger, acquisition_transaction
from cadrumo.application.actividad_asset.tests.register_support import MemoryRepository, memory_register_authority
from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.application.operator_actions.models import PreconditionVerdict
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    resolve_activity_asset_schedule_authority,
)
from cadrumo.domain.calculations.registry.actividad_asset_parameters import ACTIVITY_ASSET_PARAMETER_IDS
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim, effective_claims
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    ApprovedAmortizationPlan,
    ChargingInfrastructureEvidence,
    DefiniteUsefulLife,
    DigitOrder,
    DirectEstimationRegime,
    LowValueElection,
    OriginalPriceDetermination,
    PlanAnnualAmount,
    PlanApprovalKind,
    RenewableDocumentationKind,
    RenewableInstallationPurpose,
    RenewableSelfConsumptionEvidence,
    SmallEnterpriseEvidence,
    UsedAssetOriginalPrice,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetPeriodElapsedError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
)
from cadrumo.domain.renta.actividad_asset.vehicle_affectation import (
    ElectricPropulsion,
    VehicleAffectation,
    VehicleCategory,
    VehicleListedUse,
    VehiclePrivateUse,
)
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear

from ..compiler.loader import load_modelo_directory, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ERRORS = "ledger.actividad_asset.errors."


@contextmanager
def _refused(
    error_type: type[Exception],
    key: str,
    *,
    rendered: str | None = None,
    **context: object,
) -> Generator[None]:
    """Expect a refusal that carries catalogue ``key`` and the named context facts.

    ``rendered`` additionally matches the English text the catalogue produces for
    the refusal, so a legal citation the message must keep is still asserted.
    """
    with pytest.raises(error_type) as caught:
        yield
    error = caught.value
    assert getattr(error, "translated_message", None) == _ERRORS + key
    recorded = getattr(error, "context", None) or {}
    for name, value in context.items():
        assert recorded.get(name) == value, (name, recorded)
    if rendered is not None:
        assert re.search(rendered, resolve_error_message(error, locale="en")), rendered


@cache
def _acquisition() -> Transaction:
    """One payment large enough to bear every asset the tests register; the check bounds, not equates."""
    return acquisition_transaction(amount=Decimal("10000000.00"), taxable_base=None, iva_amount=None)


_YEAR_START = date(2025, 1, 1)
_YEAR_END = date(2026, 1, 1)
_DESCRIPTOR = ActivityAssetDescriptorFacts(name="Published-authority element")
_NORMAL = DirectEstimationRegime.NORMAL
_SIMPLIFIED = DirectEstimationRegime.SIMPLIFIED


def _modelo_100() -> ModeloRevision:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", "100")).revisions["2025"]


def _legal_reference(reference_id: str) -> LegalReference:
    return load_shared_catalogues(bundled_path("registry", "aeat")).legal[reference_id]


def _election(
    method: AmortizationMethod,
    regime: DirectEstimationRegime = _NORMAL,
    **facts: object,
) -> ActivityAssetAmortizationElection:
    return ActivityAssetAmortizationElection.model_validate({"regime": regime, "method": method, **facts})


def _asset(
    election: ActivityAssetAmortizationElection,
    *,
    basis: str,
    kind: AssetKind = AssetKind.MATERIAL,
    in_service: date = _YEAR_START,
    condition: AcquiredCondition = AcquiredCondition.NEW,
    residual: str = "0",
    opening: str = "0",
    opening_through: int | None = None,
    opening_method: AmortizationMethod | None = None,
    built: date | None = None,
    asset_id: str = "asset",
    vehicle: VehicleAffectation | None = None,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=_acquisition().transaction_id,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=kind,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal(basis),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="reviewed business allocation",
        ),
        residual_value=Decimal(residual),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal(opening),
            amortization_method=opening_method,
            covered_through_tax_year=(opening_through or in_service.year) if Decimal(opening) else None,
        ),
        acquired_condition=condition,
        building_construction_date=built,
        amortization=election,
        vehicle_affectation=vehicle,
    )


def _charge(
    asset: ActivityAssetRevision,
    *,
    covered_from: date = _YEAR_START,
    covered_until: date = _YEAR_END,
    history: AssetScheduleHistory | None = None,
    free_amount: str | None = None,
    workforce: tuple[PlantillaMediaYear, ...] = (),
) -> ScheduledAmortizationCharge:
    return forecast_activity_asset_charge(
        asset,
        modelo_100_revision=_modelo_100(),
        authority_generation="candidate-source",
        covered_from=covered_from,
        covered_until=covered_until,
        history=history or AssetScheduleHistory(),
        taxpayer_workforce=lambda: workforce,
        legal_reference=_legal_reference,
        requested_free_amount=Decimal(free_amount) if free_amount is not None else None,
    )


def _linear(class_key: str, regime: DirectEstimationRegime = _NORMAL, **facts: object):
    return _election(AmortizationMethod.LINEAR, regime, authority_class_key=class_key, **facts)


# --- Linear table (LIS art. 12.1.a; RIS art. 4) ---------------------------------------------


def test_linear_table_resolves_each_modality_maximum_from_source() -> None:
    normal = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=_asset(_linear("equipo-proceso-informacion"), basis="2000"),
        authority_generation="candidate-source",
        workforce=(),
        legal_reference=_legal_reference,
    )
    simplified = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=_asset(
            _linear("equipo-informacion-software", _SIMPLIFIED),
            basis="2000",
            kind=AssetKind.INTANGIBLE,
        ),
        authority_generation="candidate-source",
        workforce=(),
        legal_reference=_legal_reference,
    )

    assert normal.annual_rate == Decimal("0.25")
    assert simplified.annual_rate == Decimal("0.26")
    assert "metodo-admitido:key:material:linear" in normal.source_reference
    assert "coeficiente-lineal-maximo:key:equipo-proceso-informacion" in normal.source_reference


def test_two_thousand_euro_computer_forecasts_permitted_charge_not_purchase_cost() -> None:
    charge = _charge(_asset(_linear("equipo-proceso-informacion"), basis="2000.00"))

    # 2,000 x 25% for a full 2025 service year.
    assert charge.amount == Decimal("500.00")


def test_elected_linear_coefficient_is_bounded_by_the_maximum_and_the_maximum_period() -> None:
    # Processing equipment: maximum 25%, maximum period 8 years, so the floor is 1/8 = 12.5%.
    elected = _charge(_asset(_linear("equipo-proceso-informacion", linear_coefficient=Decimal("0.20")), basis="2000"))
    floor = _charge(_asset(_linear("equipo-proceso-informacion", linear_coefficient=Decimal("0.125")), basis="2000"))

    assert elected.amount == Decimal("400.00")  # 2,000 x 20%
    assert floor.amount == Decimal("250.00")  # 2,000 x 12.5%
    for outside in ("0.12", "0.26"):
        with _refused(ActividadAssetValidationError, "elected_coefficient_out_of_range"):
            _charge(_asset(_linear("equipo-proceso-informacion", linear_coefficient=Decimal(outside)), basis="2000"))


def test_first_partial_year_and_residual_value_use_the_amortizable_basis() -> None:
    partial = _charge(_asset(_linear("equipo-proceso-informacion"), basis="2000", in_service=date(2025, 7, 1)))
    residual = _charge(_asset(_linear("equipo-proceso-informacion"), basis="2000", residual="400"))

    assert partial.service_days == 184
    assert partial.amount == Decimal("252.05")  # 2,000 x 25% x 184/365 = 252.0548
    assert residual.amount == Decimal("400.00")  # (2,000 - 400) x 25%


def test_used_asset_may_double_the_maximum_only_in_the_normal_modality() -> None:
    used_machine = _charge(_asset(_linear("maquinaria"), basis="10000", condition=AcquiredCondition.USED))
    simplified_used = _charge(
        _asset(_linear("maquinaria", _SIMPLIFIED), basis="10000", condition=AcquiredCondition.USED),
    )

    assert used_machine.amount == Decimal("2400.00")  # 10,000 x (2 x 12%)
    assert simplified_used.amount == Decimal("1200.00")  # 10,000 x 12%, no doubling enrolled


def test_a_building_under_ten_years_old_is_not_a_used_asset() -> None:
    young = _charge(
        _asset(
            _linear("edificio-industrial"),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=date(2020, 1, 1),
        ),
    )
    old = _charge(
        _asset(
            _linear("edificio-industrial"),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=date(2015, 1, 1),
        ),
    )

    assert young.amount == Decimal("3000.00")  # five years old: 100,000 x 3%
    assert old.amount == Decimal("6000.00")  # exactly ten years old: 100,000 x (2 x 3%)
    with _refused(ActividadAssetIncompleteError, "used_building_requires_construction_date"):
        _charge(_asset(_linear("edificio-industrial"), basis="100000", condition=AcquiredCondition.USED))


# --- Used elements on their originating price (RIS art. 4.3.b and 4.3.c) --------------------
#
# RIS art. 4.3: "Tratandose de elementos patrimoniales del inmovilizado material e inversiones
# inmobiliarias que se adquieran usados, es decir, que no sean puestos en condiciones de
# funcionamiento por primera vez, el calculo de la amortizacion se efectuara de acuerdo con los
# siguientes criterios:
#   a) Sobre el precio de adquisicion, hasta el limite resultante de multiplicar por 2 la cantidad
#      derivada de aplicar el coeficiente de amortizacion lineal maximo.
#   b) Si se conoce el precio de adquisicion o coste de produccion originario, este podra ser
#      tomado como base para la aplicacion del coeficiente de amortizacion lineal maximo.
#   c) Si no se conoce el precio de adquisicion o coste de produccion originario, el contribuyente
#      podra determinar aquel pericialmente. Establecido dicho precio [...] se procedera de
#      acuerdo con lo previsto en la letra anterior."
# [...] "A los efectos de este apartado no se consideraran como elementos patrimoniales usados los
# edificios cuya antiguedad sea inferior a diez anos."
#
# Letter a doubles the coefficient on the acquisition price.  Letters b and c apply the single
# maximum coefficient (machinery: 12%) to the originating price, so 30,000 x 12% = 3,600.


def _original(
    price: str,
    determination: OriginalPriceDetermination = OriginalPriceDetermination.KNOWN,
    evidence: str | None = None,
) -> UsedAssetOriginalPrice:
    return UsedAssetOriginalPrice(
        determination=determination,
        original_price=Decimal(price),
        evidence_reference=evidence,
    )


def _used_machine(*, price: str = "30000.00", basis: str = "10000", **facts: object) -> ActivityAssetRevision:
    return _asset(
        _election(
            AmortizationMethod.LINEAR,
            _NORMAL,
            authority_class_key="maquinaria",
            used_original_price=_original(price),
            **facts,
        ),
        basis=basis,
        condition=AcquiredCondition.USED,
    )


def test_a_known_original_price_is_the_base_of_the_single_maximum_coefficient() -> None:
    asset = _used_machine()
    authority = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=asset,
        authority_generation="candidate-source",
        workforce=(),
        legal_reference=_legal_reference,
    )

    assert authority.annual_rate == Decimal("0.12")  # the table maximum, not twice it
    assert authority.original_price_basis == Decimal("30000.00")
    assert _charge(asset).amount == Decimal("3600.00")  # 30,000 x 12%, against 2,400 on the doubled acquisition price
    assert _charge(_used_machine(linear_coefficient=Decimal("0.10"))).amount == Decimal("3000.00")  # 30,000 x 10%


def test_the_original_price_route_is_limited_to_the_undoubled_maximum() -> None:
    at_maximum = _charge(_used_machine(linear_coefficient=Decimal("0.12")))

    assert at_maximum.amount == Decimal("3600.00")
    for above in ("0.1201", "0.24"):
        with _refused(ActividadAssetValidationError, "elected_coefficient_out_of_range", maximum=Decimal("0.12")):
            _charge(_used_machine(linear_coefficient=Decimal(above)))


def test_the_original_price_route_never_charges_beyond_the_elements_own_basis() -> None:
    # 100,000 x 12% = 12,000 would exceed the 10,000 the element cost, so only the cost remains.
    assert _charge(_used_machine(price="100000.00")).amount == Decimal("10000.00")


def test_an_expert_valuation_of_the_original_price_proceeds_as_a_known_price() -> None:
    valuation = _original("25000.00", OriginalPriceDetermination.EXPERT_VALUATION, "valuation-report-2025-001")
    asset = _asset(
        _linear("maquinaria", used_original_price=valuation),
        basis="10000",
        condition=AcquiredCondition.USED,
    )

    assert _charge(asset).amount == Decimal("3000.00")  # 25,000 x 12%
    with pytest.raises(ValueError, match="requires its evidence_reference"):
        _original("25000.00", OriginalPriceDetermination.EXPERT_VALUATION)


def test_a_change_of_original_price_is_a_change_of_election() -> None:
    plain = _asset(_linear("maquinaria"), basis="10000", condition=AcquiredCondition.USED)

    assert _used_machine(price="30000.00").amortization.fingerprint != (
        _used_machine(price="31000.00").amortization.fingerprint
    )
    assert _used_machine().amortization.fingerprint != plain.amortization.fingerprint


def test_an_original_price_is_a_fact_of_the_linear_method_only() -> None:
    with pytest.raises(ValueError, match="not a fact of the constant_percentage method"):
        _election(
            AmortizationMethod.CONSTANT_PERCENTAGE,
            authority_class_key="maquinaria",
            used_original_price=_original("30000.00"),
        )


def test_the_original_price_route_refuses_an_element_that_is_not_used() -> None:
    new_machine = _asset(
        _linear("maquinaria", used_original_price=_original("30000.00")),
        basis="10000",
        condition=AcquiredCondition.NEW,
    )

    with _refused(ActividadAssetUnsupportedError, "used_original_price_requires_used_asset", asset_id="asset"):
        _charge(new_machine)


def test_the_original_price_route_refuses_a_modality_without_a_used_asset_rule() -> None:
    simplified = _asset(
        _linear("maquinaria", _SIMPLIFIED, used_original_price=_original("30000.00")),
        basis="10000",
        condition=AcquiredCondition.USED,
    )

    with _refused(ActividadAssetUnsupportedError, "used_original_price_not_enrolled", regime="simplified"):
        _charge(simplified)


def test_the_original_price_route_follows_the_ten_year_building_rule() -> None:
    def building(built: date | None) -> ActivityAssetRevision:
        return _asset(
            _linear("edificio-industrial", used_original_price=_original("150000.00")),
            basis="100000",
            condition=AcquiredCondition.USED,
            built=built,
        )

    # Exactly ten years old on the in-service date: used, so 150,000 x 3%.
    assert _charge(building(date(2015, 1, 1))).amount == Decimal("4500.00")
    # One day short of ten years: not a used element, so the route does not apply.
    with _refused(ActividadAssetUnsupportedError, "used_original_price_requires_used_asset"):
        _charge(building(date(2015, 1, 2)))
    with _refused(ActividadAssetIncompleteError, "used_building_requires_construction_date"):
        _charge(building(None))


def test_the_original_price_route_does_not_combine_with_multi_shift_use() -> None:
    with _refused(ActividadAssetUnsupportedError, "multi_shift_with_used_asset_unsupported"):
        _charge(_used_machine(shift_hours_per_day=Decimal("16")))


def test_multi_shift_coefficient_follows_the_hours_formula() -> None:
    # Machinery: max 12%, period-implied 1/18. 16 hours: 1/18 + (12% - 1/18) x 16/8 = 24% - 1/18.
    charge = _charge(_asset(_linear("maquinaria", shift_hours_per_day=Decimal("16")), basis="18000"))

    assert charge.amount == Decimal("3320.00")  # 18,000 x 24% - 18,000/18 = 4,320 - 1,000
    with _refused(ActividadAssetValidationError, "multi_shift_requires_extra_shift"):
        _charge(_asset(_linear("maquinaria", shift_hours_per_day=Decimal("8")), basis="18000"))
    with _refused(ActividadAssetUnsupportedError, "multi_shift_not_enrolled", regime="simplified"):
        _charge(_asset(_linear("maquinaria", _SIMPLIFIED, shift_hours_per_day=Decimal("16")), basis="18000"))


def _small_enterprise(turnover: str, made_available: date = date(2025, 11, 15)) -> SmallEnterpriseEvidence:
    return SmallEnterpriseEvidence(
        evidence_reference="prior-year-accounts",
        made_available_on=made_available,
        prior_period_net_turnover=Decimal(turnover),
    )


def test_reduced_size_acceleration_doubles_the_maximum_for_a_new_element() -> None:
    # The AEAT 2025 manual's LIS art. 103 example: a EUR 36,000 machine in service on
    # 1 December. The manual illustrates with a month fraction (x 1/12 = EUR 720); the
    # only official unit, binding DGT consulta V1978-24, prorates by days in service over
    # the days of the year: 36,000 x 24% x 31/365 = 733.8082.
    charge = _charge(
        _asset(
            _linear("maquinaria", small_enterprise=_small_enterprise("2800000")),
            basis="36000",
            in_service=date(2025, 12, 1),
        ),
    )

    assert charge.amount == Decimal("733.81")
    with _refused(ActividadAssetUnsupportedError, "reduced_size_turnover_reached"):
        _charge(
            _asset(
                _linear("maquinaria", small_enterprise=_small_enterprise("10000000", made_available=_YEAR_START)),
                basis="36000",
            )
        )
    assert _charge(
        _asset(
            _linear("maquinaria", small_enterprise=_small_enterprise("9999999.99", made_available=_YEAR_START)),
            basis="36000",
        ),
    ).amount == Decimal("8640.00")  # 36,000 x 24%
    with _refused(ActividadAssetUnsupportedError, "reduced_size_acceleration_new_only"):
        _charge(
            _asset(
                _linear("maquinaria", small_enterprise=_small_enterprise("100", made_available=_YEAR_START)),
                basis="36000",
                condition=AcquiredCondition.USED,
            ),
        )


def test_used_doubling_is_limited_to_material_assets_where_it_is_enrolled() -> None:
    used_software = _charge(
        _asset(
            _linear("intangible-software"),
            basis="3000",
            kind=AssetKind.INTANGIBLE,
            condition=AcquiredCondition.USED,
        ),
    )
    simplified_used_building = _charge(
        _asset(
            _linear("edificio-otra-construccion", _SIMPLIFIED),
            basis="100000",
            condition=AcquiredCondition.USED,
        ),
    )

    # RIS art. 4.3 covers material assets only: 3,000 x 33%, not 66%.
    assert used_software.amount == Decimal("990.00")
    # The simplified table applies no used multiplier, so no construction date is needed: 100,000 x 3%.
    assert simplified_used_building.amount == Decimal("3000.00")


# --- Constant percentage (LIS art. 12.1.b; RIS art. 5) ---------------------------------------


def _constant(class_key: str, coefficient: str | None = None, regime: DirectEstimationRegime = _NORMAL):
    facts: dict[str, object] = {"authority_class_key": class_key}
    if coefficient is not None:
        facts["linear_coefficient"] = Decimal(coefficient)
    return _election(AmortizationMethod.CONSTANT_PERCENTAGE, regime, **facts)


def test_constant_percentage_weights_the_elected_coefficient_by_period_band() -> None:
    long_band = _charge(_asset(_constant("maquinaria"), basis="10000"))
    medium_band = _charge(_asset(_constant("equipo-electronico", "0.20"), basis="1000"))
    short_band = _charge(_asset(_constant("equipo-proceso-informacion", "0.25"), basis="1000"))
    floored = _charge(_asset(_constant("obra-civil-general", "0.02"), basis="100000"))

    assert long_band.amount == Decimal("3000.00")  # 12% -> 8.33 years -> x2.5 = 30%
    assert medium_band.amount == Decimal("400.00")  # 20% -> exactly 5 years -> x2 = 40%
    assert short_band.amount == Decimal("375.00")  # 25% -> 4 years -> x1.5 = 37.5%
    assert floored.amount == Decimal("11000.00")  # 2% -> 50 years -> x2.5 = 5%, floored at 11%


def test_constant_percentage_applies_to_the_value_pending_at_the_start_of_the_year() -> None:
    first_partial = _charge(_asset(_constant("maquinaria"), basis="10000", in_service=date(2025, 7, 1)))
    second_year = _charge(
        _asset(
            _constant("maquinaria"),
            basis="10000",
            in_service=date(2024, 1, 1),
            opening="3000",
            opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
        ),
    )
    with_residual = _charge(_asset(_constant("maquinaria"), basis="10000", residual="1000"))
    quarter_after_claim = _charge(
        _asset(_constant("maquinaria"), basis="10000"),
        covered_from=date(2025, 4, 1),
        covered_until=date(2025, 7, 1),
        history=AssetScheduleHistory(accumulated_in_tax_year=Decimal("739.73")),
    )

    assert first_partial.amount == Decimal("1512.33")  # 10,000 x 30% x 184/365 = 1,512.3288
    assert second_year.amount == Decimal("2100.00")  # (10,000 - 3,000) x 30%
    assert with_residual.amount == Decimal("2700.00")  # (10,000 - 1,000) x 30%
    # In-year claims do not change the start-of-year pending value: 10,000 x 30% accrues
    # 739.726 by 1 April and 1,487.671 by 1 July, so the quarter is 1,487.67 - 739.73.
    assert quarter_after_claim.amount == Decimal("747.94")


def test_constant_percentage_amortizes_everything_pending_in_the_final_year() -> None:
    # 25% elected -> 4-year life from 1 July 2021, concluding on 1 July 2025.
    asset = _asset(
        _constant("equipo-proceso-informacion", "0.25"),
        basis="10000",
        in_service=date(2021, 7, 1),
        opening="8000",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )

    whole_year = _charge(asset)
    first_quarter = _charge(asset, covered_until=date(2025, 4, 1))

    assert whole_year.covered_until == date(2025, 7, 1)
    assert whole_year.amount == Decimal("2000.00")  # the whole pending value
    assert first_quarter.amount == Decimal("994.48")  # 2,000 x 90/181 = 994.4751
    with pytest.raises(ActividadAssetPeriodElapsedError, match="amortization_period_elapsed"):
        _charge(asset, covered_from=date(2025, 8, 1))


def test_constant_percentage_final_year_intervals_telescope_to_the_pending_value() -> None:
    asset = _asset(
        _constant("equipo-proceso-informacion", "0.25"),
        basis="10000",
        in_service=date(2021, 7, 1),
        opening="9000",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )
    boundaries = (date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3), date(2025, 7, 1))

    amounts = [_charge(asset, covered_from=start, covered_until=end).amount for start, end in pairwise(boundaries)]

    # 1,000 pending over 181 final-year days: 5.52 + 5.53 + 988.95, no stranded cent.
    assert amounts == [Decimal("5.52"), Decimal("5.53"), Decimal("988.95")]
    assert sum(amounts, Decimal("0")) == Decimal("1000.00")


def test_a_from_start_method_refuses_an_unattested_opening_amount() -> None:
    unattested = _asset(_constant("maquinaria"), basis="10000", in_service=date(2024, 1, 1), opening="3000")
    other_method = _asset(
        _constant("maquinaria"),
        basis="10000",
        in_service=date(2024, 1, 1),
        opening="1200",
        opening_method=AmortizationMethod.LINEAR,
    )

    for asset in (unattested, other_method):
        with pytest.raises(ActividadAssetUnsupportedError, match="opening_amount_must_attest_from_start_method"):
            _charge(asset)


def test_constant_percentage_excludes_buildings_furniture_and_the_simplified_modality() -> None:
    for class_key in ("mobiliario", "edificio-industrial", "almacen-deposito", "util-herramienta"):
        with _refused(
            ActividadAssetUnsupportedError, "method_excludes_buildings_and_furniture", provision="RIS art. 5.2"
        ):
            _charge(_asset(_constant(class_key), basis="1000"))
    with _refused(
        ActividadAssetUnsupportedError, "method_excluded_by_law", rendered=r"excluded by law.*rd-439-2007:art-30"
    ):
        _charge(_asset(_constant("maquinaria", regime=_SIMPLIFIED), basis="1000"))


def test_constant_percentage_and_sum_of_digits_admit_the_intangibles_the_table_lists() -> None:
    constant = _charge(_asset(_constant("intangible-software"), basis="3000", kind=AssetKind.INTANGIBLE))
    digits = _charge(_asset(_digits("intangible-software", 4), basis="3000", kind=AssetKind.INTANGIBLE))

    # LIS art. 12.1.a lists software at 33%: 3.03 years is under 5, so RIS art. 5.1.a weights it
    # 1.5 to 49.5%, and 3,000 x 49.5% = 1,485.00.
    assert constant.amount == Decimal("1485.00")
    # Whole-year periods run from ceil(1 / 0.33) = 4 to the 6-year maximum; four years descending
    # gives the first year 4 of 10 digits: 3,000 x 4/10 = 1,200.00.
    assert digits.amount == Decimal("1200.00")


def test_simplified_intangible_table_methods_refuse_with_the_sources_that_leave_them_open() -> None:
    for election in (
        _constant("equipo-informacion-software", regime=_SIMPLIFIED),
        _election(
            AmortizationMethod.SUM_OF_DIGITS,
            _SIMPLIFIED,
            authority_class_key="equipo-informacion-software",
            sum_of_digits_period_years=4,
            digit_order=DigitOrder.DESCENDING,
        ),
    ):
        with _refused(
            ActividadAssetUnsupportedError,
            "simplified_intangible_table_method",
            rendered=r"RIRPF art\. 30\.1a.*Orden of 27 March 1998",
        ):
            _charge(_asset(election, basis="3000", kind=AssetKind.INTANGIBLE))


# --- Sum of digits (LIS art. 12.1.c; RIS art. 6) ---------------------------------------------


def _digits(class_key: str, period: int, order: DigitOrder = DigitOrder.DESCENDING):
    return _election(
        AmortizationMethod.SUM_OF_DIGITS,
        authority_class_key=class_key,
        sum_of_digits_period_years=period,
        digit_order=order,
    )


def test_sum_of_digits_allocates_quota_per_digit_in_either_order() -> None:
    # Machinery, 9 years: digit sum 45, quota 45,000 / 45 = 1,000 per digit.
    descending = _charge(_asset(_digits("maquinaria", 9), basis="45000"))
    ascending = _charge(_asset(_digits("maquinaria", 9, DigitOrder.ASCENDING), basis="45000"))
    mid_year = _charge(_asset(_digits("maquinaria", 9), basis="45000", in_service=date(2025, 7, 1)))

    assert descending.amount == Decimal("9000.00")  # digit 9
    assert ascending.amount == Decimal("1000.00")  # digit 1
    assert mid_year.amount == Decimal("4536.99")  # first life year 9,000 x 184/365 = 4,536.9863


def test_sum_of_digits_period_lies_between_the_coefficient_and_the_maximum_period() -> None:
    # Machinery: 12% implies 8.33 years, so whole-year periods run from 9 to the 18-year maximum.
    assert _charge(_asset(_digits("maquinaria", 18), basis="171000")).amount == Decimal("18000.00")  # 171,000 x 18/171
    for period in (8, 19):
        with _refused(ActividadAssetValidationError, "sum_of_digits_period_out_of_range"):
            _charge(_asset(_digits("maquinaria", period), basis="45000"))


def test_sum_of_digits_final_life_year_reaches_exactly_the_basis() -> None:
    asset = _asset(
        _digits("maquinaria", 9),
        basis="45000",
        in_service=date(2017, 1, 1),
        opening="44000",
        opening_method=AmortizationMethod.SUM_OF_DIGITS,
    )

    # 2025 is the ninth life year, digit 1: 1,000, which leaves nothing pending.
    assert _charge(asset).amount == Decimal("1000.00")


def test_sum_of_digits_excludes_buildings_and_furniture() -> None:
    for class_key in ("edificio-comercial-administrativo-servicios-vivienda", "enseres-otros"):
        with _refused(
            ActividadAssetUnsupportedError, "method_excludes_buildings_and_furniture", provision="RIS art. 6.2"
        ):
            _charge(_asset(_digits(class_key, 20), basis="1000"))


# --- Approved plan (LIS art. 12.1.d; RIS art. 7) ---------------------------------------------


def _plan(submitted: date = date(2024, 11, 1), amounts: tuple[tuple[int, str], ...] = ((2025, "5000"),)):
    return _election(
        AmortizationMethod.APPROVED_PLAN,
        approved_plan=ApprovedAmortizationPlan(
            approval_reference="resolution-2025-0001",
            approval_kind=PlanApprovalKind.EXPRESS,
            submitted_on=submitted,
            resolved_on=submitted + timedelta(days=60),
            annual_amounts=tuple(PlanAnnualAmount(tax_year=year, amount=Decimal(amount)) for year, amount in amounts),
        ),
    )


def test_approved_plan_charges_its_annual_distribution_over_service_days() -> None:
    plan = _plan(amounts=((2025, "5000"), (2026, "4000"), (2027, "3000")))

    assert _charge(_asset(plan, basis="12000")).amount == Decimal("5000.00")
    assert _charge(_asset(plan, basis="12000"), covered_until=date(2025, 4, 1)).amount == Decimal(
        "1232.88",
    )  # 5,000 x 90/365 = 1,232.8767


def test_approved_plan_refusals() -> None:
    with _refused(
        ActividadAssetUnsupportedError, "approved_plan_not_yet_effective", rendered=re.escape("RIS art. 7.8")
    ):
        _charge(_asset(_plan(submitted=date(2026, 1, 10)), basis="12000"))
    with pytest.raises(ActividadAssetValidationError, match="approved_plan_exceeds_basis"):
        _charge(_asset(_plan(amounts=((2025, "5000"), (2026, "8000"))), basis="12000"))
    with _refused(ActividadAssetUnsupportedError, "approved_plan_without_distribution"):
        _charge(_asset(_plan(amounts=((2026, "5000"),)), basis="12000"))
    simplified_plan = _plan().model_copy(update={"regime": _SIMPLIFIED})
    with _refused(ActividadAssetUnsupportedError, "method_excluded_by_law"):
        _charge(_asset(simplified_plan, basis="12000"))


# --- Intangibles (LIS art. 12.2) --------------------------------------------------------------


def test_definite_life_intangible_amortizes_over_its_evidenced_life() -> None:
    licence = _election(
        AmortizationMethod.INTANGIBLE_USEFUL_LIFE,
        useful_life=DefiniteUsefulLife(ends_on=date(2027, 1, 1), evidence_reference="licence-term"),
    )
    asset = _asset(licence, basis="3650", kind=AssetKind.INTANGIBLE)

    assert _charge(asset).amount == Decimal("1825.00")  # 3,650 x 365/730
    assert _charge(asset, covered_until=date(2025, 4, 1)).amount == Decimal("450.00")  # 3,650 x 90/730
    with _refused(ActividadAssetValidationError, "useful_life_must_end_after_service"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.INTANGIBLE_USEFUL_LIFE,
                    useful_life=DefiniteUsefulLife(ends_on=_YEAR_START, evidence_reference="bad"),
                ),
                basis="3650",
                kind=AssetKind.INTANGIBLE,
            ),
        )


def test_reduced_size_goodwill_and_indefinite_life_intangibles_deduct_150_percent_of_the_twentieth() -> None:
    evidence = _small_enterprise("2800000", made_available=_YEAR_START)
    goodwill = _charge(
        _asset(
            _election(AmortizationMethod.GOODWILL, small_enterprise=evidence),
            basis="40000",
            kind=AssetKind.INTANGIBLE,
            condition=AcquiredCondition.USED,
        ),
    )
    indefinite = _charge(
        _asset(
            _election(AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE, _SIMPLIFIED, small_enterprise=evidence),
            basis="20000",
            kind=AssetKind.INTANGIBLE,
        ),
    )

    # LIS art. 103.5 as the AEAT manual and DGT V0976-24 read it: 150% of the 5% art. 12.2
    # amount is 7.5%, so 40,000 x 7.5% = 3,000.00 and 20,000 x 7.5% = 1,500.00. Unlike
    # art. 103.1, the element need not be new, so acquired goodwill qualifies.
    assert goodwill.amount == Decimal("3000.00")
    assert indefinite.amount == Decimal("1500.00")
    with _refused(ActividadAssetUnsupportedError, "reduced_size_turnover_reached"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.GOODWILL,
                    small_enterprise=_small_enterprise("10000000", made_available=_YEAR_START),
                ),
                basis="40000",
                kind=AssetKind.INTANGIBLE,
            ),
        )


def test_indefinite_life_and_goodwill_are_limited_to_one_twentieth_in_both_modalities() -> None:
    indefinite = _charge(
        _asset(_election(AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE), basis="20000", kind=AssetKind.INTANGIBLE),
    )
    goodwill = _charge(
        _asset(_election(AmortizationMethod.GOODWILL, _SIMPLIFIED), basis="40000", kind=AssetKind.INTANGIBLE),
    )

    assert indefinite.amount == Decimal("1000.00")  # 20,000 / 20
    assert goodwill.amount == Decimal("2000.00")  # 40,000 / 20
    with _refused(ActividadAssetUnsupportedError, "method_not_enrolled_for_kind", asset_kind="material"):
        _charge(_asset(_election(AmortizationMethod.GOODWILL), basis="40000"))


# --- Free depreciation (LIS art. 12.3; DA 18a) -------------------------------------------------


def test_low_value_free_resolves_published_threshold_and_cap() -> None:
    authority = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=_asset(
            _election(
                AmortizationMethod.LOW_VALUE_FREE,
                authority_class_key="mobiliario",
                low_value=LowValueElection(
                    election_reference="operator-low-value-election",
                    new_material_evidence_reference="canonical-invoice-new-item-attestation",
                ),
            ),
            basis="300",
        ),
        authority_generation="candidate-source",
        workforce=(),
        legal_reference=_legal_reference,
    )

    assert authority.free_depreciation_unit_threshold == Decimal("300")
    assert authority.free_depreciation_annual_cap == Decimal("25000")
    assert "libertad-amortizacion-umbral-unitario" in authority.source_reference


def test_research_development_free_and_building_methods() -> None:
    machine = _asset(
        _election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
            authority_class_key="maquinaria",
            research_development_evidence_reference="rnd-project-affectation",
        ),
        basis="10000",
    )
    building = _asset(
        _election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING,
            authority_class_key="edificio-industrial",
            research_development_evidence_reference="rnd-building-affectation",
        ),
        basis="100000",
    )

    assert _charge(machine, free_amount="7000").amount == Decimal("7000.00")
    assert _charge(building).amount == Decimal("10000.00")  # 100,000 / 10 years
    with pytest.raises(ActividadAssetValidationError, match="free_amount_exceeds_remaining_basis"):
        _charge(machine, free_amount="10000.01")
    with _refused(ActividadAssetUnsupportedError, "research_development_free_excludes_buildings"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
                    authority_class_key="edificio-industrial",
                    research_development_evidence_reference="rnd",
                ),
                basis="100000",
            ),
            free_amount="1",
        )
    with _refused(ActividadAssetValidationError, "research_development_building_requires_building_class"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING,
                    authority_class_key="maquinaria",
                    research_development_evidence_reference="rnd",
                ),
                basis="100000",
            ),
        )


def test_charging_infrastructure_free_depreciation_window() -> None:
    def charger(in_service: date, condition: AcquiredCondition = AcquiredCondition.NEW) -> ActivityAssetRevision:
        return _asset(
            _election(
                AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE,
                authority_class_key="instalacion-resto",
                charging_infrastructure=ChargingInfrastructureEvidence(
                    technical_documentation_reference="rebt-memoria",
                    installation_certificate_reference="ccaa-certificate",
                ),
            ),
            basis="2500",
            in_service=in_service,
            condition=condition,
        )

    assert _charge(charger(date(2025, 3, 1)), free_amount="2500").amount == Decimal("2500.00")
    assert _charge(charger(date(2024, 6, 1)), free_amount="1500").amount == Decimal("1500.00")
    with _refused(
        ActividadAssetUnsupportedError, "charging_infrastructure_period_not_enrolled", rendered=re.escape("DA 18a.2")
    ):
        _charge(charger(date(2023, 6, 1)), free_amount="1500")
    with _refused(ActividadAssetUnsupportedError, "charging_infrastructure_new_only"):
        _charge(charger(date(2025, 3, 1), AcquiredCondition.USED), free_amount="100")


@pytest.mark.parametrize(
    ("method", "key", "provision"),
    [
        (AmortizationMethod.JUSTIFIED_AMOUNT, "justified_amount_unvalidated", "LIS art. 12.1.e"),
        (AmortizationMethod.ENTITY_REGIME_FREE, "entity_regime_not_individual", "LIS art. 12.3.a and 12.3.d"),
    ],
)
def test_statutory_methods_the_product_cannot_validate_refuse_with_their_provision(
    method: AmortizationMethod,
    key: str,
    provision: str,
) -> None:
    with _refused(ActividadAssetUnsupportedError, key, rendered=provision):
        _charge(_asset(_election(method), basis="1000"))


# --- Vehicles (LIRPF art. 29; RIRPF art. 22; LIS DA 18a.1) ------------------------------------


def _vehicle(
    category: VehicleCategory = VehicleCategory.PASSENGER_CAR,
    private_use: VehiclePrivateUse = VehiclePrivateUse.NONE,
    listed_use: VehicleListedUse | None = None,
    *,
    in_books: bool = True,
    propulsion: ElectricPropulsion | None = None,
) -> VehicleAffectation:
    return VehicleAffectation(
        category=category,
        private_use=private_use,
        listed_use=listed_use,
        recorded_in_activity_books=in_books,
        evidence_reference="vehicle-use-log",
        electric_propulsion=propulsion,
    )


def test_a_vehicle_class_charges_only_on_a_declaration_that_proves_affectation() -> None:
    car = _linear("transporte-externo")

    with _refused(
        ActividadAssetIncompleteError,
        "vehicle_affectation_required_for_class",
        rendered="vehicle affectation declaration",
    ):
        _charge(_asset(car, basis="20000"))
    # External transport is 16%: 20,000 x 16% = 3,200.00 for a car used only for the activity.
    assert _charge(_asset(car, basis="20000", vehicle=_vehicle())).amount == Decimal("3200.00")
    # A taxi keeps its accessory rest-day use under RIRPF art. 22.4 (b).
    taxi = _vehicle(
        private_use=VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME, listed_use=VehicleListedUse.PAID_PASSENGER_TRANSPORT
    )
    assert _charge(_asset(car, basis="20000", vehicle=taxi)).amount == Decimal("3200.00")
    # A delivery van outside the restricted categories keeps the general accessory-use allowance.
    van = _vehicle(VehicleCategory.OTHER_VEHICLE, VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME)
    assert _charge(_asset(car, basis="20000", vehicle=van)).amount == Decimal("3200.00")
    # A truck's table class cannot hold a restricted vehicle, so no declaration is needed: 20,000 x 20%.
    assert _charge(_asset(_linear("transporte-autocamion"), basis="20000")).amount == Decimal("4000.00")


def test_a_vehicle_not_proven_affected_refuses_with_its_provision() -> None:
    car = _linear("transporte-externo")
    refusals = (
        (_vehicle(private_use=VehiclePrivateUse.SHARED), "vehicle_shared_use", "22.2.1"),
        (
            _vehicle(private_use=VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME),
            "vehicle_private_use_category_restricted",
            "22.4",
        ),
        (
            _vehicle(VehicleCategory.MOTORCYCLE, VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME),
            "vehicle_private_use_category_restricted",
            "22.4",
        ),
        (_vehicle(in_books=False), "vehicle_missing_from_books", "22.2.2"),
    )
    for declaration, key, provision in refusals:
        with _refused(ActividadAssetUnsupportedError, key, rendered=re.escape(provision)):
            _charge(_asset(car, basis="20000", vehicle=declaration))
    # Simplified modality: the transport group is flagged too.
    with _refused(
        ActividadAssetIncompleteError,
        "vehicle_affectation_required_for_class",
        rendered="vehicle affectation declaration",
    ):
        _charge(_asset(_linear("transporte", _SIMPLIFIED), basis="20000"))


def test_the_goods_transport_use_belongs_to_a_mixed_vehicle_only() -> None:
    with pytest.raises(ValueError, match="mixed vehicle"):
        _vehicle(listed_use=VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT)
    assert (
        _vehicle(
            VehicleCategory.MIXED_VEHICLE,
            VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME,
            VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT,
        ).listed_use
        is VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT
    )


def test_electric_vehicle_free_depreciation_needs_an_affected_new_vehicle_in_the_window() -> None:
    election = _election(AmortizationMethod.ELECTRIC_VEHICLE_FREE, authority_class_key="transporte-externo")
    electric = _vehicle(propulsion=ElectricPropulsion.BEV)

    charged = _charge(_asset(election, basis="30000", vehicle=electric), free_amount="30000")

    assert charged.amount == Decimal("30000.00")
    with _refused(ActividadAssetIncompleteError, "electric_vehicle_propulsion_required"):
        _charge(_asset(election, basis="30000", vehicle=_vehicle()), free_amount="100")
    with _refused(ActividadAssetUnsupportedError, "electric_vehicle_new_only"):
        _charge(
            _asset(election, basis="30000", vehicle=electric, condition=AcquiredCondition.USED),
            free_amount="100",
        )
    with _refused(
        ActividadAssetUnsupportedError, "electric_vehicle_period_not_enrolled", rendered=re.escape("DA 18a.1")
    ):
        _charge(_asset(election, basis="30000", vehicle=electric, in_service=date(2023, 6, 1)), free_amount="100")
    with _refused(ActividadAssetUnsupportedError, "vehicle_shared_use", rendered=re.escape("22.2.1")):
        shared = _vehicle(private_use=VehiclePrivateUse.SHARED, propulsion=ElectricPropulsion.BEV)
        _charge(_asset(election, basis="30000", vehicle=shared), free_amount="100")


# --- Workforce-conditioned free depreciation (LIS art. 102; DA 17a) -------------------------------

_OBSERVED = PlantillaMediaState.OBSERVED
_COMMITTED = PlantillaMediaState.COMMITTED


def _workforce(*years: tuple[int, str, PlantillaMediaState]) -> tuple[PlantillaMediaYear, ...]:
    return tuple(
        PlantillaMediaYear(year=year, average_workforce=Decimal(average), state=state) for year, average, state in years
    )


# 2024 before; 2025 and 2026 after; 2027 and 2028 the further 24 months.
_GROWING = _workforce(
    (2024, "10.00", _OBSERVED),
    (2025, "12.00", _OBSERVED),
    (2026, "13.00", _COMMITTED),
    (2027, "13.00", _COMMITTED),
    (2028, "13.00", _COMMITTED),
)


def _employment() -> ActivityAssetAmortizationElection:
    return _election(
        AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE,
        authority_class_key="maquinaria",
        small_enterprise=_small_enterprise("5000000", made_available=date(2025, 2, 15)),
    )


def test_job_creating_free_depreciation_caps_the_investment_by_the_workforce_increase() -> None:
    machine = _asset(_employment(), basis="200000", in_service=date(2025, 3, 1))
    authority = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=machine,
        authority_generation="candidate-source",
        workforce=_GROWING,
        legal_reference=_legal_reference,
    )

    # 24 months after 1 January 2025: (12 x 365 + 13 x 365) / 730 = 12.50 against 10.00 before, an
    # increase of 2.50; LIS art. 102.1 lets 120,000 x 2.50 = 300,000.00 of investment benefit.
    assert authority.free_depreciation_investment_cap == Decimal("300000.00")
    assert "erd-empleo-inversion-por-unidad-plantilla" in authority.source_reference
    assert "taxpayer-profile:irpf.plantilla_media:2024:observed" in authority.source_reference
    assert "taxpayer-profile:irpf.plantilla_media:2028:committed" in authority.source_reference
    assert _charge(machine, free_amount="150000", workforce=_GROWING).amount == Decimal("150000.00")
    # The whole 300,000.00 fits the cap exactly; one cent more does not.
    assert _charge(
        _asset(_employment(), basis="300000", in_service=date(2025, 3, 1)),
        free_amount="300000",
        workforce=_GROWING,
    ).amount == Decimal("300000.00")
    with pytest.raises(ActividadAssetUnsupportedError, match="investment_cap_exceeded"):
        _charge(
            _asset(_employment(), basis="300000.01", in_service=date(2025, 3, 1)),
            free_amount="1",
            workforce=_GROWING,
        )


def test_job_creating_free_depreciation_refuses_each_unmet_condition() -> None:
    machine = _asset(_employment(), basis="200000", in_service=date(2025, 3, 1))

    with _refused(ActividadAssetIncompleteError, "workforce_year_not_declared", year=2027):
        _charge(machine, free_amount="1", workforce=tuple(item for item in _GROWING if item.year != 2027))
    with _refused(ActividadAssetIncompleteError, "workforce_year_not_declared", year=2024):
        _charge(machine, free_amount="1")
    flat = _workforce(*((year, "10.00", _OBSERVED) for year in range(2024, 2029)))
    with _refused(ActividadAssetUnsupportedError, "workforce_increase_not_reached"):
        _charge(machine, free_amount="1", workforce=flat)
    lost = _workforce(
        (2024, "10.00", _OBSERVED),
        (2025, "12.00", _OBSERVED),
        (2026, "13.00", _COMMITTED),
        (2027, "11.00", _COMMITTED),
        (2028, "11.00", _COMMITTED),
    )
    with _refused(ActividadAssetUnsupportedError, "workforce_increase_not_kept"):
        _charge(machine, free_amount="1", workforce=lost)
    with _refused(ActividadAssetUnsupportedError, "job_creation_new_only"):
        _charge(
            _asset(_employment(), basis="200000", in_service=date(2025, 3, 1), condition=AcquiredCondition.USED),
            free_amount="1",
            workforce=_GROWING,
        )
    large = _election(
        AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE,
        authority_class_key="maquinaria",
        small_enterprise=_small_enterprise("12000000", made_available=date(2025, 2, 15)),
    )
    with _refused(
        ActividadAssetUnsupportedError, "reduced_size_turnover_reached", rendered=re.escape("LIS art. 101.1")
    ):
        _charge(_asset(large, basis="200000", in_service=date(2025, 3, 1)), free_amount="1", workforce=_GROWING)
    with _refused(ActividadAssetUnsupportedError, "method_excluded_by_law", asset_kind="intangible"):
        _charge(
            _asset(
                _election(
                    AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE,
                    authority_class_key="equipo-proceso-informacion",
                    small_enterprise=_small_enterprise("5000000", made_available=date(2025, 2, 15)),
                ),
                basis="2000",
                kind=AssetKind.INTANGIBLE,
                in_service=date(2025, 3, 1),
            ),
            free_amount="1",
            workforce=_GROWING,
        )
    with pytest.raises(ValueError, match="requires small_enterprise"):
        _election(AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE, authority_class_key="maquinaria")


def test_assets_entering_service_together_share_one_investment_cap() -> None:
    operations, _ = _operations(_GROWING)

    def forecast(asset_id: str) -> ScheduledAmortizationCharge:
        return operations.forecast(
            asset_id=asset_id,
            covered_from=_YEAR_START,
            covered_until=_YEAR_END,
            requested_free_amount=Decimal("1000"),
        )

    operations.create(
        _asset(_employment(), basis="200000", in_service=date(2025, 3, 1), asset_id="first-machine"), _DESCRIPTOR
    )
    # A linear asset of the same year and a 2024 asset under the incentive draw on no 2025 cap.
    operations.create(
        _asset(_linear("maquinaria"), basis="500000", in_service=date(2025, 3, 1), asset_id="plain"), _DESCRIPTOR
    )
    operations.create(
        _asset(_employment(), basis="250000", in_service=date(2024, 3, 1), asset_id="earlier-year"), _DESCRIPTOR
    )

    assert forecast("first-machine").amount == Decimal("1000.00")

    # 200,000 + 150,000 = 350,000 of 2025 investment exceeds the 300,000.00 cap, so neither asset
    # is charged freely: the product does not choose which part of which asset benefits.
    operations.create(
        _asset(_employment(), basis="150000", in_service=date(2025, 6, 1), asset_id="second-machine"), _DESCRIPTOR
    )
    for asset_id in ("first-machine", "second-machine"):
        with pytest.raises(ActividadAssetUnsupportedError, match="investment_cap_exceeded"):
            forecast(asset_id)


def _renewable_evidence(
    purpose: RenewableInstallationPurpose = RenewableInstallationPurpose.ELECTRICITY_SELF_CONSUMPTION,
    documentation: RenewableDocumentationKind = RenewableDocumentationKind.LOW_VOLTAGE_CERTIFICATE,
    *,
    made_available: date = date(2025, 1, 10),
    replaces_fossil: bool = False,
    building_code: bool = False,
) -> RenewableSelfConsumptionEvidence:
    return RenewableSelfConsumptionEvidence(
        purpose=purpose,
        documentation_kind=documentation,
        documentation_reference="cie-2025-0042",
        made_available_on=made_available,
        replaces_fossil_installation=replaces_fossil,
        required_by_building_code=building_code,
    )


def _renewable(
    evidence: RenewableSelfConsumptionEvidence | None = None,
    class_key: str = "instalacion-resto",
) -> ActivityAssetAmortizationElection:
    return _election(
        AmortizationMethod.RENEWABLE_SELF_CONSUMPTION_FREE,
        authority_class_key=class_key,
        renewable_self_consumption=evidence or _renewable_evidence(),
    )


# 2024 before; 2025 and 2026 after; DA 17a.1 asks only that the average is kept.
_KEPT = _workforce((2024, "10.00", _OBSERVED), (2025, "10.00", _OBSERVED), (2026, "10.00", _COMMITTED))


def test_renewable_free_depreciation_charges_a_2025_installation_up_to_the_investment_cap() -> None:
    panels = _asset(_renewable(), basis="40000", in_service=date(2025, 2, 1))
    authority = resolve_activity_asset_schedule_authority(
        _modelo_100(),
        tax_year=2025,
        asset_revision=panels,
        authority_generation="candidate-source",
        workforce=_KEPT,
        legal_reference=_legal_reference,
    )

    assert authority.free_depreciation_investment_cap == Decimal("500000")
    assert "renewable-documentation:low_voltage_certificate:cie-2025-0042" in authority.source_reference
    assert "taxpayer-profile:irpf.plantilla_media:2026:committed" in authority.source_reference
    assert _charge(panels, free_amount="40000", workforce=_KEPT).amount == Decimal("40000.00")
    heat = _renewable(
        _renewable_evidence(
            RenewableInstallationPurpose.THERMAL_OWN_USE,
            RenewableDocumentationKind.ENERGY_EFFICIENCY_CERTIFICATE,
            replaces_fossil=True,
        ),
    )
    assert _charge(
        _asset(heat, basis="9000", in_service=date(2025, 5, 1)), free_amount="9000", workforce=_KEPT
    ).amount == (Decimal("9000.00"))
    # The installation made available on the day RDL 18/2022 entered into force qualifies.
    first_day = _renewable(_renewable_evidence(made_available=date(2022, 10, 20)))
    assert _charge(
        _asset(first_day, basis="1000", in_service=date(2025, 2, 1)), free_amount="1000", workforce=_KEPT
    ).amount == (Decimal("1000.00"))
    with pytest.raises(ActividadAssetUnsupportedError, match="investment_cap_exceeded"):
        _charge(_asset(_renewable(), basis="500000.01", in_service=date(2025, 2, 1)), free_amount="1", workforce=_KEPT)


def test_renewable_free_depreciation_refuses_each_unmet_condition() -> None:
    def refused(
        election: ActivityAssetAmortizationElection,
        key: str,
        *,
        in_service: date = date(2025, 2, 1),
        rendered: str | None = None,
    ) -> None:
        with _refused(ActividadAssetUnsupportedError, key, rendered=rendered):
            _charge(_asset(election, basis="40000", in_service=in_service), free_amount="1", workforce=_KEPT)

    refused(_renewable(class_key="edificio-industrial"), "renewable_excludes_buildings")
    refused(
        _renewable(
            _renewable_evidence(
                RenewableInstallationPurpose.THERMAL_OWN_USE,
                RenewableDocumentationKind.THERMAL_PROCESS_REGISTRATION,
            ),
        ),
        "renewable_thermal_requires_fossil_replacement",
        rendered="fossil energy",
    )
    refused(
        _renewable(_renewable_evidence(building_code=True)),
        "renewable_mandatory_installation_unsupported",
        rendered=re.escape("DA 17a.5"),
    )
    refused(
        _renewable(_renewable_evidence(made_available=date(2022, 10, 19))),
        "renewable_made_available_before_admitted_date",
    )
    refused(
        _renewable(_renewable_evidence(made_available=date(2024, 1, 10))),
        "renewable_entry_year_not_enrolled",
        in_service=date(2024, 6, 1),
    )
    shrinking = _workforce((2024, "10.00", _OBSERVED), (2025, "9.00", _OBSERVED), (2026, "9.50", _COMMITTED))
    with _refused(ActividadAssetUnsupportedError, "workforce_fell_below", rendered=re.escape("LIS DA 17a.1")):
        _charge(_asset(_renewable(), basis="40000", in_service=date(2025, 2, 1)), free_amount="1", workforce=shrinking)
    with _refused(ActividadAssetUnsupportedError, "method_excluded_by_law", asset_kind="intangible"):
        _charge(
            _asset(
                _renewable(class_key="equipo-proceso-informacion"),
                basis="2000",
                kind=AssetKind.INTANGIBLE,
                in_service=date(2025, 2, 1),
            ),
            free_amount="1",
            workforce=_KEPT,
        )
    with pytest.raises(ValueError, match=re.escape("DA 17a.6")):
        _renewable_evidence(documentation=RenewableDocumentationKind.ENERGY_EFFICIENCY_CERTIFICATE)


def test_renewable_free_depreciation_is_taken_only_in_the_entry_year() -> None:
    """A window reaching an earlier entry year still refuses a later period's free charge."""
    revision = _modelo_100()
    widened = revision.model_copy(
        update={
            "parameters": tuple(
                parameter.model_copy(
                    update={
                        "values": tuple(
                            value.model_copy(update={"value": Decimal("2024")}) for value in parameter.values
                        )
                    },
                )
                if parameter.id == "renta-actividad-inmovilizado-amortizacion-renovables-primer-ejercicio"
                else parameter
                for parameter in revision.parameters
            ),
        },
    )
    installed_2024 = _asset(
        _renewable(_renewable_evidence(made_available=date(2024, 1, 10))),
        basis="40000",
        in_service=date(2024, 6, 1),
    )

    with _refused(ActividadAssetUnsupportedError, "renewable_only_in_entry_period"):
        resolve_activity_asset_schedule_authority(
            widened,
            tax_year=2025,
            asset_revision=installed_2024,
            authority_generation="candidate-source",
            workforce=_workforce((2023, "10.00", _OBSERVED), (2024, "10.00", _OBSERVED), (2025, "10.00", _OBSERVED)),
            legal_reference=_legal_reference,
        )


def test_methods_the_workforce_does_not_condition_never_read_it() -> None:
    def unreadable() -> tuple[PlantillaMediaYear, ...]:
        raise AssertionError("the average workforce was read for a method it does not condition")

    charge = forecast_activity_asset_charge(
        _asset(_linear("maquinaria"), basis="10000"),
        modelo_100_revision=_modelo_100(),
        authority_generation="candidate-source",
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        history=AssetScheduleHistory(),
        taxpayer_workforce=unreadable,
        legal_reference=_legal_reference,
    )

    assert charge.amount == Decimal("1200.00")  # machinery 12% of 10,000


def test_unknown_class_and_kind_mismatch_fail_closed() -> None:
    with _refused(ActividadAssetUnsupportedError, "table_class_without_group_classification"):
        _charge(_asset(_linear("caller-invented-class"), basis="1000"))
    with _refused(ActividadAssetUnsupportedError, "table_class_wrong_kind", asset_kind="intangible"):
        _charge(_asset(_linear("mobiliario"), basis="1000", kind=AssetKind.INTANGIBLE))


def test_the_declared_read_set_names_only_parameters_the_revision_declares() -> None:
    """The orphan check trusts this set, so a stale id in it would hide nothing but mislead."""
    declared = {parameter.id for parameter in _modelo_100().parameters}

    assert declared >= ACTIVITY_ASSET_PARAMETER_IDS, sorted(ACTIVITY_ASSET_PARAMETER_IDS - declared)


def test_an_absent_admission_parameter_fails_closed() -> None:
    revision = _modelo_100()
    stripped = revision.model_copy(
        update={
            "parameters": tuple(
                parameter
                for parameter in revision.parameters
                if parameter.id != "renta-actividad-inmovilizado-amortizacion-normal-metodo-admitido"
            ),
        },
    )

    with _refused(ActividadAssetUnsupportedError, "parameter_absent"):
        resolve_activity_asset_schedule_authority(
            stripped,
            tax_year=2025,
            asset_revision=_asset(_linear("mobiliario"), basis="1000"),
            authority_generation="candidate-source",
            workforce=(),
            legal_reference=_legal_reference,
        )


# --- Change of method and shared operations -------------------------------------------------


def _operations(
    workforce: tuple[PlantillaMediaYear, ...] = (),
) -> tuple[ActivityAssetOperations, MemoryRepository]:
    def forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=_modelo_100(),
            authority_generation="published-registry-test-generation",
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=lambda: workforce,
            legal_reference=_legal_reference,
            requested_free_amount=requested_free_amount,
        )

    repository = MemoryRepository()
    return (
        ActivityAssetOperations(
            repository=repository,
            ledger=MemoryLedger(_acquisition()),
            forecast_operation=forecast,
            taxpayer_modality=lambda: DirectEstimationRegime.NORMAL,
            register_authority=memory_register_authority(),
        ),
        repository,
    )


def test_a_change_of_method_inside_a_claimed_tax_year_refuses() -> None:
    operations, _ = _operations()
    linear = _asset(_linear("maquinaria"), basis="10000", asset_id="switching-machine")
    operations.create(linear, _DESCRIPTOR)
    first_quarter = operations.forecast(
        asset_id=linear.asset_id,
        covered_from=_YEAR_START,
        covered_until=date(2025, 4, 1),
    )
    operations.record_claim(first_quarter, creating_operation="test.linear-q1")
    switched = linear.model_copy(
        update={
            "revision_number": 2,
            "supersedes_revision_id": linear.revision_id,
            "amortization": _constant("maquinaria"),
        },
    )
    operations.correct(switched)

    assert first_quarter.amount == Decimal("295.89")  # 10,000 x 12% x 90/365 = 295.8904
    with pytest.raises(ActividadAssetValidationError, match="election_changes_only_at_year_boundary"):
        operations.forecast(asset_id=linear.asset_id, covered_from=date(2025, 4, 1), covered_until=date(2025, 7, 1))


def test_constant_percentage_and_sum_of_digits_cannot_be_adopted_after_another_method() -> None:
    constant = _asset(
        _constant("maquinaria"),
        basis="10000",
        in_service=date(2024, 1, 1),
        opening="1200",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )
    earlier_linear = AssetScheduleHistory(election_fingerprints_before_tax_year=(_linear("maquinaria").fingerprint,))
    earlier_same = AssetScheduleHistory(election_fingerprints_before_tax_year=(constant.amortization.fingerprint,))

    with pytest.raises(ActividadAssetUnsupportedError, match="from_start_method_after_other_election"):
        _charge(constant, history=earlier_linear)
    assert _charge(constant, history=earlier_same).amount == Decimal("2640.00")  # (10,000 - 1,200) x 30%
    # A move to linear from a tax-year boundary is admitted and runs on the remaining basis.
    linear = _asset(_linear("maquinaria"), basis="10000", in_service=date(2024, 1, 1), opening="3000")
    after_constant = AssetScheduleHistory(election_fingerprints_before_tax_year=(constant.amortization.fingerprint,))
    assert _charge(linear, history=after_constant).amount == Decimal("1200.00")  # 10,000 x 12%


def test_an_undeclared_vehicle_refuses_with_its_correction_action_until_corrected() -> None:
    operations, _ = _operations()
    car = _asset(_linear("transporte-externo"), basis="20000", asset_id="undeclared-car")
    operations.create(car, _DESCRIPTOR)

    with pytest.raises(ActividadAssetIncompleteError) as refused:
        operations.forecast(asset_id=car.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)

    verdict = refused.value.terminal_precondition_verdict
    assert isinstance(verdict, PreconditionVerdict)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.ledger.actividad_asset.correct_revision"
    assert verdict.missing_argument_names == ("revision_json",)
    assert verdict.evidence[0].values["asset_id"] == "undeclared-car"
    assert verdict.evidence[0].values["revision_id"] == car.revision_id
    assert refused.value.context == {"asset_id": "undeclared-car", "class_key": "transporte-externo"}
    assert "vehicle" in resolve_error_message(refused.value, locale="en").lower()
    assert "aeat " not in resolve_error_message(refused.value, locale="en")
    corrected = car.model_copy(
        update={"revision_number": 2, "supersedes_revision_id": car.revision_id, "vehicle_affectation": _vehicle()},
    )
    operations.correct(corrected)
    # The corrected car is used only for the activity: 20,000 x 16% = 3,200.00.
    forecast = operations.forecast(asset_id=car.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)
    assert forecast.amount == Decimal("3200.00")


def test_a_superseding_claim_is_forecast_without_the_claim_it_replaces() -> None:
    operations, repository = _operations()
    machine = _asset(
        _linear("maquinaria"),
        basis="1000",
        in_service=date(2017, 1, 1),
        opening="950",
        asset_id="nearly-amortized-machine",
    )
    operations.create(machine, _DESCRIPTOR)
    first = operations.forecast(asset_id=machine.asset_id, covered_from=_YEAR_START, covered_until=date(2025, 4, 1))
    operations.record_claim(first, creating_operation="test.q1")
    second = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=date(2025, 4, 1),
        covered_until=date(2025, 7, 1),
    )
    second_claim = operations.record_claim(second, creating_operation="test.q2").claim
    corrected = machine.model_copy(
        update={"revision_number": 2, "supersedes_revision_id": machine.revision_id, "residual_value": Decimal("10")},
    )
    before = repository.history

    # Counting the claim it would replace, 950 + 29.59 + 20.41 exceeds the corrected 990 basis.
    with pytest.raises(ActividadAssetClaimConflictError, match="correction_below_effective_claims"):
        operations.correct(corrected)
    assert repository.history == before

    history = operations.correct(
        corrected,
        (SupersedingClaimRequest(supersedes_claim_id=second_claim.claim_id),),
        origin="test.q2-corrected",
    )
    replacement = history.claims[-1]

    # 1,000 x 12% x 90/365 = 29.59; the second quarter is capped at the 20.41 left of the 50.00 pending.
    assert (first.amount, second.amount) == (Decimal("29.59"), Decimal("20.41"))
    # Without it, the corrected 990 basis leaves 990 - 950 - 29.59 = 10.41.
    assert replacement.amount == Decimal("10.41")
    effective = {claim.claim_id: claim.amount for claim in effective_claims(repository.history.claims)}
    assert second_claim.claim_id not in effective
    assert sum(effective.values(), Decimal("0")) == Decimal("40.00")


def test_a_forecast_cannot_supersede_a_claim_the_asset_does_not_have() -> None:
    operations, _ = _operations()
    machine = _asset(_linear("maquinaria"), basis="1000", asset_id="no-claims-machine")
    operations.create(machine, _DESCRIPTOR)

    with pytest.raises(ActividadAssetValidationError, match="superseded_claim_not_effective"):
        operations.forecast(
            asset_id=machine.asset_id,
            covered_from=_YEAR_START,
            covered_until=_YEAR_END,
            supersedes_claim_id="c" * 64,
        )


def test_the_history_write_refuses_a_claim_under_a_superseded_revision() -> None:
    machine = _asset(_linear("maquinaria"), basis="1000", asset_id="corrected-before-write")
    corrected = machine.model_copy(
        update={"revision_number": 2, "supersedes_revision_id": machine.revision_id, "residual_value": Decimal("10")},
    )
    history = ActivityAssetHistory(revisions=(machine, corrected))
    stale = AmortizationClaim.from_schedule(
        _charge(machine, covered_until=date(2025, 7, 1)),
        asset_kind=machine.asset_kind,
        creating_operation="test.stale-revision",
    )

    with pytest.raises(ActividadAssetClaimConflictError, match="claim_not_under_current_revision"):
        history.record_claim(stale)


def test_two_forecasts_taken_before_recording_cannot_both_consume_the_basis() -> None:
    operations, repository = _operations()
    machine = _asset(
        _election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
            authority_class_key="maquinaria",
            research_development_evidence_reference="rnd-project-affectation",
        ),
        basis="10000",
        asset_id="rnd-machine",
    )
    operations.create(machine, _DESCRIPTOR)
    first_half = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=_YEAR_START,
        covered_until=date(2025, 7, 1),
        requested_free_amount=Decimal("10000"),
    )
    second_half = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=date(2025, 7, 1),
        covered_until=_YEAR_END,
        requested_free_amount=Decimal("10000"),
    )

    operations.record_claim(first_half, creating_operation="test.rnd-first-half")
    with pytest.raises(ActividadAssetValidationError, match="free_amount_exceeds_remaining_basis"):
        operations.record_claim(second_half, creating_operation="test.rnd-second-half")
    assert sum((claim.amount for claim in repository.history.claims), Decimal("0")) == Decimal("10000")


def test_a_hand_edited_forecast_is_refused_at_record_time() -> None:
    operations, _ = _operations()
    machine = _asset(_linear("maquinaria"), basis="10000", asset_id="edited-machine")
    operations.create(machine, _DESCRIPTOR)
    forecast = operations.forecast(asset_id=machine.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)
    inflated = forecast.model_copy(update={"amount": Decimal("5000.00")})

    with pytest.raises(ActividadAssetValidationError, match="forecast_no_longer_matches"):
        operations.record_claim(inflated, creating_operation="test.inflated")


def test_the_history_write_refuses_a_claim_beyond_the_basis_even_without_operations() -> None:
    machine = _asset(_linear("maquinaria"), basis="1000", asset_id="direct-write-machine")
    first_half = _charge(machine, covered_until=date(2025, 7, 1))
    second_half = _charge(machine, covered_from=date(2025, 7, 1))
    history = ActivityAssetHistory(revisions=(machine,))
    after_first = history.record_claim(
        AmortizationClaim.from_schedule(first_half, asset_kind=machine.asset_kind, creating_operation="test.first"),
    ).history
    beyond = AmortizationClaim.from_schedule(
        second_half.model_copy(update={"amount": Decimal("950.00")}),
        asset_kind=machine.asset_kind,
        creating_operation="test.beyond",
    )

    # First half: 1,000 x 12% x 181/365 = 59.51; adding 950.00 would reach 1,009.51 of a 1,000 basis.
    assert first_half.amount == Decimal("59.51")
    with pytest.raises(ActividadAssetClaimConflictError, match="claims_exceed_amortizable_basis"):
        after_first.record_claim(beyond)


def test_low_value_free_real_authority_forecast_records_one_idempotent_claim() -> None:
    operations, _ = _operations()
    asset = _asset(
        _election(
            AmortizationMethod.LOW_VALUE_FREE,
            authority_class_key="mobiliario",
            low_value=LowValueElection(
                election_reference="operator-elected-full-amount",
                new_material_evidence_reference="canonical-new-material-invoice",
            ),
        ),
        basis="300.00",
        asset_id="published-free-depreciation-tool",
    )
    operations.create(asset, _DESCRIPTOR)
    forecast = operations.forecast(
        asset_id=asset.asset_id,
        covered_from=_YEAR_START,
        covered_until=_YEAR_END,
        requested_free_amount=Decimal("300.00"),
    )
    first = operations.record_claim(forecast, creating_operation="test.real-authority-free-depreciation")
    retry = operations.record_claim(forecast, creating_operation="test.real-authority-free-depreciation")

    assert forecast.amount == Decimal("300.00")
    assert first.claim.method is AmortizationMethod.LOW_VALUE_FREE
    assert retry.reused_existing_claim is True
    with pytest.raises(ActividadAssetIncompleteError, match="free_amount_required"):
        operations.forecast(asset_id=asset.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)


# --- Maximum period and the registry floor --------------------------------------------------


def _published_year_operations(*, today: date) -> ActivityAssetOperations:
    """Resolve each year through the published authority's own edition selection, floor included."""

    def forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        with bundled_indexed_authority().operation() as operation:
            return forecast_activity_asset_charge(
                revision,
                modelo_100_revision=operation.revision_for_context("100", filing_year=covered_from.year, period="0A"),
                authority_generation=operation.pin().logical_generation,
                covered_from=covered_from,
                covered_until=covered_until,
                history=history,
                taxpayer_workforce=lambda: (),
                legal_reference=operation.legal_reference,
                requested_free_amount=requested_free_amount,
            )

    return ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_acquisition()),
        forecast_operation=forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.NORMAL,
        register_authority=memory_register_authority(today=today),
    )


def _ten_percent_furniture() -> ActivityAssetRevision:
    return _asset(
        _linear("mobiliario"),
        basis="10000",
        in_service=date(2005, 3, 15),
        opening="9000",
        opening_through=2024,
        asset_id="twenty-year-furniture",
    )


def test_ten_percent_with_twenty_years_stops_on_the_boundary_day_in_forecast_claim_and_plan() -> None:
    operations, _ = _operations()
    furniture = _ten_percent_furniture()
    operations.create(furniture, _DESCRIPTOR)

    # In service 15 March 2005 plus 20 years ends the period on 15 March 2025, its first day out.
    # 1 January to 14 March is 73 days: 10,000 x 10% x 73/365 = 200.00.
    last = operations.forecast(asset_id=furniture.asset_id, covered_from=_YEAR_START, covered_until=date(2025, 3, 15))
    assert (last.covered_until, last.service_days, last.amount) == (date(2025, 3, 15), 73, Decimal("200.00"))
    clipped = operations.forecast(asset_id=furniture.asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END)
    assert (clipped.covered_until, clipped.amount) == (date(2025, 3, 15), Decimal("200.00"))
    final_day = operations.forecast(
        asset_id=furniture.asset_id,
        covered_from=date(2025, 3, 14),
        covered_until=date(2025, 3, 15),
    )
    assert (final_day.service_days, final_day.amount) == (1, Decimal("2.74"))

    with pytest.raises(ActividadAssetPeriodElapsedError, match="amortization_period_elapsed") as refused:
        operations.forecast(asset_id=furniture.asset_id, covered_from=date(2025, 3, 15), covered_until=_YEAR_END)
    assert refused.value.context == {"ended_on": date(2025, 3, 14), "ended_before": date(2025, 3, 15)}

    past = last.model_copy(update={"covered_from": date(2025, 3, 15), "covered_until": date(2025, 3, 16)})
    with pytest.raises(ActividadAssetPeriodElapsedError, match="amortization_period_elapsed"):
        operations.record_claim(past, creating_operation="test.past-the-period")


def test_the_plan_shows_the_elapsed_year_as_elapsed_and_never_as_a_zero_amount() -> None:
    furniture = _ten_percent_furniture()
    operations = _published_year_operations(today=date(2025, 6, 30))
    operations.create(furniture, _DESCRIPTOR)

    rows = {row.tax_year: row for row in operations.plan(furniture.asset_id)}

    assert rows[2025].planned is not None
    assert rows[2025].planned.decimal == "200.00"
    assert rows[2025].service_days == 73
    assert rows[2026].absence is PlanFigureAbsence.PERIOD_ELAPSED
    assert rows[2026].planned is None
    assert rows[2026].absence_reason_key == "ledger.actividad_asset.errors.amortization_period_elapsed"
    assert rows[2026].claim_state is ActivityAssetClaimState.NOT_DUE
    assert rows[2024].absence is PlanFigureAbsence.COVERED_BY_OPENING

    limits = operations.plan_limits(furniture.asset_id)
    assert limits.class_key == "mobiliario"
    assert limits.not_table_bound is None
    assert limits.maximum_coefficient is not None
    assert Decimal(limits.maximum_coefficient.decimal) == Decimal("0.10")
    assert limits.minimum_coefficient is not None
    assert Decimal(limits.minimum_coefficient.decimal) == Decimal("0.05")
    assert limits.maximum_period_years is not None
    assert Decimal(limits.maximum_period_years.decimal) == Decimal("20")
    assert limits.maximum_period_ends_on == date(2025, 3, 15)
    assert limits.legal_citations_complete
    # The parameters the furniture election cites, in the order the authority cites them, each provision once.
    assert [citation.text for citation in limits.legal_citations] == [
        "Ley 35/2006, art.\u00a028",
        "Ley 27/2014, art.\u00a012",
        "Real Decreto 634/2015, art.\u00a05",
        "Real Decreto 634/2015, art.\u00a06",
        "Real Decreto 634/2015, art.\u00a07",
        "Ley 27/2014, DA\u00a018",
        "Ley 27/2014, art.\u00a0102",
        "Ley 27/2014, DA\u00a017",
        "Real Decreto 439/2007, art.\u00a022",
        "Ley 35/2006, art.\u00a029",
        "Real Decreto 439/2007, art.\u00a030",
    ]
    assert limits.legal_citations[0].permalink == "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28"
    assert limits.legal_citations[5].permalink == "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava"


def test_a_year_before_the_registry_floor_is_typed_and_never_a_guessed_figure() -> None:
    operations = _published_year_operations(today=date(2025, 12, 31))
    old = _asset(_linear("mobiliario"), basis="10000", in_service=date(2019, 7, 1), asset_id="pre-floor-chair")
    operations.create(old, _DESCRIPTOR)

    rows = {row.tax_year: row for row in operations.plan(old.asset_id)}

    for year in (2019, 2020, 2021):
        assert rows[year].absence is PlanFigureAbsence.EDITION_UNAVAILABLE
        assert rows[year].planned is None
        assert rows[year].claimable_intervals == ()
    # From the floor the table reads again, on the 1,000.00 a full year.
    assert rows[2022].planned is not None
    assert rows[2022].planned.decimal == "1000.00"


def test_an_authority_for_a_table_method_cannot_omit_the_end_of_its_period() -> None:
    with pytest.raises(ValueError, match="linear schedule authority requires maximum_period_ends_on"):
        ScheduleAuthority(
            tax_year=2025,
            asset_kind=AssetKind.MATERIAL,
            method=AmortizationMethod.LINEAR,
            election_fingerprint="a" * 64,
            authority_generation="floor-test",
            source_reference="floor-test",
            annual_rate=Decimal("0.10"),
        )
