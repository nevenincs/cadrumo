"""Activity asset schedule authority method and affectation resolution."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetClaimState
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations, SupersedingClaimRequest
from cadrumo.application.actividad_asset.schedule_walk import PlanFigureAbsence
from cadrumo.application.actividad_asset.tests.ledger_support import MemoryLedger
from cadrumo.application.actividad_asset.tests.register_support import MemoryRepository, memory_register_authority
from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.application.operator_actions.models import PreconditionVerdict
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    resolve_activity_asset_schedule_authority,
)
from cadrumo.domain.calculations.registry.actividad_asset_parameters import ACTIVITY_ASSET_PARAMETER_IDS
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim, effective_claims
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    ChargingInfrastructureEvidence,
    DirectEstimationRegime,
    LowValueElection,
    RenewableDocumentationKind,
    RenewableInstallationPurpose,
    RenewableSelfConsumptionEvidence,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetPeriodElapsedError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    ActivityAssetRevision,
    AssetKind,
)
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
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear

from .activity_asset_schedule_support import (
    DESCRIPTOR,
    TAX_YEAR,
    YEAR_END,
    YEAR_START,
    acquisition,
    activity_asset_schedule_asset,
    activity_asset_schedule_charge,
    activity_asset_schedule_constant,
    activity_asset_schedule_election,
    activity_asset_schedule_linear,
    activity_asset_schedule_refused,
    legal_reference,
    modelo_100,
    small_enterprise,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_indefinite_life_and_goodwill_are_limited_to_one_twentieth_in_both_modalities() -> None:
    indefinite = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_election(AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE),
            basis="20000",
            kind=AssetKind.INTANGIBLE,
        ),
    )
    goodwill = activity_asset_schedule_charge(
        activity_asset_schedule_asset(
            activity_asset_schedule_election(AmortizationMethod.GOODWILL, DirectEstimationRegime.SIMPLIFIED),
            basis="40000",
            kind=AssetKind.INTANGIBLE,
        ),
    )

    assert indefinite.amount == Decimal("1000.00")  # 20,000 / 20
    assert goodwill.amount == Decimal("2000.00")  # 40,000 / 20
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "method_not_enrolled_for_kind", asset_kind="material"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(activity_asset_schedule_election(AmortizationMethod.GOODWILL), basis="40000")
        )


def test_low_value_free_resolves_published_threshold_and_cap() -> None:
    authority = resolve_activity_asset_schedule_authority(
        modelo_100(),
        tax_year=TAX_YEAR,
        asset_revision=activity_asset_schedule_asset(
            activity_asset_schedule_election(
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
        legal_reference=legal_reference,
    )

    assert authority.free_depreciation_unit_threshold == Decimal("300")
    assert authority.free_depreciation_annual_cap == Decimal("25000")
    assert "libertad-amortizacion-umbral-unitario" in authority.source_reference


def test_research_development_free_and_building_methods() -> None:
    machine = activity_asset_schedule_asset(
        activity_asset_schedule_election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
            authority_class_key="maquinaria",
            research_development_evidence_reference="rnd-project-affectation",
        ),
        basis="10000",
    )
    building = activity_asset_schedule_asset(
        activity_asset_schedule_election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING,
            authority_class_key="edificio-industrial",
            research_development_evidence_reference="rnd-building-affectation",
        ),
        basis="100000",
    )

    assert activity_asset_schedule_charge(machine, free_amount="7000").amount == Decimal("7000.00")
    assert activity_asset_schedule_charge(building).amount == Decimal("10000.00")  # 100,000 / 10 years
    with pytest.raises(ActividadAssetValidationError, match="free_amount_exceeds_remaining_basis"):
        activity_asset_schedule_charge(machine, free_amount="10000.01")
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "research_development_free_excludes_buildings"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_election(
                    AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
                    authority_class_key="edificio-industrial",
                    research_development_evidence_reference="rnd",
                ),
                basis="100000",
            ),
            free_amount="1",
        )
    with activity_asset_schedule_refused(
        ActividadAssetValidationError, "research_development_building_requires_building_class"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_election(
                    AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING,
                    authority_class_key="maquinaria",
                    research_development_evidence_reference="rnd",
                ),
                basis="100000",
            ),
        )


def test_charging_infrastructure_free_depreciation_window() -> None:
    def charger(in_service: date, condition: AcquiredCondition = AcquiredCondition.NEW) -> ActivityAssetRevision:
        return activity_asset_schedule_asset(
            activity_asset_schedule_election(
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

    assert activity_asset_schedule_charge(charger(date(TAX_YEAR, 3, 1)), free_amount="2500").amount == Decimal(
        "2500.00"
    )
    assert activity_asset_schedule_charge(charger(date(TAX_YEAR - 1, 6, 1)), free_amount="1500").amount == Decimal(
        "1500.00"
    )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "charging_infrastructure_period_not_enrolled", rendered=re.escape("DA 18a.2")
    ):
        activity_asset_schedule_charge(charger(date(TAX_YEAR - 2, 6, 1)), free_amount="1500")
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "charging_infrastructure_new_only"):
        activity_asset_schedule_charge(charger(date(TAX_YEAR, 3, 1), AcquiredCondition.USED), free_amount="100")


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
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, key, rendered=provision):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(activity_asset_schedule_election(method), basis="1000")
        )


def activity_asset_schedule_authority_methods_vehicle(
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
    car = activity_asset_schedule_linear("transporte-externo")

    with activity_asset_schedule_refused(
        ActividadAssetIncompleteError,
        "vehicle_affectation_required_for_class",
        rendered="vehicle affectation declaration",
    ):
        activity_asset_schedule_charge(activity_asset_schedule_asset(car, basis="20000"))
    # External transport is 16%: 20,000 x 16% = 3,200.00 for a car used only for the activity.
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(car, basis="20000", vehicle=activity_asset_schedule_authority_methods_vehicle())
    ).amount == Decimal("3200.00")
    # A taxi keeps its accessory rest-day use under RIRPF art. 22.4 (b).
    taxi = activity_asset_schedule_authority_methods_vehicle(
        private_use=VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME, listed_use=VehicleListedUse.PAID_PASSENGER_TRANSPORT
    )
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(car, basis="20000", vehicle=taxi)
    ).amount == Decimal("3200.00")
    # A delivery van outside the restricted categories keeps the general accessory-use allowance.
    van = activity_asset_schedule_authority_methods_vehicle(
        VehicleCategory.OTHER_VEHICLE, VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME
    )
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(car, basis="20000", vehicle=van)
    ).amount == Decimal("3200.00")
    # A truck's table class cannot hold a restricted vehicle, so no declaration is needed: 20,000 x 20%.
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(activity_asset_schedule_linear("transporte-autocamion"), basis="20000")
    ).amount == Decimal("4000.00")


def test_a_vehicle_not_proven_affected_refuses_with_its_provision() -> None:
    car = activity_asset_schedule_linear("transporte-externo")
    refusals = (
        (
            activity_asset_schedule_authority_methods_vehicle(private_use=VehiclePrivateUse.SHARED),
            "vehicle_shared_use",
            "22.2.1",
        ),
        (
            activity_asset_schedule_authority_methods_vehicle(private_use=VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME),
            "vehicle_private_use_category_restricted",
            "22.4",
        ),
        (
            activity_asset_schedule_authority_methods_vehicle(
                VehicleCategory.MOTORCYCLE, VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME
            ),
            "vehicle_private_use_category_restricted",
            "22.4",
        ),
        (activity_asset_schedule_authority_methods_vehicle(in_books=False), "vehicle_missing_from_books", "22.2.2"),
    )
    for declaration, key, provision in refusals:
        with activity_asset_schedule_refused(ActividadAssetUnsupportedError, key, rendered=re.escape(provision)):
            activity_asset_schedule_charge(activity_asset_schedule_asset(car, basis="20000", vehicle=declaration))
    # Simplified modality: the transport group is flagged too.
    with activity_asset_schedule_refused(
        ActividadAssetIncompleteError,
        "vehicle_affectation_required_for_class",
        rendered="vehicle affectation declaration",
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_linear("transporte", DirectEstimationRegime.SIMPLIFIED), basis="20000"
            )
        )


def test_the_goods_transport_use_belongs_to_a_mixed_vehicle_only() -> None:
    with activity_asset_schedule_refused(
        ActividadAssetValidationError, "goods_transport_use_requires_mixed_vehicle", field="listed_use"
    ):
        activity_asset_schedule_authority_methods_vehicle(listed_use=VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT)
    assert (
        activity_asset_schedule_authority_methods_vehicle(
            VehicleCategory.MIXED_VEHICLE,
            VehiclePrivateUse.ACCESSORY_NON_WORKING_TIME,
            VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT,
        ).listed_use
        is VehicleListedUse.MIXED_VEHICLE_GOODS_TRANSPORT
    )


def test_electric_vehicle_free_depreciation_needs_an_affected_new_vehicle_in_the_window() -> None:
    election = activity_asset_schedule_election(
        AmortizationMethod.ELECTRIC_VEHICLE_FREE, authority_class_key="transporte-externo"
    )
    electric = activity_asset_schedule_authority_methods_vehicle(propulsion=ElectricPropulsion.BEV)

    charged = activity_asset_schedule_charge(
        activity_asset_schedule_asset(election, basis="30000", vehicle=electric), free_amount="30000"
    )

    assert charged.amount == Decimal("30000.00")
    with activity_asset_schedule_refused(ActividadAssetIncompleteError, "electric_vehicle_propulsion_required"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                election, basis="30000", vehicle=activity_asset_schedule_authority_methods_vehicle()
            ),
            free_amount="100",
        )
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "electric_vehicle_new_only"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(election, basis="30000", vehicle=electric, condition=AcquiredCondition.USED),
            free_amount="100",
        )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "electric_vehicle_period_not_enrolled", rendered=re.escape("DA 18a.1")
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                election, basis="30000", vehicle=electric, in_service=date(TAX_YEAR - 2, 6, 1)
            ),
            free_amount="100",
        )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "vehicle_shared_use", rendered=re.escape("22.2.1")
    ):
        shared = activity_asset_schedule_authority_methods_vehicle(
            private_use=VehiclePrivateUse.SHARED, propulsion=ElectricPropulsion.BEV
        )
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(election, basis="30000", vehicle=shared), free_amount="100"
        )


_OBSERVED = PlantillaMediaState.OBSERVED


_COMMITTED = PlantillaMediaState.COMMITTED


def workforce(*years: tuple[int, str, PlantillaMediaState]) -> tuple[PlantillaMediaYear, ...]:
    return tuple(
        PlantillaMediaYear(year=year, average_workforce=Decimal(average), state=state) for year, average, state in years
    )


# One year before the tax year; the tax year and the next after; the two following the further 24 months.
GROWING = workforce(
    (TAX_YEAR - 1, "10.00", _OBSERVED),
    (TAX_YEAR, "12.00", _OBSERVED),
    (TAX_YEAR + 1, "13.00", _COMMITTED),
    (TAX_YEAR + 2, "13.00", _COMMITTED),
    (TAX_YEAR + 3, "13.00", _COMMITTED),
)


def employment() -> ActivityAssetAmortizationElection:
    return activity_asset_schedule_election(
        AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE,
        authority_class_key="maquinaria",
        small_enterprise=small_enterprise("5000000", made_available=date(TAX_YEAR, 2, 15)),
    )


def test_job_creating_free_depreciation_caps_the_investment_by_the_workforce_increase() -> None:
    machine = activity_asset_schedule_asset(employment(), basis="200000", in_service=date(TAX_YEAR, 3, 1))
    authority = resolve_activity_asset_schedule_authority(
        modelo_100(),
        tax_year=TAX_YEAR,
        asset_revision=machine,
        authority_generation="candidate-source",
        workforce=GROWING,
        legal_reference=legal_reference,
    )

    # 24 months after 1 January of the tax year: (12 x 365 + 13 x 365) / 730 = 12.50 against 10.00 before, an
    # increase of 2.50; LIS art. 102.1 lets 120,000 x 2.50 = 300,000.00 of investment benefit.
    assert authority.free_depreciation_investment_cap == Decimal("300000.00")
    assert "erd-empleo-inversion-por-unidad-plantilla" in authority.source_reference
    assert f"taxpayer-profile:irpf.plantilla_media:{TAX_YEAR - 1}:observed" in authority.source_reference
    assert f"taxpayer-profile:irpf.plantilla_media:{TAX_YEAR + 3}:committed" in authority.source_reference
    assert activity_asset_schedule_charge(machine, free_amount="150000", workforce=GROWING).amount == Decimal(
        "150000.00"
    )
    # The whole 300,000.00 fits the cap exactly; one cent more does not.
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(employment(), basis="300000", in_service=date(TAX_YEAR, 3, 1)),
        free_amount="300000",
        workforce=GROWING,
    ).amount == Decimal("300000.00")
    with pytest.raises(ActividadAssetUnsupportedError, match="investment_cap_exceeded"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(employment(), basis="300000.01", in_service=date(TAX_YEAR, 3, 1)),
            free_amount="1",
            workforce=GROWING,
        )


def test_job_creating_free_depreciation_refuses_each_unmet_condition() -> None:
    machine = activity_asset_schedule_asset(employment(), basis="200000", in_service=date(TAX_YEAR, 3, 1))

    with activity_asset_schedule_refused(
        ActividadAssetIncompleteError, "workforce_year_not_declared", year=TAX_YEAR + 2
    ):
        activity_asset_schedule_charge(
            machine, free_amount="1", workforce=tuple(item for item in GROWING if item.year != TAX_YEAR + 2)
        )
    with activity_asset_schedule_refused(
        ActividadAssetIncompleteError, "workforce_year_not_declared", year=TAX_YEAR - 1
    ):
        activity_asset_schedule_charge(machine, free_amount="1")
    flat = workforce(*((year, "10.00", _OBSERVED) for year in range(TAX_YEAR - 1, TAX_YEAR + 4)))
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "workforce_increase_not_reached"):
        activity_asset_schedule_charge(machine, free_amount="1", workforce=flat)
    lost = workforce(
        (TAX_YEAR - 1, "10.00", _OBSERVED),
        (TAX_YEAR, "12.00", _OBSERVED),
        (TAX_YEAR + 1, "13.00", _COMMITTED),
        (TAX_YEAR + 2, "11.00", _COMMITTED),
        (TAX_YEAR + 3, "11.00", _COMMITTED),
    )
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "workforce_increase_not_kept"):
        activity_asset_schedule_charge(machine, free_amount="1", workforce=lost)
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "job_creation_new_only"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                employment(), basis="200000", in_service=date(TAX_YEAR, 3, 1), condition=AcquiredCondition.USED
            ),
            free_amount="1",
            workforce=GROWING,
        )
    large = activity_asset_schedule_election(
        AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE,
        authority_class_key="maquinaria",
        small_enterprise=small_enterprise("12000000", made_available=date(TAX_YEAR, 2, 15)),
    )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "reduced_size_turnover_reached", rendered=re.escape("LIS art. 101.1")
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(large, basis="200000", in_service=date(TAX_YEAR, 3, 1)),
            free_amount="1",
            workforce=GROWING,
        )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "method_excluded_by_law", asset_kind="intangible"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_election(
                    AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE,
                    authority_class_key="equipo-proceso-informacion",
                    small_enterprise=small_enterprise("5000000", made_available=date(TAX_YEAR, 2, 15)),
                ),
                basis="2000.00",
                kind=AssetKind.INTANGIBLE,
                in_service=date(TAX_YEAR, 3, 1),
            ),
            free_amount="1",
            workforce=GROWING,
        )
    with activity_asset_schedule_refused(
        ActividadAssetValidationError,
        "election_requires_fact",
        method=AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE.value,
        field="small_enterprise",
    ):
        activity_asset_schedule_election(
            AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE, authority_class_key="maquinaria"
        )


def test_assets_entering_service_together_share_one_investment_cap() -> None:
    operations, _ = _operations(GROWING)

    def forecast(asset_id: str) -> ScheduledAmortizationCharge:
        return operations.forecast(
            asset_id=asset_id,
            covered_from=YEAR_START,
            covered_until=YEAR_END,
            requested_free_amount=Decimal("1000"),
        )

    operations.create(
        activity_asset_schedule_asset(
            employment(), basis="200000", in_service=date(TAX_YEAR, 3, 1), asset_id="first-machine"
        ),
        DESCRIPTOR,
    )
    # A linear asset of the same year and an asset of the year before under the incentive draw on no cap.
    operations.create(
        activity_asset_schedule_asset(
            activity_asset_schedule_linear("maquinaria"),
            basis="500000",
            in_service=date(TAX_YEAR, 3, 1),
            asset_id="plain",
        ),
        DESCRIPTOR,
    )
    operations.create(
        activity_asset_schedule_asset(
            employment(), basis="250000", in_service=date(TAX_YEAR - 1, 3, 1), asset_id="earlier-year"
        ),
        DESCRIPTOR,
    )

    assert forecast("first-machine").amount == Decimal("1000.00")

    # 200,000 + 150,000 = 350,000 of the tax year's investment exceeds the 300,000.00 cap, so neither asset
    # is charged freely: the product does not choose which part of which asset benefits.
    operations.create(
        activity_asset_schedule_asset(
            employment(), basis="150000", in_service=date(TAX_YEAR, 6, 1), asset_id="second-machine"
        ),
        DESCRIPTOR,
    )
    for asset_id in ("first-machine", "second-machine"):
        with pytest.raises(ActividadAssetUnsupportedError, match="investment_cap_exceeded"):
            forecast(asset_id)


def renewable_evidence(
    purpose: RenewableInstallationPurpose = RenewableInstallationPurpose.ELECTRICITY_SELF_CONSUMPTION,
    documentation: RenewableDocumentationKind = RenewableDocumentationKind.LOW_VOLTAGE_CERTIFICATE,
    *,
    made_available: date = date(TAX_YEAR, 1, 10),
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


def renewable(
    evidence: RenewableSelfConsumptionEvidence | None = None,
    class_key: str = "instalacion-resto",
) -> ActivityAssetAmortizationElection:
    return activity_asset_schedule_election(
        AmortizationMethod.RENEWABLE_SELF_CONSUMPTION_FREE,
        authority_class_key=class_key,
        renewable_self_consumption=evidence or renewable_evidence(),
    )


# One year before the tax year; the tax year and the next after; DA 17a.1 asks only that the average is kept.
_KEPT = workforce(
    (TAX_YEAR - 1, "10.00", _OBSERVED), (TAX_YEAR, "10.00", _OBSERVED), (TAX_YEAR + 1, "10.00", _COMMITTED)
)


def test_renewable_free_depreciation_charges_an_installation_of_the_tax_year_up_to_the_investment_cap() -> None:
    panels = activity_asset_schedule_asset(renewable(), basis="40000", in_service=date(TAX_YEAR, 2, 1))
    authority = resolve_activity_asset_schedule_authority(
        modelo_100(),
        tax_year=TAX_YEAR,
        asset_revision=panels,
        authority_generation="candidate-source",
        workforce=_KEPT,
        legal_reference=legal_reference,
    )

    assert authority.free_depreciation_investment_cap == Decimal("500000")
    assert "renewable-documentation:low_voltage_certificate:cie-2025-0042" in authority.source_reference
    assert f"taxpayer-profile:irpf.plantilla_media:{TAX_YEAR + 1}:committed" in authority.source_reference
    assert activity_asset_schedule_charge(panels, free_amount="40000", workforce=_KEPT).amount == Decimal("40000.00")
    heat = renewable(
        renewable_evidence(
            RenewableInstallationPurpose.THERMAL_OWN_USE,
            RenewableDocumentationKind.ENERGY_EFFICIENCY_CERTIFICATE,
            replaces_fossil=True,
        ),
    )
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(heat, basis="9000", in_service=date(TAX_YEAR, 5, 1)),
        free_amount="9000",
        workforce=_KEPT,
    ).amount == (Decimal("9000.00"))
    # The installation made available on the day RDL 18/2022 entered into force qualifies.
    first_day = renewable(renewable_evidence(made_available=date(TAX_YEAR - 3, 10, 20)))
    assert activity_asset_schedule_charge(
        activity_asset_schedule_asset(first_day, basis="1000", in_service=date(TAX_YEAR, 2, 1)),
        free_amount="1000",
        workforce=_KEPT,
    ).amount == (Decimal("1000.00"))
    with pytest.raises(ActividadAssetUnsupportedError, match="investment_cap_exceeded"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(renewable(), basis="500000.01", in_service=date(TAX_YEAR, 2, 1)),
            free_amount="1",
            workforce=_KEPT,
        )


def test_renewable_free_depreciation_refuses_each_unmet_condition() -> None:
    def refused(
        election: ActivityAssetAmortizationElection,
        key: str,
        *,
        in_service: date = date(TAX_YEAR, 2, 1),
        rendered: str | None = None,
    ) -> None:
        with activity_asset_schedule_refused(ActividadAssetUnsupportedError, key, rendered=rendered):
            activity_asset_schedule_charge(
                activity_asset_schedule_asset(election, basis="40000", in_service=in_service),
                free_amount="1",
                workforce=_KEPT,
            )

    refused(renewable(class_key="edificio-industrial"), "renewable_excludes_buildings")
    refused(
        renewable(
            renewable_evidence(
                RenewableInstallationPurpose.THERMAL_OWN_USE,
                RenewableDocumentationKind.THERMAL_PROCESS_REGISTRATION,
            ),
        ),
        "renewable_thermal_requires_fossil_replacement",
        rendered="fossil energy",
    )
    refused(
        renewable(renewable_evidence(building_code=True)),
        "renewable_mandatory_installation_unsupported",
        rendered=re.escape("DA 17a.5"),
    )
    refused(
        renewable(renewable_evidence(made_available=date(TAX_YEAR - 3, 10, 19))),
        "renewable_made_available_before_admitted_date",
    )
    refused(
        renewable(renewable_evidence(made_available=date(TAX_YEAR - 1, 1, 10))),
        "renewable_entry_year_not_enrolled",
        in_service=date(TAX_YEAR - 1, 6, 1),
    )
    shrinking = workforce(
        (TAX_YEAR - 1, "10.00", _OBSERVED), (TAX_YEAR, "9.00", _OBSERVED), (TAX_YEAR + 1, "9.50", _COMMITTED)
    )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "workforce_fell_below", rendered=re.escape("LIS DA 17a.1")
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(renewable(), basis="40000", in_service=date(TAX_YEAR, 2, 1)),
            free_amount="1",
            workforce=shrinking,
        )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "method_excluded_by_law", asset_kind="intangible"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                renewable(class_key="equipo-proceso-informacion"),
                basis="2000.00",
                kind=AssetKind.INTANGIBLE,
                in_service=date(TAX_YEAR, 2, 1),
            ),
            free_amount="1",
            workforce=_KEPT,
        )
    with activity_asset_schedule_refused(
        ActividadAssetValidationError,
        "renewable_documentation_mismatch",
        field="documentation_kind",
        purpose=RenewableInstallationPurpose.ELECTRICITY_SELF_CONSUMPTION.value,
    ):
        renewable_evidence(documentation=RenewableDocumentationKind.ENERGY_EFFICIENCY_CERTIFICATE)


def test_renewable_free_depreciation_is_taken_only_in_the_entry_year() -> None:
    """A window reaching an earlier entry year still refuses a later period's free charge."""
    revision = modelo_100()
    widened = revision.model_copy(
        update={
            "parameters": tuple(
                parameter.model_copy(
                    update={
                        "values": tuple(
                            value.model_copy(update={"value": Decimal(TAX_YEAR - 1)}) for value in parameter.values
                        )
                    },
                )
                if parameter.id == "renta-actividad-inmovilizado-amortizacion-renovables-primer-ejercicio"
                else parameter
                for parameter in revision.parameters
            ),
        },
    )
    installed_year_before = activity_asset_schedule_asset(
        renewable(renewable_evidence(made_available=date(TAX_YEAR - 1, 1, 10))),
        basis="40000",
        in_service=date(TAX_YEAR - 1, 6, 1),
    )

    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "renewable_only_in_entry_period"):
        resolve_activity_asset_schedule_authority(
            widened,
            tax_year=TAX_YEAR,
            asset_revision=installed_year_before,
            authority_generation="candidate-source",
            workforce=workforce(
                (TAX_YEAR - 2, "10.00", _OBSERVED), (TAX_YEAR - 1, "10.00", _OBSERVED), (TAX_YEAR, "10.00", _OBSERVED)
            ),
            legal_reference=legal_reference,
        )


def test_methods_the_workforce_does_not_condition_never_read_it() -> None:
    def unreadable() -> tuple[PlantillaMediaYear, ...]:
        raise AssertionError("the average workforce was read for a method it does not condition")

    charge = forecast_activity_asset_charge(
        activity_asset_schedule_asset(activity_asset_schedule_linear("maquinaria"), basis="10000"),
        modelo_100_revision=modelo_100(),
        authority_generation="candidate-source",
        covered_from=YEAR_START,
        covered_until=YEAR_END,
        history=AssetScheduleHistory(),
        taxpayer_workforce=unreadable,
        legal_reference=legal_reference,
    )

    assert charge.amount == Decimal("1200.00")  # machinery 12% of 10,000


def test_unknown_class_and_kind_mismatch_fail_closed() -> None:
    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "table_class_without_group_classification"):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(activity_asset_schedule_linear("caller-invented-class"), basis="1000")
        )
    with activity_asset_schedule_refused(
        ActividadAssetUnsupportedError, "table_class_wrong_kind", asset_kind="intangible"
    ):
        activity_asset_schedule_charge(
            activity_asset_schedule_asset(
                activity_asset_schedule_linear("mobiliario"), basis="1000", kind=AssetKind.INTANGIBLE
            )
        )


def test_the_declared_read_set_names_only_parameters_the_revision_declares() -> None:
    """The orphan check trusts this set, so a stale id in it would hide nothing but mislead."""
    declared = {parameter.id for parameter in modelo_100().parameters}

    assert declared >= ACTIVITY_ASSET_PARAMETER_IDS, sorted(ACTIVITY_ASSET_PARAMETER_IDS - declared)


def test_an_absent_admission_parameter_fails_closed() -> None:
    revision = modelo_100()
    stripped = revision.model_copy(
        update={
            "parameters": tuple(
                parameter
                for parameter in revision.parameters
                if parameter.id != "renta-actividad-inmovilizado-amortizacion-normal-metodo-admitido"
            ),
        },
    )

    with activity_asset_schedule_refused(ActividadAssetUnsupportedError, "parameter_absent"):
        resolve_activity_asset_schedule_authority(
            stripped,
            tax_year=TAX_YEAR,
            asset_revision=activity_asset_schedule_asset(activity_asset_schedule_linear("mobiliario"), basis="1000"),
            authority_generation="candidate-source",
            workforce=(),
            legal_reference=legal_reference,
        )


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
            modelo_100_revision=modelo_100(),
            authority_generation="published-registry-test-generation",
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=lambda: workforce,
            legal_reference=legal_reference,
            requested_free_amount=requested_free_amount,
        )

    repository = MemoryRepository()
    return (
        ActivityAssetOperations(
            repository=repository,
            ledger=MemoryLedger(acquisition()),
            forecast_operation=forecast,
            taxpayer_modality=lambda: DirectEstimationRegime.NORMAL,
            register_authority=memory_register_authority(),
        ),
        repository,
    )


def test_a_change_of_method_inside_a_claimed_tax_year_refuses() -> None:
    operations, _ = _operations()
    linear = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"), basis="10000", asset_id="switching-machine"
    )
    operations.create(linear, DESCRIPTOR)
    first_quarter = operations.forecast(
        asset_id=linear.asset_id,
        covered_from=YEAR_START,
        covered_until=date(TAX_YEAR, 4, 1),
    )
    operations.record_claim(first_quarter, creating_operation="test.linear-q1")
    switched = linear.model_copy(
        update={
            "revision_number": 2,
            "supersedes_revision_id": linear.revision_id,
            "amortization": activity_asset_schedule_constant("maquinaria"),
        },
    )
    operations.correct(switched)

    assert first_quarter.amount == Decimal("295.89")  # 10,000 x 12% x 90/365 = 295.8904
    with pytest.raises(ActividadAssetValidationError, match="election_changes_only_at_year_boundary"):
        operations.forecast(
            asset_id=linear.asset_id, covered_from=date(TAX_YEAR, 4, 1), covered_until=date(TAX_YEAR, 7, 1)
        )


def test_constant_percentage_and_sum_of_digits_cannot_be_adopted_after_another_method() -> None:
    constant = activity_asset_schedule_asset(
        activity_asset_schedule_constant("maquinaria"),
        basis="10000",
        in_service=date(TAX_YEAR - 1, 1, 1),
        opening="1200",
        opening_method=AmortizationMethod.CONSTANT_PERCENTAGE,
    )
    earlier_linear = AssetScheduleHistory(
        election_fingerprints_before_tax_year=(activity_asset_schedule_linear("maquinaria").fingerprint,)
    )
    earlier_same = AssetScheduleHistory(election_fingerprints_before_tax_year=(constant.amortization.fingerprint,))

    with pytest.raises(ActividadAssetUnsupportedError, match="from_start_method_after_other_election"):
        activity_asset_schedule_charge(constant, history=earlier_linear)
    assert activity_asset_schedule_charge(constant, history=earlier_same).amount == Decimal(
        "2640.00"
    )  # (10,000 - 1,200) x 30%
    # A move to linear from a tax-year boundary is admitted and runs on the remaining basis.
    linear = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"), basis="10000", in_service=date(TAX_YEAR - 1, 1, 1), opening="3000"
    )
    after_constant = AssetScheduleHistory(election_fingerprints_before_tax_year=(constant.amortization.fingerprint,))
    assert activity_asset_schedule_charge(linear, history=after_constant).amount == Decimal("1200.00")  # 10,000 x 12%


def test_an_undeclared_vehicle_refuses_with_its_correction_action_until_corrected() -> None:
    operations, _ = _operations()
    car = activity_asset_schedule_asset(
        activity_asset_schedule_linear("transporte-externo"), basis="20000", asset_id="undeclared-car"
    )
    operations.create(car, DESCRIPTOR)

    with pytest.raises(ActividadAssetIncompleteError) as refused:
        operations.forecast(asset_id=car.asset_id, covered_from=YEAR_START, covered_until=YEAR_END)

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
        update={
            "revision_number": 2,
            "supersedes_revision_id": car.revision_id,
            "vehicle_affectation": activity_asset_schedule_authority_methods_vehicle(),
        },
    )
    operations.correct(corrected)
    # The corrected car is used only for the activity: 20,000 x 16% = 3,200.00.
    forecast = operations.forecast(asset_id=car.asset_id, covered_from=YEAR_START, covered_until=YEAR_END)
    assert forecast.amount == Decimal("3200.00")


def test_a_superseding_claim_is_forecast_without_the_claim_it_replaces() -> None:
    operations, repository = _operations()
    machine = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"),
        basis="1000",
        in_service=date(TAX_YEAR - 8, 1, 1),
        opening="950",
        asset_id="nearly-amortized-machine",
    )
    operations.create(machine, DESCRIPTOR)
    first = operations.forecast(asset_id=machine.asset_id, covered_from=YEAR_START, covered_until=date(TAX_YEAR, 4, 1))
    operations.record_claim(first, creating_operation="test.q1")
    second = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=date(TAX_YEAR, 4, 1),
        covered_until=date(TAX_YEAR, 7, 1),
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
    machine = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"), basis="1000", asset_id="no-claims-machine"
    )
    operations.create(machine, DESCRIPTOR)

    with pytest.raises(ActividadAssetValidationError, match="superseded_claim_not_effective"):
        operations.forecast(
            asset_id=machine.asset_id,
            covered_from=YEAR_START,
            covered_until=YEAR_END,
            supersedes_claim_id="c" * 64,
        )


def test_the_history_write_refuses_a_claim_under_a_superseded_revision() -> None:
    machine = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"), basis="1000", asset_id="corrected-before-write"
    )
    corrected = machine.model_copy(
        update={"revision_number": 2, "supersedes_revision_id": machine.revision_id, "residual_value": Decimal("10")},
    )
    history = ActivityAssetHistory(revisions=(machine, corrected))
    stale = AmortizationClaim.from_schedule(
        activity_asset_schedule_charge(machine, covered_until=date(TAX_YEAR, 7, 1)),
        asset_kind=machine.asset_kind,
        creating_operation="test.stale-revision",
    )

    with pytest.raises(ActividadAssetClaimConflictError, match="claim_not_under_current_revision"):
        history.record_claim(stale)


def test_two_forecasts_taken_before_recording_cannot_both_consume_the_basis() -> None:
    operations, repository = _operations()
    machine = activity_asset_schedule_asset(
        activity_asset_schedule_election(
            AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
            authority_class_key="maquinaria",
            research_development_evidence_reference="rnd-project-affectation",
        ),
        basis="10000",
        asset_id="rnd-machine",
    )
    operations.create(machine, DESCRIPTOR)
    first_half = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=YEAR_START,
        covered_until=date(TAX_YEAR, 7, 1),
        requested_free_amount=Decimal("10000"),
    )
    second_half = operations.forecast(
        asset_id=machine.asset_id,
        covered_from=date(TAX_YEAR, 7, 1),
        covered_until=YEAR_END,
        requested_free_amount=Decimal("10000"),
    )

    operations.record_claim(first_half, creating_operation="test.rnd-first-half")
    with pytest.raises(ActividadAssetValidationError, match="free_amount_exceeds_remaining_basis"):
        operations.record_claim(second_half, creating_operation="test.rnd-second-half")
    assert sum((claim.amount for claim in repository.history.claims), Decimal("0")) == Decimal("10000")


def test_a_hand_edited_forecast_is_refused_at_record_time() -> None:
    operations, _ = _operations()
    machine = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"), basis="10000", asset_id="edited-machine"
    )
    operations.create(machine, DESCRIPTOR)
    forecast = operations.forecast(asset_id=machine.asset_id, covered_from=YEAR_START, covered_until=YEAR_END)
    inflated = forecast.model_copy(update={"amount": Decimal("5000.00")})

    with pytest.raises(ActividadAssetValidationError, match="forecast_no_longer_matches"):
        operations.record_claim(inflated, creating_operation="test.inflated")


def test_the_history_write_refuses_a_claim_beyond_the_basis_even_without_operations() -> None:
    machine = activity_asset_schedule_asset(
        activity_asset_schedule_linear("maquinaria"), basis="1000", asset_id="direct-write-machine"
    )
    first_half = activity_asset_schedule_charge(machine, covered_until=date(TAX_YEAR, 7, 1))
    second_half = activity_asset_schedule_charge(machine, covered_from=date(TAX_YEAR, 7, 1))
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
    asset = activity_asset_schedule_asset(
        activity_asset_schedule_election(
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
    operations.create(asset, DESCRIPTOR)
    forecast = operations.forecast(
        asset_id=asset.asset_id,
        covered_from=YEAR_START,
        covered_until=YEAR_END,
        requested_free_amount=Decimal("300.00"),
    )
    first = operations.record_claim(forecast, creating_operation="test.real-authority-free-depreciation")
    retry = operations.record_claim(forecast, creating_operation="test.real-authority-free-depreciation")

    assert forecast.amount == Decimal("300.00")
    assert first.claim.method is AmortizationMethod.LOW_VALUE_FREE
    assert retry.reused_existing_claim is True
    with pytest.raises(ActividadAssetIncompleteError, match="free_amount_required"):
        operations.forecast(asset_id=asset.asset_id, covered_from=YEAR_START, covered_until=YEAR_END)


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
        ledger=MemoryLedger(acquisition()),
        forecast_operation=forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.NORMAL,
        register_authority=memory_register_authority(today=today),
    )


def _ten_percent_furniture() -> ActivityAssetRevision:
    return activity_asset_schedule_asset(
        activity_asset_schedule_linear("mobiliario"),
        basis="10000",
        in_service=date(TAX_YEAR - 20, 3, 15),
        opening="9000",
        opening_through=TAX_YEAR - 1,
        asset_id="twenty-year-furniture",
    )


def test_ten_percent_with_twenty_years_stops_on_the_boundary_day_in_forecast_claim_and_plan() -> None:
    operations, _ = _operations()
    furniture = _ten_percent_furniture()
    operations.create(furniture, DESCRIPTOR)

    # In service 15 March twenty years earlier ends the period on 15 March of the tax year, its first day out.
    # 1 January to 14 March is 73 days: 10,000 x 10% x 73/365 = 200.00.
    last = operations.forecast(
        asset_id=furniture.asset_id, covered_from=YEAR_START, covered_until=date(TAX_YEAR, 3, 15)
    )
    assert (last.covered_until, last.service_days, last.amount) == (date(TAX_YEAR, 3, 15), 73, Decimal("200.00"))
    clipped = operations.forecast(asset_id=furniture.asset_id, covered_from=YEAR_START, covered_until=YEAR_END)
    assert (clipped.covered_until, clipped.amount) == (date(TAX_YEAR, 3, 15), Decimal("200.00"))
    final_day = operations.forecast(
        asset_id=furniture.asset_id,
        covered_from=date(TAX_YEAR, 3, 14),
        covered_until=date(TAX_YEAR, 3, 15),
    )
    assert (final_day.service_days, final_day.amount) == (1, Decimal("2.74"))

    with pytest.raises(ActividadAssetPeriodElapsedError, match="amortization_period_elapsed") as refused:
        operations.forecast(asset_id=furniture.asset_id, covered_from=date(TAX_YEAR, 3, 15), covered_until=YEAR_END)
    assert refused.value.context == {"ended_on": date(TAX_YEAR, 3, 14), "ended_before": date(TAX_YEAR, 3, 15)}

    past = last.model_copy(update={"covered_from": date(TAX_YEAR, 3, 15), "covered_until": date(TAX_YEAR, 3, 16)})
    with pytest.raises(ActividadAssetPeriodElapsedError, match="amortization_period_elapsed"):
        operations.record_claim(past, creating_operation="test.past-the-period")


def test_the_plan_shows_the_elapsed_year_as_elapsed_and_never_as_a_zero_amount() -> None:
    furniture = _ten_percent_furniture()
    operations = _published_year_operations(today=date(TAX_YEAR, 6, 30))
    operations.create(furniture, DESCRIPTOR)

    rows = {row.tax_year: row for row in operations.plan(furniture.asset_id)}

    planned = rows[TAX_YEAR].planned
    assert planned is not None
    assert planned.decimal == "200.00"
    assert rows[TAX_YEAR].service_days == 73
    assert rows[TAX_YEAR + 1].absence is PlanFigureAbsence.PERIOD_ELAPSED
    assert rows[TAX_YEAR + 1].planned is None
    assert rows[TAX_YEAR + 1].absence_reason_key == "ledger.actividad_asset.errors.amortization_period_elapsed"
    assert rows[TAX_YEAR + 1].claim_state is ActivityAssetClaimState.NOT_DUE
    assert rows[TAX_YEAR - 1].absence is PlanFigureAbsence.COVERED_BY_OPENING

    limits = operations.plan_limits(furniture.asset_id)
    assert limits.class_key == "mobiliario"
    assert limits.not_table_bound is None
    assert limits.maximum_coefficient is not None
    assert Decimal(limits.maximum_coefficient.decimal) == Decimal("0.10")
    assert limits.minimum_coefficient is not None
    assert Decimal(limits.minimum_coefficient.decimal) == Decimal("0.05")
    assert limits.maximum_period_years is not None
    assert Decimal(limits.maximum_period_years.decimal) == Decimal("20")
    assert limits.maximum_period_ends_on == date(TAX_YEAR, 3, 15)
    assert limits.legal_citations_complete
    # Entering service before the floor, the election is read under the floor edition.  Its admitted
    # methods predate LIS DA 17 (renewables, added by RDL 18/2022 art. 22 for installations entering
    # service from 2023) and DA 18 (vehicles and charging, RDL 4/2024 art. 4), so neither is cited.
    assert [citation.text for citation in limits.legal_citations] == [
        "Ley 35/2006, art.\u00a028",
        "Ley 27/2014, art.\u00a012",
        "Real Decreto 634/2015, art.\u00a05",
        "Real Decreto 634/2015, art.\u00a06",
        "Real Decreto 634/2015, art.\u00a07",
        "Ley 27/2014, art.\u00a0102",
        "Real Decreto 439/2007, art.\u00a022",
        "Ley 35/2006, art.\u00a029",
        "Real Decreto 439/2007, art.\u00a030",
    ]
    assert limits.legal_citations[0].permalink == "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a28"

    new_furniture = activity_asset_schedule_asset(
        activity_asset_schedule_linear("mobiliario"),
        basis="10000",
        in_service=YEAR_START,
        asset_id="new-furniture",
    )
    new_operations = _published_year_operations(today=date(TAX_YEAR, 6, 30))
    new_operations.create(new_furniture, DESCRIPTOR)
    new_limits = new_operations.plan_limits(new_furniture.asset_id)
    assert new_limits.legal_citations_complete
    # The parameters a furniture election of the tax year cites, in the order the authority cites them, each
    # provision once.
    assert [citation.text for citation in new_limits.legal_citations] == [
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
    assert (
        new_limits.legal_citations[5].permalink == "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328#dadecimoctava"
    )


def test_a_year_before_the_registry_floor_is_typed_and_never_a_guessed_figure() -> None:
    floor = filing_year_envelope().floor
    operations = _published_year_operations(today=date(TAX_YEAR, 12, 31))
    old = activity_asset_schedule_asset(
        activity_asset_schedule_linear("mobiliario"),
        basis="10000",
        in_service=date(floor - 3, 7, 1),
        asset_id="pre-floor-chair",
    )
    operations.create(old, DESCRIPTOR)

    rows = {row.tax_year: row for row in operations.plan(old.asset_id)}

    for year in range(floor - 3, floor):
        assert rows[year].absence is PlanFigureAbsence.EDITION_UNAVAILABLE
        assert rows[year].planned is None
        assert rows[year].claimable_intervals == ()
    # From the floor the table reads again, on the 1,000.00 a full year.
    planned_at_floor = rows[floor].planned
    assert planned_at_floor is not None
    assert planned_at_floor.decimal == "1000.00"


def test_an_authority_for_a_table_method_cannot_omit_the_end_of_its_period() -> None:
    with pytest.raises(ValueError, match="linear schedule authority requires maximum_period_ends_on"):
        ScheduleAuthority(
            tax_year=TAX_YEAR,
            asset_kind=AssetKind.MATERIAL,
            method=AmortizationMethod.LINEAR,
            election_fingerprint="a" * 64,
            authority_generation="floor-test",
            source_reference="floor-test",
            annual_rate=Decimal("0.10"),
        )
