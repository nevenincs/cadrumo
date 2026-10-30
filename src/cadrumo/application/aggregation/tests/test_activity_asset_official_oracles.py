"""End-to-end proof of the activity-asset amortization against independent worked examples.

Every element is created, forecast and claimed through ``ActivityAssetOperations``, the use-case
boundary the registered operations call, over the published 2025 authority.  Modelo 100 casillas
0208 and 0227 and Modelo 130 casilla 02 are then read through the real source-mesh resolvers.

Figures come from two kinds of oracle, never from a run of the code under test:

* the AEAT "Manual practico de Renta 2025" worked examples, read from the bundled corpus; and
* hand-worked cases whose arithmetic is shown beside each assertion.

Dates are half-open: a charge covers ``covered_from`` up to, not including, ``covered_until``.
The day count is service days over the 365 days of 2025.

Out of scope for this backend, and therefore not asserted as figures:

* the manual's estimacion objetiva examples (a 6.050,00 incentive for investment and an agrarian
  11.185,00): the election has only the normal and simplified direct-estimation regimes, and the
  modulos amortization table and its free-depreciation limits are not enrolled.  Only the rule
  they share with direct estimation, that a charge never exceeds the value still pending, is
  proved with their figures;
* the leasing limit of 3.840,00: an unexercised financial lease is refused, and the tripled
  coefficient of the leasing rule is not a method;
* the property-affectation valuation example, which rebuilds amortization by year from 1985 under
  percentages that changed over time: the register takes the pre-onboarding amount as attested
  opening history and does not reconstruct it;
* the reduced-size determination of the manual's four turnover examples beyond the threshold:
  the register is handed the prior-period turnover and neither annualizes it nor looks back three
  years;
* capital inmobiliario and usufruct examples, which are not activity assets.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....core.tipos_actividad import TipoActividad
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category_catalogue import amortizable_spending_categories
from ....domain.renta.actividad_asset.claims import effective_claims
from ....domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from ....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    SmallEnterpriseEvidence,
)
from ....domain.renta.actividad_asset.errors import ActividadAssetUnsupportedError, ActividadAssetValidationError
from ....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
    OwnershipMode,
)
from ....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ....domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ....domain.transactions.models import Transaction
from ...actividad_asset.disposal_calculation import pinned_disposal_bounds
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.operations import ActivityAssetOperations
from ...actividad_asset.tests.ledger_support import MemoryLedger
from ...actividad_asset.tests.register_support import MemoryRepository, memory_register_authority
from ...calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ...modelo.calculation_notes import GATE_REFUSED_REASONS
from ..source_mesh import CalculationSourceResolution
from .test_modelo_source_mesh_ledger import (
    _m130_binding_id,
    _machine_acquisition_transaction,
    _reasons,
    _renta_expense_binding_id,
    _revision,
    resolve_m100,
    resolve_m130,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_NORMAL = DirectEstimationRegime.NORMAL
_SIMPLIFIED = DirectEstimationRegime.SIMPLIFIED
_YEAR_START = date(2025, 1, 1)
_YEAR_END = date(2026, 1, 1)
_QUARTER_STARTS = (_YEAR_START, date(2025, 4, 1), date(2025, 7, 1), date(2025, 10, 1))
_QUARTER_ENDS = (date(2025, 4, 1), date(2025, 7, 1), date(2025, 10, 1), _YEAR_END)
_QUARTERS = ("1T", "2T", "3T", "4T")
_DESCRIPTOR = ActivityAssetDescriptorFacts(name="Oracle element")
_ZERO = Decimal("0")


# --- Fixtures ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Register:
    """One bucket's register over the published authority, with the ledger rows it acquires from."""

    operations: ActivityAssetOperations
    repository: MemoryRepository
    rows: tuple[Transaction, ...]

    @property
    def history(self) -> ActivityAssetHistory:
        return self.repository.history


def _purchase(name: str, price: str, *, activity: str | None = None) -> Transaction:
    """The bank row of a purchase in a register-owned amortization category: price plus 21 % IVA."""
    base = Decimal(price)
    iva = (base * Decimal("0.21")).quantize(Decimal("0.01"))
    row = _machine_acquisition_transaction(
        str(amortizable_spending_categories()[0]),
        provider_id=name,
        amount=base + iva,
        taxable_base=base,
        iva_amount=iva,
    )
    return row if activity is None else row.model_copy(update={"tipo_actividad": TipoActividad(activity)})


def _register(
    operation: PinnedAuthorityOperation,
    *rows: Transaction,
    modality: DirectEstimationRegime = _NORMAL,
) -> _Register:
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
            modelo_100_revision=operation.revision_for_context("100", filing_year=covered_from.year, period="0A"),
            authority_generation=operation.pin().logical_generation,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=lambda: (),
            legal_reference=operation.legal_reference,
            requested_free_amount=requested_free_amount,
        )

    repository = MemoryRepository()
    return _Register(
        operations=ActivityAssetOperations(
            repository=repository,
            ledger=MemoryLedger(*rows),
            forecast_operation=forecast,
            taxpayer_modality=lambda: modality,
            register_authority=replace(
                memory_register_authority(),
                disposal_bounds=pinned_disposal_bounds(operation),
            ),
        ),
        repository=repository,
        rows=rows,
    )


def _linear(
    class_key: str,
    regime: DirectEstimationRegime = _NORMAL,
    *,
    linear_coefficient: Decimal | None = None,
    small_enterprise: SmallEnterpriseEvidence | None = None,
) -> ActivityAssetAmortizationElection:
    facts: dict[str, object] = {}
    if linear_coefficient is not None:
        facts["linear_coefficient"] = linear_coefficient
    if small_enterprise is not None:
        facts["small_enterprise"] = small_enterprise
    return ActivityAssetAmortizationElection.model_validate(
        {"regime": regime, "method": AmortizationMethod.LINEAR, "authority_class_key": class_key, **facts},
    )


def _goodwill() -> ActivityAssetAmortizationElection:
    return ActivityAssetAmortizationElection(regime=_NORMAL, method=AmortizationMethod.GOODWILL)


def _element(
    asset_id: str,
    purchase: Transaction,
    election: ActivityAssetAmortizationElection,
    price: str,
    *,
    in_service: date = _YEAR_START,
    kind: AssetKind = AssetKind.MATERIAL,
    condition: AcquiredCondition = AcquiredCondition.NEW,
    opening: str = "0",
    opening_through: int | None = None,
    basis: ActivityAssetBasis | None = None,
    shape: AcquisitionShape = AcquisitionShape.PRIMARY_PURCHASE,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=purchase.transaction_id,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=shape,
        asset_kind=kind,
        basis=basis
        or ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal(price),
            non_deductible_iva=_ZERO,
            prior_allocation_provenance="reviewed business allocation",
        ),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal(opening),
            covered_through_tax_year=(opening_through or in_service.year) if Decimal(opening) else None,
        ),
        acquired_condition=condition,
        amortization=election,
    )


def _claim(register: _Register, asset_id: str, start: date, end: date) -> ScheduledAmortizationCharge:
    """Forecast one interval and record it, as the forecast-then-claim operations do."""
    forecast = register.operations.forecast(asset_id=asset_id, covered_from=start, covered_until=end)
    register.operations.record_claim(forecast, creating_operation="test.oracle")
    return forecast


def _m100(register: _Register) -> tuple[Decimal, Decimal, CalculationSourceResolution]:
    """Return casillas 0208 and 0227 of Modelo 100 for 2025, and the resolution behind them."""
    resolution = resolve_m100(register.history, rows=register.rows)
    revision = _revision("100", "2025")
    return (
        resolution.binding_values.get(_renta_expense_binding_id(revision, "0208"), _ZERO),
        resolution.binding_values.get(_renta_expense_binding_id(revision, "0227"), _ZERO),
        resolution,
    )


def _m130(register: _Register, quarter: str) -> tuple[Decimal, CalculationSourceResolution]:
    """Return casilla 02 of the cumulative Modelo 130 of ``quarter``, and the resolution behind it."""
    resolution = resolve_m130(register.history, quarter, rows=register.rows)
    return (
        resolution.binding_values.get(_m130_binding_id(_revision("130", "2019-y-siguientes")), _ZERO),
        resolution,
    )


def _small_enterprise(turnover: str) -> SmallEnterpriseEvidence:
    return SmallEnterpriseEvidence(
        evidence_reference="prior-year-accounts",
        made_available_on=date(2025, 11, 15),
        prior_period_net_turnover=Decimal(turnover),
    )


def _accelerated_machine(
    operation: PinnedAuthorityOperation,
    *,
    linear_coefficient: Decimal | None = None,
) -> _Register:
    """The manual's 36.000 machine in service on 1 December 2025, with a prior-year turnover of 2.800.000."""
    purchase = _purchase("accelerated-machine", "36000")
    register = _register(operation, purchase)
    register.operations.create(
        _element(
            "machine",
            purchase,
            _linear(
                "maquinaria",
                linear_coefficient=linear_coefficient,
                small_enterprise=_small_enterprise("2800000"),
            ),
            "36000",
            in_service=date(2025, 12, 1),
        ),
        _DESCRIPTOR,
    )
    return register


# --- Manual example: accelerated amortization of a new machine (LIS art. 103) ------------------
#
# Machine of 36.000 in service on 1 December 2025; maximum linear coefficient of machinery 12 %,
# doubled to 24 %.  Prior-year turnover 2.800.000, below the 10.000.000 limit.
#
# The manual prorates by months: 24 % x 36.000 x 1/12 = 720.  The register prorates by days in
# service, 31 of 365: 36.000 x 24 % x 31 / 365 = 8.640 x 31 / 365 = 733,8082..., so 733,81.  The
# coefficient is a corridor between the maximum and the one the maximum period implies (RIS art.
# 4.1), so the manual's 720 is a lawful smaller claim.  It needs the elected coefficient
# 720 x 365 / (36.000 x 31) = 0,2354838..., entered to seven decimals as 0,2354839.


def test_the_accelerated_machine_claims_the_day_count_maximum_into_both_forms(
    operation: PinnedAuthorityOperation,
) -> None:
    register = _accelerated_machine(operation)

    forecast = _claim(register, "machine", _YEAR_START, _YEAR_END)

    assert (forecast.covered_from, forecast.service_days) == (date(2025, 12, 1), 31)
    assert forecast.amount == Decimal("733.81")
    box_0208, box_0227, _ = _m100(register)
    assert (box_0208, box_0227) == (Decimal("733.81"), _ZERO)
    assert _m130(register, "3T")[0] == _ZERO
    assert _m130(register, "4T")[0] == Decimal("733.81")


def test_the_manuals_720_is_an_elected_claim_inside_the_corridor_and_reaches_both_forms(
    operation: PinnedAuthorityOperation,
) -> None:
    register = _accelerated_machine(operation, linear_coefficient=Decimal("0.2354839"))

    forecast = _claim(register, "machine", _YEAR_START, _YEAR_END)

    assert forecast.amount == Decimal("720.00")
    assert forecast.amount < Decimal("733.81")
    box_0208, box_0227, _ = _m100(register)
    assert (box_0208, box_0227) == (Decimal("720.00"), _ZERO)
    assert _m130(register, "4T")[0] == Decimal("720.00")


@pytest.mark.parametrize("outside", ["0.25", "0.05"])
def test_an_elected_coefficient_outside_the_corridor_is_refused_at_forecast(
    operation: PinnedAuthorityOperation,
    outside: str,
) -> None:
    # Above the doubled maximum 24 %, and below the 1/18 = 5,56 % the 18-year maximum period implies.
    register = _accelerated_machine(operation, linear_coefficient=Decimal(outside))

    with pytest.raises(ActividadAssetValidationError, match="elected_coefficient_out_of_range"):
        register.operations.forecast(asset_id="machine", covered_from=_YEAR_START, covered_until=_YEAR_END)
    assert register.history.claims == ()


# --- Manual examples: reduced-size enterprise by turnover (LIS art. 101) -----------------------
#
# The manual's four owners, as the register receives them: the prior-period turnover as one
# figure.  The determination itself (three-year look-back, annualizing a short year) is the
# operator's; the register applies the 10.000.000 limit to the figure it is given.  A 10.000,00
# machine in service on 1 December that qualifies charges 10.000 x 24 % x 31 / 365 = 203,8356,
# so 203,84.


@pytest.mark.parametrize(
    ("turnover", "reduced_size"),
    [
        ("8300000", True),  # example a: 2024 turnover 8.300.000
        ("10100000", False),  # example b: 2024 turnover 10.100.000
        ("9200000", True),  # example c: 4.600.000 over six months, raised to the year
        ("240000", True),  # example d: 60.000 over three months, raised to the year
    ],
)
def test_the_reduced_size_limit_applies_to_the_prior_period_turnover_it_is_given(
    operation: PinnedAuthorityOperation,
    turnover: str,
    reduced_size: bool,
) -> None:
    purchase = _purchase("reduced-size-machine", "10000")
    register = _register(operation, purchase)
    register.operations.create(
        _element(
            "machine",
            purchase,
            _linear("maquinaria", small_enterprise=_small_enterprise(turnover)),
            "10000",
            in_service=date(2025, 12, 1),
        ),
        _DESCRIPTOR,
    )

    if reduced_size:
        forecast = register.operations.forecast(asset_id="machine", covered_from=_YEAR_START, covered_until=_YEAR_END)
        assert forecast.amount == Decimal("203.84")
    else:
        with pytest.raises(ActividadAssetUnsupportedError, match="reduced_size_turnover_reached"):
            register.operations.forecast(asset_id="machine", covered_from=_YEAR_START, covered_until=_YEAR_END)


# --- Manual example: leasing, and the regimes the register does not take -----------------------


def test_an_unexercised_financial_lease_is_refused_so_the_leasing_limit_is_not_a_figure() -> None:
    purchase = _purchase("leased-van", "16000")

    with pytest.raises(ValidationError, match="financial_lease_unexercised"):
        _element(
            "van",
            purchase,
            _linear("maquinaria"),
            "16000",
            in_service=date(2025, 7, 1),
            shape=AcquisitionShape.FINANCIAL_LEASE_UNEXERCISED,
        )


def test_estimacion_objetiva_is_not_a_regime_an_election_can_name() -> None:
    with pytest.raises(ValidationError, match="regime"):
        ActivityAssetAmortizationElection.model_validate(
            {"regime": "objetiva", "method": "linear", "authority_class_key": "maquinaria"},
        )


# --- Manual examples under modulos: the pending-value cap, with their figures ------------------
#
# The modulos example amortizes a coffee machine of 9.400 whose accumulated amortization at the end
# of 2024 is 8.400, and the agrarian example a spreader of 7.500 with 7.200 accumulated, both at a
# 25 % maximum coefficient.  The coefficient would give 2.350 and 1.875; each stops at the value
# still pending, 1.000 and 300.  A trailer of 3.155 already fully amortized charges nothing.  The
# elements here are computing equipment, which has the same 25 % maximum under direct estimation.


def test_a_charge_stops_at_the_value_still_pending_and_a_spent_element_charges_nothing(
    operation: PinnedAuthorityOperation,
) -> None:
    rows = (_purchase("coffee-machine", "9400"), _purchase("spreader", "7500"), _purchase("trailer", "3155"))
    register = _register(operation, *rows)
    for asset_id, row, price, pending_before in (
        ("coffee-machine", rows[0], "9400", "8400"),
        ("spreader", rows[1], "7500", "7200"),
        ("trailer", rows[2], "3155", "3155"),
    ):
        register.operations.create(
            _element(
                asset_id,
                row,
                _linear("equipo-proceso-informacion"),
                price,
                in_service=date(2019, 1, 1),
                opening=pending_before,
                opening_through=2024,
            ),
            _DESCRIPTOR,
        )

    charges = {
        asset_id: _claim(register, asset_id, _YEAR_START, _YEAR_END).amount
        for asset_id in (
            "coffee-machine",
            "spreader",
            "trailer",
        )
    }

    assert charges == {
        "coffee-machine": Decimal("1000.00"),  # 9.400 - 8.400, not 9.400 x 25 % = 2.350
        "spreader": Decimal("300.00"),  # 7.500 - 7.200, not 7.500 x 25 % = 1.875
        "trailer": Decimal("0.00"),
    }
    box_0208, box_0227, _ = _m100(register)
    assert (box_0208, box_0227) == (Decimal("1300.00"), _ZERO)
    assert _m130(register, "4T")[0] == Decimal("1300.00")


# --- Used asset (RIS art. 4.3.a), hand-worked --------------------------------------------------
#
# RIS art. 4.3.a: "Sobre el precio de adquisicion, hasta el limite resultante de multiplicar por 2
# la cantidad derivada de aplicar el coeficiente de amortizacion lineal maximo."
#
# A used machine bought for 10.000 and in service on 1 April 2025 (275 days of service).
# Machinery's maximum is 12 %, so the limit is 24 %: 10.000 x 24 % = 2.400 a year.  Cumulative
# from 1 April, rounded to cents at each quarter's end:
#   to 1 July (91 days):    2.400 x  91 / 365 =   598,3561 =   598,36
#   to 1 October (183):     2.400 x 183 / 365 = 1.203,2877 = 1.203,29
#   to 1 January 2026 (275): 2.400 x 275 / 365 = 1.808,2192 = 1.808,22
# so the three quarterly claims are 598,36, 604,93 and 604,93.  A new twin at 12 % charges
# 1.200 x 275 / 365 = 904,1096 = 904,11, and 2 x 904,11 = 1.808,22.


def _used_machine(operation: PinnedAuthorityOperation) -> _Register:
    purchase = _purchase("used-machine", "10000")
    register = _register(operation, purchase)
    register.operations.create(
        _element(
            "used-machine",
            purchase,
            _linear("maquinaria"),
            "10000",
            in_service=date(2025, 4, 1),
            condition=AcquiredCondition.USED,
        ),
        _DESCRIPTOR,
    )
    return register


def test_a_used_machine_is_charged_at_twice_the_maximum_on_its_price(operation: PinnedAuthorityOperation) -> None:
    register = _used_machine(operation)

    claims = [
        _claim(register, "used-machine", start, end)
        for start, end in zip(_QUARTER_STARTS[1:], _QUARTER_ENDS[1:], strict=True)
    ]

    assert [claim.amount for claim in claims] == [Decimal("598.36"), Decimal("604.93"), Decimal("604.93")]
    assert [claim.service_days for claim in claims] == [91, 92, 92]
    assert [_m130(register, quarter)[0] for quarter in _QUARTERS] == [
        _ZERO,
        Decimal("598.36"),
        Decimal("1203.29"),
        Decimal("1808.22"),
    ]
    assert _m100(register)[0] == Decimal("1808.22")


def test_a_used_machine_cannot_elect_more_than_twice_the_maximum_and_a_new_one_gets_half(
    operation: PinnedAuthorityOperation,
) -> None:
    used_over = _purchase("used-over", "10000")
    over = _register(operation, used_over)
    over.operations.create(
        _element(
            "over",
            used_over,
            _linear("maquinaria", linear_coefficient=Decimal("0.25")),
            "10000",
            in_service=date(2025, 4, 1),
            condition=AcquiredCondition.USED,
        ),
        _DESCRIPTOR,
    )
    new_purchase = _purchase("new-twin", "10000")
    twin = _register(operation, new_purchase)
    twin.operations.create(
        _element("twin", new_purchase, _linear("maquinaria"), "10000", in_service=date(2025, 4, 1)),
        _DESCRIPTOR,
    )

    with pytest.raises(ActividadAssetValidationError, match="elected_coefficient_out_of_range"):
        over.operations.forecast(asset_id="over", covered_from=_YEAR_START, covered_until=_YEAR_END)
    assert twin.operations.forecast(asset_id="twin", covered_from=_YEAR_START, covered_until=_YEAR_END).amount == (
        Decimal("904.11")
    )


# --- Manual example: baja of an element afecto, by day count -----------------------------------
#
# A building affected on 1 January 1998 and valued at 54.000, of which 60 % (32.400) is
# construction; simplified modality, linear 3 %.  A full year charges 32.400 x 3 % = 972, and the
# 27 years 1998 to 2024 charged 27 x 972 = 26.244.  Sold on 30 June 2025 for 210.000 with 13.000 of
# costs.
#
# The manual halves the year, 486, and gets accumulated 26.730 and a gain of 169.730.  The sale
# date is the last day of service, so 2025 has 181 of 365 days: 972 x 181 / 365 = 482,0055, so
# 482,01, and 486 would exceed the day-count maximum.  Accumulated 26.244 + 482,01 = 26.726,01;
# acquisition value 54.000 less that = 27.273,99; gain 210.000 - 13.000 - 27.273,99 = 169.726,01.


def test_the_manuals_sold_building_reduces_cost_by_the_day_count_charge(operation: PinnedAuthorityOperation) -> None:
    purchase = _purchase("sold-building", "54000")
    register = _register(operation, purchase, modality=_SIMPLIFIED)
    building = ActivityAssetBasis(
        stage=AssetBasisStage.WHOLE_PROPERTY,
        basis_amount=Decimal("54000"),
        non_deductible_iva=_ZERO,
        is_property=True,
        construction_cost=Decimal("32400"),
        land_cost=Decimal("21600"),
        ownership_mode=OwnershipMode.SOLE,
        ownership_share=Decimal("1"),
        office_area=Decimal("1"),
        total_area=Decimal("1"),
    )
    register.operations.create(
        _element(
            "building",
            purchase,
            _linear("edificio-otra-construccion", _SIMPLIFIED),
            "54000",
            in_service=date(1998, 1, 1),
            condition=AcquiredCondition.USED,
            opening="26244",
            opening_through=2024,
            basis=building,
        ),
        _DESCRIPTOR,
    )
    full_year = _claim(register, "building", _YEAR_START, _YEAR_END)

    register.operations.dispose(
        "building",
        ActivityAssetDisposal(
            disposal_date=date(2025, 6, 30),
            reason=ActivityAssetDisposalReason.SALE,
            proceeds=Decimal("210000.00"),
            transmission_costs=Decimal("13000.00"),
        ),
    )
    _, calculation = register.operations.disposal_calculation("building")

    assert full_year.amount == Decimal("972.00")
    shortened = [claim for claim in effective_claims(register.history.claims) if claim.tax_year == 2025]
    assert [(claim.amount, claim.covered_until) for claim in shortened] == [(Decimal("482.01"), date(2025, 7, 1))]
    assert calculation.deducted == Decimal("26726.01")
    assert calculation.net_value == Decimal("27273.99")
    assert calculation.result == Decimal("169726.01")
    box_0208, _, resolution = _m100(register)
    assert box_0208 == Decimal("482.01")
    gains = [
        value for binding, value in resolution.binding_values.items() if str(binding).endswith("gain-property-1843")
    ]
    assert gains == [Decimal("169726.01")]
    assert "unrouted_observation" not in {item.reason for item in resolution.diagnostics}


# --- Invariants over a mixed register ----------------------------------------------------------
#
# Three elements claimed quarter by quarter:
#   machine  7.700 at 12 %, in service 17 March (15, 106, 198 and 290 days at each quarter end);
#   used     the 10.000 machine above, from 1 April;
#   goodwill 1.000 at 5 %, from 1 January.
# Cumulative amounts rounded to cents at each quarter end, hand-worked as 7.700 x 12 % x days / 365:
#   machine  37,97  268,34  501,24  734,14   (claims 37,97  230,37  232,90  232,90)
#   used      0,00  598,36 1.203,29 1.808,22
#   goodwill 12,33   24,79   37,40   50,00   (claims 12,33   12,46   12,61   12,60)
#   total    50,30  891,49 1.741,93 2.592,36
_CUMULATIVE_BY_QUARTER = (Decimal("50.30"), Decimal("891.49"), Decimal("1741.93"), Decimal("2592.36"))


def _mixed_register(operation: PinnedAuthorityOperation) -> _Register:
    rows = (
        _purchase("mixed-machine", "7700"),
        _purchase("mixed-used", "10000"),
        _purchase("mixed-goodwill", "1000"),
    )
    register = _register(operation, *rows)
    register.operations.create(
        _element("machine", rows[0], _linear("maquinaria"), "7700", in_service=date(2025, 3, 17)),
        _DESCRIPTOR,
    )
    register.operations.create(
        _element(
            "used",
            rows[1],
            _linear("maquinaria"),
            "10000",
            in_service=date(2025, 4, 1),
            condition=AcquiredCondition.USED,
        ),
        _DESCRIPTOR,
    )
    register.operations.create(
        _element("goodwill", rows[2], _goodwill(), "1000", kind=AssetKind.INTANGIBLE),
        _DESCRIPTOR,
    )
    return register


def _claim_every_quarter(register: _Register) -> dict[str, list[Decimal]]:
    """Claim each element in each quarter it is in service; return the amounts by element."""
    in_service_from = {"machine": 0, "used": 1, "goodwill": 0}
    return {
        asset_id: [
            _claim(register, asset_id, _QUARTER_STARTS[index], _QUARTER_ENDS[index]).amount for index in range(first, 4)
        ]
        for asset_id, first in in_service_from.items()
    }


def test_the_quarterly_claims_sum_to_the_annual_charge_and_the_annual_forecast(
    operation: PinnedAuthorityOperation,
) -> None:
    register = _mixed_register(operation)
    twin = _mixed_register(operation)

    amounts = _claim_every_quarter(register)

    assert amounts == {
        "machine": [Decimal("37.97"), Decimal("230.37"), Decimal("232.90"), Decimal("232.90")],
        "used": [Decimal("598.36"), Decimal("604.93"), Decimal("604.93")],
        "goodwill": [Decimal("12.33"), Decimal("12.46"), Decimal("12.61"), Decimal("12.60")],
    }
    annual = {
        asset_id: twin.operations.forecast(asset_id=asset_id, covered_from=_YEAR_START, covered_until=_YEAR_END).amount
        for asset_id in amounts
    }
    assert annual == {
        "machine": Decimal("734.14"),
        "used": Decimal("1808.22"),
        "goodwill": Decimal("50.00"),
    }
    for asset_id, quarterly in amounts.items():
        assert sum(quarterly, _ZERO) == annual[asset_id]


def test_modelo_130_accrues_the_hand_worked_total_each_quarter_and_the_fourth_equals_0208_plus_0227(
    operation: PinnedAuthorityOperation,
) -> None:
    register = _mixed_register(operation)
    _claim_every_quarter(register)

    cumulative = [_m130(register, quarter)[0] for quarter in _QUARTERS]
    box_0208, box_0227, _ = _m100(register)

    assert tuple(cumulative) == _CUMULATIVE_BY_QUARTER
    assert (box_0208, box_0227) == (Decimal("2542.36"), Decimal("50.00"))
    assert cumulative[3] == box_0208 + box_0227
    assert all(later >= earlier for earlier, later in pairwise(cumulative))

    handoff = register.operations.filing_handoff(tax_year=2025, m130_period=Period.from_year_and_code(2025, "4T"))
    assert handoff.material_m100.amount == box_0208
    assert handoff.intangible_m100.amount == box_0227
    assert handoff.material_m130.amount + handoff.intangible_m130.amount == cumulative[3]


def test_a_claim_gap_is_a_non_blocking_finding_and_no_deduction_is_invented(
    operation: PinnedAuthorityOperation,
) -> None:
    rows = (_purchase("gap-machine", "10000"), _purchase("gap-goodwill", "1000"))
    register = _register(operation, *rows)
    register.operations.create(
        _element("machine", rows[0], _linear("maquinaria"), "10000"),
        _DESCRIPTOR,
    )
    register.operations.create(
        _element("goodwill", rows[1], _goodwill(), "1000", kind=AssetKind.INTANGIBLE),
        _DESCRIPTOR,
    )
    # Only the first quarter of the machine is claimed: 10.000 x 12 % x 90 / 365 = 295,89.
    first_quarter = _claim(register, "machine", _YEAR_START, date(2025, 4, 1))

    box_0208, box_0227, annual = _m100(register)
    gaps = [item for item in annual.diagnostics if item.reason == "activity_asset_claim_gap"]

    assert first_quarter.amount == Decimal("295.89")
    assert (box_0208, box_0227) == (Decimal("295.89"), _ZERO)
    assert len(gaps) == 2
    assert not set(_reasons(annual)) & GATE_REFUSED_REASONS
    by_asset = {item.source_ref: item.message for item in gaps}
    # 1.200,00 less the 295,89 claimed; the whole 50,00 of the unclaimed goodwill.
    assert "904.11 EUR accrued" in by_asset["activity-asset:machine"]
    assert "2025-04-01 to 2026-01-01" in by_asset["activity-asset:machine"]
    assert "50.00 EUR accrued" in by_asset["activity-asset:goodwill"]
    # The quarterly form still accrues from the schedule, so a later annual claim stays possible.
    assert _m130(register, "4T")[0] == Decimal("1250.00")


def test_an_agrarian_element_adds_nothing_to_casilla_02_but_still_reaches_modelo_100(
    operation: PinnedAuthorityOperation,
) -> None:
    farm_row = _purchase("farm-machine", "10000", activity="B01")
    office_row = _purchase("office-computer", "2000", activity="A05")
    register = _register(operation, farm_row, office_row)
    register.operations.create(_element("farm", farm_row, _linear("maquinaria"), "10000"), _DESCRIPTOR)
    register.operations.create(
        _element("office", office_row, _linear("equipo-proceso-informacion"), "2000"),
        _DESCRIPTOR,
    )
    farm = _claim(register, "farm", _YEAR_START, _YEAR_END)
    office = _claim(register, "office", _YEAR_START, _YEAR_END)

    box_0208, _, _ = _m100(register)
    box_02, quarterly = _m130(register, "4T")

    # 10.000 x 12 % = 1.200,00 and 2.000 x 25 % = 500,00.
    assert (farm.amount, office.amount) == (Decimal("1200.00"), Decimal("500.00"))
    assert box_0208 == Decimal("1700.00")
    assert box_02 == Decimal("500.00")
    excluded = [item for item in quarterly.diagnostics if item.reason == "activity_asset_agrarian_excluded"]
    assert [item.source_ref for item in excluded] == ["activity-asset:farm"]


def test_a_charge_never_pushes_total_amortization_past_the_amortizable_base(
    operation: PinnedAuthorityOperation,
) -> None:
    # A used element of 1.000 from 1 July 2022 at twice the 25 % maximum, 50 %:
    #   2022: 1.000 x 50 % x 184 / 365 = 252,05;  2023: 500,00;
    #   2024: 500,00 would reach 1.252,05, so it stops at the 247,95 still pending;  2025: nothing left.
    purchase = _purchase("capped-computer", "1000")
    register = _register(operation, purchase)
    register.operations.create(
        _element(
            "computer",
            purchase,
            _linear("equipo-proceso-informacion"),
            "1000",
            in_service=date(2022, 7, 1),
            condition=AcquiredCondition.USED,
        ),
        _DESCRIPTOR,
    )

    yearly = [_claim(register, "computer", date(year, 1, 1), date(year + 1, 1, 1)).amount for year in range(2022, 2026)]

    assert yearly == [Decimal("252.05"), Decimal("500.00"), Decimal("247.95"), Decimal("0.00")]
    assert sum(yearly, _ZERO) == Decimal("1000.00")
    assert sum((claim.amount for claim in effective_claims(register.history.claims)), _ZERO) <= Decimal("1000.00")
    assert _m100(register)[0] == _ZERO


def test_no_ledger_category_reaches_0208_or_0227_without_the_register(operation: PinnedAuthorityOperation) -> None:
    categories = amortizable_spending_categories()
    assert categories

    for index, category in enumerate(categories):
        row = _machine_acquisition_transaction(str(category), provider_id=f"unregistered-{index}")
        register = _register(operation, row)

        box_0208, box_0227, annual = _m100(register)
        box_02, quarterly = _m130(register, "4T")

        assert (box_0208, box_0227, box_02) == (_ZERO, _ZERO, _ZERO), category
        for resolution in (annual, quarterly):
            assert "ledger_amortization_row_unregistered" in _reasons(resolution), category
            assert row.transaction_id not in resolution.source_transaction_ids, category
