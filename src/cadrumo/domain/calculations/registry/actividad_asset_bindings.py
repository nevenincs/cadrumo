"""Resolve an activity-asset amortization election against registry authority.

The immutable asset revision carries the taxpayer's election.  This resolver
validates it against the Modelo 100 revision's published parameters (method
admission per modality, table-class groups, coefficient bounds, weighting
bands, thresholds and incentive windows) and emits the one typed
:class:`ScheduleAuthority` the schedule consumes.  Every legal number comes
from a parameter; an absent row is unsupported and a row valued zero is an
exclusion the parameter's legal references ground.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ...renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ...renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...renta.actividad_asset.schedule import ScheduleAuthority, add_fractional_years, add_years
from .formula_runtime_ops import resolve_dated_value, resolve_keyed_bracket
from .schema import ModeloRevision
from .schema_base import ThresholdComparison
from .schema_formula import ParameterDefinition

_PREFIX = "renta-actividad-inmovilizado-amortizacion"
_COEFFICIENT_IDS = {
    DirectEstimationRegime.NORMAL: f"{_PREFIX}-normal-coeficiente-lineal-maximo",
    DirectEstimationRegime.SIMPLIFIED: f"{_PREFIX}-simplificada-coeficiente-lineal-maximo",
}
_PERIOD_IDS = {
    DirectEstimationRegime.NORMAL: f"{_PREFIX}-normal-periodo-maximo-anos",
    DirectEstimationRegime.SIMPLIFIED: f"{_PREFIX}-simplificada-periodo-maximo-anos",
}
_METHOD_ADMISSION_IDS = {
    DirectEstimationRegime.NORMAL: f"{_PREFIX}-normal-metodo-admitido",
    DirectEstimationRegime.SIMPLIFIED: f"{_PREFIX}-simplificada-metodo-admitido",
}
_BUILDING_CLASS_ID = f"{_PREFIX}-clase-edificio"
_FURNITURE_CLASS_ID = f"{_PREFIX}-clase-mobiliario-enseres"
_WEIGHTING_ID = f"{_PREFIX}-porcentaje-constante-ponderacion"
_MEDIUM_PERIOD_ID = f"{_PREFIX}-porcentaje-constante-umbral-periodo-medio"
_LONG_PERIOD_ID = f"{_PREFIX}-porcentaje-constante-umbral-periodo-largo"
_MINIMUM_PERCENTAGE_ID = f"{_PREFIX}-porcentaje-constante-minimo"
_USED_MULTIPLIER_ID = f"{_PREFIX}-usado-multiplicador-coeficiente-maximo"
_USED_BUILDING_AGE_ID = f"{_PREFIX}-edificio-usado-antiguedad-minima"
_SHIFT_HOURS_ID = f"{_PREFIX}-turno-normal-horas"
_ERD_TURNOVER_ID = f"{_PREFIX}-erd-cifra-negocios-umbral"
_ERD_MULTIPLIER_ID = f"{_PREFIX}-erd-multiplicador-coeficiente-maximo"
_RND_BUILDING_PERIOD_ID = f"{_PREFIX}-idi-edificio-periodo"
_CHARGING_FIRST_YEAR_ID = f"{_PREFIX}-infraestructura-recarga-primer-ejercicio"
_CHARGING_LAST_YEAR_ID = f"{_PREFIX}-infraestructura-recarga-ultimo-ejercicio"
_INDEFINITE_LIFE_RATE_ID = "renta-actividad-inmovilizado-intangible-vida-util-no-estimable-limite-anual"
_GOODWILL_RATE_ID = "renta-actividad-fondo-comercio-amortizacion-limite-anual"
_LOW_VALUE_THRESHOLD_ID = "renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-umbral-unitario"
_LOW_VALUE_ANNUAL_CAP_ID = "renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-limite-anual"

_REFUSED_METHODS: dict[AmortizationMethod, str] = {
    AmortizationMethod.JUSTIFIED_AMOUNT: (
        "LIS art. 12.1.e admits an amount the taxpayer justifies, but no registry authority can validate that "
        "justification, and an unvalidated caller amount cannot become a filing-grade charge"
    ),
    AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE: (
        "LIS art. 102 depends on the average workforce over the following 48 months, and no canonical "
        "average-workforce fact exists"
    ),
    AmortizationMethod.RENEWABLE_SELF_CONSUMPTION_FREE: (
        "LIS DA 17a depends on maintaining the average workforce for 24 months, and no canonical "
        "average-workforce fact exists"
    ),
    AmortizationMethod.ELECTRIC_VEHICLE_FREE: (
        "LIS DA 18a.1 covers vehicles, whose IRPF affectation is outside the enrolled activity-asset scope"
    ),
    AmortizationMethod.ENTITY_REGIME_FREE: (
        "LIS art. 12.3.a and 12.3.d apply to sociedades laborales and explotaciones asociativas prioritarias, "
        "which are entities rather than individual taxpayers"
    ),
}
_INDEFINITE_ACCELERATION_REFUSAL = (
    "reduced-size acceleration of indefinite-life intangibles and goodwill is refused: LIS art. 103.5 in the "
    "consolidated text cross-refers to the pre-2016 art. 13.3 regime while the AEAT 2025 manual applies 150% "
    "to the art. 12.2 amount, so the two official sources disagree on its scope"
)


@dataclass(frozen=True, slots=True)
class _Parameters:
    by_id: dict[str, ParameterDefinition]
    revision_id: str
    tax_year: int

    def require(self, parameter_id: str) -> ParameterDefinition:
        parameter = self.by_id.get(parameter_id)
        if parameter is None:
            raise ActividadAssetUnsupportedError(
                f"activity-asset authority parameter {parameter_id!r} is absent from Modelo 100 revision "
                f"{self.revision_id}",
            )
        return parameter

    def keyed(self, parameter_id: str, key: str) -> Decimal | None:
        return resolve_keyed_bracket(self.require(parameter_id), key=key, filing_year=self.tax_year)

    def scalar(self, parameter_id: str) -> tuple[Decimal, ThresholdComparison]:
        try:
            resolved = resolve_dated_value(
                self.require(parameter_id),
                {"filing_period": date(self.tax_year, 12, 31)},
            )
        except ActividadAssetUnsupportedError:
            raise
        except Exception as exc:
            raise ActividadAssetUnsupportedError(
                f"activity-asset authority parameter {parameter_id!r} is not resolvable for {self.tax_year}",
            ) from exc
        return resolved.value, resolved.comparison

    def value(self, parameter_id: str) -> Decimal:
        return self.scalar(parameter_id)[0]

    def reference(self, parameter_id: str, key: str | None = None) -> str:
        suffix = f":key:{key}" if key is not None else ""
        return f"modelo-100:{self.revision_id}:parameter:{parameter_id}{suffix}"


@dataclass(frozen=True, slots=True)
class _Resolution:
    method_facts: dict[str, object]
    references: tuple[str, ...]


def resolve_activity_asset_schedule_authority(
    modelo_revision: ModeloRevision,
    *,
    tax_year: int,
    asset_revision: ActivityAssetRevision,
    authority_generation: str,
) -> ScheduleAuthority:
    """Validate one revision's election and resolve its tax-year authority."""
    if modelo_revision.id != str(tax_year):
        raise ActividadAssetUnsupportedError(
            f"Modelo 100 revision {modelo_revision.id} does not govern tax year {tax_year}",
        )
    election = asset_revision.amortization
    refusal = _REFUSED_METHODS.get(election.method)
    if refusal is not None:
        raise ActividadAssetUnsupportedError(refusal)
    parameters = _Parameters(
        by_id={str(parameter.id): parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    admission_reference = _require_method_admitted(parameters, asset_revision)
    resolution = _resolve_method(parameters, asset_revision)
    return ScheduleAuthority.model_validate(
        {
            "tax_year": tax_year,
            "asset_kind": asset_revision.asset_kind,
            "method": election.method,
            "election_fingerprint": election.fingerprint,
            "authority_generation": authority_generation,
            "source_reference": ";".join((admission_reference, *resolution.references)),
            **resolution.method_facts,
        },
    )


def _require_method_admitted(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> str:
    election = asset_revision.amortization
    parameter_id = _METHOD_ADMISSION_IDS[election.regime]
    key = f"{asset_revision.asset_kind.value}:{election.method.value}"
    admitted = parameters.keyed(parameter_id, key)
    if admitted is None:
        raise ActividadAssetUnsupportedError(
            f"{election.method.value} is not enrolled for {asset_revision.asset_kind.value} assets in the "
            f"{election.regime.value} modality",
        )
    if admitted == Decimal("0"):
        legal = ", ".join(parameters.require(parameter_id).legal_refs)
        raise ActividadAssetUnsupportedError(
            f"{election.method.value} is excluded by law for {asset_revision.asset_kind.value} assets in the "
            f"{election.regime.value} modality ({legal})",
        )
    if admitted != Decimal("1"):
        raise ActividadAssetValidationError(f"method admission {key!r} is neither admitted nor excluded")
    return parameters.reference(parameter_id, key)


def _resolve_method(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    method = asset_revision.amortization.method
    if method is AmortizationMethod.LINEAR:
        return _resolve_linear(parameters, asset_revision)
    if method is AmortizationMethod.CONSTANT_PERCENTAGE:
        return _resolve_constant_percentage(parameters, asset_revision)
    if method is AmortizationMethod.SUM_OF_DIGITS:
        return _resolve_sum_of_digits(parameters, asset_revision)
    if method is AmortizationMethod.APPROVED_PLAN:
        return _resolve_approved_plan(parameters, asset_revision)
    if method is AmortizationMethod.INTANGIBLE_USEFUL_LIFE:
        return _resolve_useful_life(asset_revision)
    if method in {AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE, AmortizationMethod.GOODWILL}:
        return _resolve_twentieth_limit(parameters, asset_revision)
    if method is AmortizationMethod.LOW_VALUE_FREE:
        return _resolve_low_value(parameters, asset_revision)
    if method is AmortizationMethod.RESEARCH_DEVELOPMENT_FREE:
        return _resolve_research_development_free(parameters, asset_revision)
    if method is AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING:
        return _resolve_research_development_building(parameters, asset_revision)
    if method is AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE:
        return _resolve_charging_infrastructure(parameters, asset_revision)
    raise ActividadAssetUnsupportedError(f"{method.value} has no enrolled authority resolver")


@dataclass(frozen=True, slots=True)
class _TableBounds:
    class_key: str
    maximum: Decimal
    minimum: Decimal
    period_years: Decimal
    references: tuple[str, ...]


def _table_bounds(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _TableBounds:
    """Resolve the class's maximum coefficient and the one its maximum period implies."""
    election = asset_revision.amortization
    class_key = election.authority_class_key
    if class_key is None:
        raise ActividadAssetIncompleteError(f"{election.method.value} requires a statutory table class")
    _require_class_matches_kind(class_key, asset_revision.asset_kind)
    coefficient_id = _COEFFICIENT_IDS[election.regime]
    period_id = _PERIOD_IDS[election.regime]
    maximum_percent = parameters.keyed(coefficient_id, class_key)
    period_years = parameters.keyed(period_id, class_key)
    if maximum_percent is None or period_years is None:
        raise ActividadAssetUnsupportedError(
            f"table class {class_key!r} is not enrolled for the {election.regime.value} modality",
        )
    return _TableBounds(
        class_key=class_key,
        maximum=maximum_percent / Decimal("100"),
        minimum=Decimal("1") / period_years,
        period_years=period_years,
        references=(parameters.reference(coefficient_id, class_key), parameters.reference(period_id, class_key)),
    )


def _require_class_matches_kind(class_key: str, asset_kind: AssetKind) -> None:
    exclusively_intangible = class_key.startswith("intangible-")
    admits_intangible = exclusively_intangible or class_key == "equipo-informacion-software"
    if asset_kind is AssetKind.INTANGIBLE and not admits_intangible:
        raise ActividadAssetUnsupportedError("intangible asset requires an enrolled intangible authority class")
    if asset_kind is AssetKind.MATERIAL and exclusively_intangible:
        raise ActividadAssetUnsupportedError("material asset cannot use an exclusively intangible authority class")


def _class_flag(parameters: _Parameters, parameter_id: str, class_key: str) -> bool:
    flag = parameters.keyed(parameter_id, class_key)
    if flag is None:
        raise ActividadAssetUnsupportedError(f"table class {class_key!r} has no enrolled group classification")
    if flag not in {Decimal("0"), Decimal("1")}:
        raise ActividadAssetValidationError(f"group classification of {class_key!r} is not a flag")
    return flag == Decimal("1")


def _is_used_for_amortization(parameters: _Parameters, asset_revision: ActivityAssetRevision, class_key: str) -> bool:
    """Apply RIS art. 4.3: a building under the minimum age is not a used asset."""
    if asset_revision.acquired_condition is not AcquiredCondition.USED:
        return False
    if not _class_flag(parameters, _BUILDING_CLASS_ID, class_key):
        return True
    built = asset_revision.building_construction_date
    if built is None:
        raise ActividadAssetIncompleteError("a used building requires its construction date")
    minimum_age, comparison = parameters.scalar(_USED_BUILDING_AGE_ID)
    age = _whole_years_between(built, asset_revision.in_service_date)
    return _reaches(Decimal(age), minimum_age, comparison)


def _whole_years_between(start: date, end: date) -> int:
    years = end.year - start.year
    return years if add_years(start, years) <= end else years - 1


def _reaches(value: Decimal, threshold: Decimal, comparison: ThresholdComparison) -> bool:
    return value >= threshold if comparison is ThresholdComparison.INCLUSIVE else value > threshold


def _resolve_linear(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    election = asset_revision.amortization
    bounds = _table_bounds(parameters, asset_revision)
    maximum = bounds.maximum
    references = list(bounds.references)
    used = _is_used_for_amortization(parameters, asset_revision, bounds.class_key)
    if used and election.shift_hours_per_day is not None:
        raise ActividadAssetUnsupportedError(
            "RIS art. 4 does not state how the multi-shift and used-asset coefficients combine",
        )
    if used and election.regime is DirectEstimationRegime.NORMAL:
        maximum *= parameters.value(_USED_MULTIPLIER_ID)
        references.append(parameters.reference(_USED_MULTIPLIER_ID))
    if election.small_enterprise is not None:
        maximum *= _small_enterprise_multiplier(parameters, asset_revision, references)
    if election.shift_hours_per_day is not None:
        if election.regime is not DirectEstimationRegime.NORMAL:
            raise ActividadAssetUnsupportedError("the RIS art. 4.2 multi-shift coefficient is a normal-modality rule")
        shift_hours = parameters.value(_SHIFT_HOURS_ID)
        if election.shift_hours_per_day <= shift_hours:
            raise ActividadAssetValidationError("a multi-shift coefficient requires more than one normal shift a day")
        maximum = bounds.minimum + (bounds.maximum - bounds.minimum) * election.shift_hours_per_day / shift_hours
        references.append(parameters.reference(_SHIFT_HOURS_ID))
    coefficient = _elected_coefficient(election, minimum=bounds.minimum, maximum=maximum)
    return _Resolution(method_facts={"annual_rate": min(coefficient, Decimal("1"))}, references=tuple(references))


def _small_enterprise_multiplier(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    references: list[str],
) -> Decimal:
    """Validate LIS arts. 101 and 103.1 and return the acceleration multiplier."""
    evidence = asset_revision.amortization.small_enterprise
    if evidence is None:  # defensive: callers check presence first
        raise ActividadAssetIncompleteError("reduced-size acceleration requires its evidence")
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError("reduced-size acceleration applies only to new elements (LIS art. 103.1)")
    if evidence.made_available_on > asset_revision.in_service_date:
        raise ActividadAssetValidationError("an asset cannot enter service before it is made available")
    threshold, comparison = parameters.scalar(_ERD_TURNOVER_ID)
    if _reaches(evidence.prior_period_net_turnover, threshold, comparison):
        raise ActividadAssetUnsupportedError(
            "prior-period net turnover reaches the reduced-size threshold (LIS art. 101.1)",
        )
    references.extend((parameters.reference(_ERD_TURNOVER_ID), parameters.reference(_ERD_MULTIPLIER_ID)))
    return parameters.value(_ERD_MULTIPLIER_ID)


def _elected_coefficient(
    election: ActivityAssetAmortizationElection,
    *,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal:
    """Apply RIS art. 4.1: any coefficient between the period-implied and the maximum."""
    elected = election.linear_coefficient
    if elected is None:
        return maximum
    if not minimum <= elected <= maximum:
        raise ActividadAssetValidationError(
            f"elected coefficient {elected} is outside the admissible range [{minimum}, {maximum}]",
        )
    return elected


def _require_not_building_or_furniture(parameters: _Parameters, bounds: _TableBounds, provision: str) -> None:
    if _class_flag(parameters, _BUILDING_CLASS_ID, bounds.class_key) or _class_flag(
        parameters,
        _FURNITURE_CLASS_ID,
        bounds.class_key,
    ):
        raise ActividadAssetUnsupportedError(
            f"buildings, mobiliario and enseres cannot use this method ({provision})",
        )


def _resolve_constant_percentage(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS art. 12.1.b and RIS art. 5 to the elected coefficient."""
    bounds = _table_bounds(parameters, asset_revision)
    _require_not_building_or_furniture(parameters, bounds, "RIS art. 5.2")
    coefficient = _elected_coefficient(asset_revision.amortization, minimum=bounds.minimum, maximum=bounds.maximum)
    period = Decimal("1") / coefficient
    medium_threshold, medium_comparison = parameters.scalar(_MEDIUM_PERIOD_ID)
    long_threshold, long_comparison = parameters.scalar(_LONG_PERIOD_ID)
    if _reaches(period, long_threshold, long_comparison):
        band = "periodo-largo"
    elif _reaches(period, medium_threshold, medium_comparison):
        band = "periodo-medio"
    else:
        band = "periodo-corto"
    weight = parameters.keyed(_WEIGHTING_ID, band)
    if weight is None:
        raise ActividadAssetUnsupportedError(f"constant-percentage weighting {band!r} is not enrolled")
    floor = parameters.value(_MINIMUM_PERCENTAGE_ID) / Decimal("100")
    percentage = min(max(coefficient * weight, floor), Decimal("1"))
    return _Resolution(
        method_facts={
            "annual_rate": percentage,
            "useful_life_ends_on": add_fractional_years(asset_revision.in_service_date, period),
        },
        references=(
            *bounds.references,
            parameters.reference(_BUILDING_CLASS_ID, bounds.class_key),
            parameters.reference(_FURNITURE_CLASS_ID, bounds.class_key),
            parameters.reference(_MEDIUM_PERIOD_ID),
            parameters.reference(_LONG_PERIOD_ID),
            parameters.reference(_WEIGHTING_ID, band),
            parameters.reference(_MINIMUM_PERCENTAGE_ID),
        ),
    )


def _resolve_sum_of_digits(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply RIS art. 6: a whole-year period between the table bounds, inclusive."""
    election = asset_revision.amortization
    bounds = _table_bounds(parameters, asset_revision)
    _require_not_building_or_furniture(parameters, bounds, "RIS art. 6.2")
    period = election.sum_of_digits_period_years
    if period is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError("sum of digits requires its period")
    shortest = math.ceil(Decimal("1") / bounds.maximum)
    longest = bounds.period_years
    if not shortest <= period <= longest:
        raise ActividadAssetValidationError(
            f"sum-of-digits period {period} is outside the admissible whole-year range [{shortest}, {longest}]",
        )
    return _Resolution(
        method_facts={"sum_of_digits_period_years": period, "digit_order": election.digit_order},
        references=(
            *bounds.references,
            parameters.reference(_BUILDING_CLASS_ID, bounds.class_key),
            parameters.reference(_FURNITURE_CLASS_ID, bounds.class_key),
        ),
    )


def _resolve_approved_plan(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply RIS art. 7.8 and bind the plan's distribution for the tax year."""
    plan = asset_revision.amortization.approved_plan
    if plan is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError("an approved-plan election requires its plan")
    if plan.submitted_on > date(parameters.tax_year, 12, 31):
        raise ActividadAssetUnsupportedError(
            "an approved plan takes effect only in tax periods ending after its submission (RIS art. 7.8)",
        )
    annual_amount = plan.amount_for(parameters.tax_year)
    if annual_amount is None:
        raise ActividadAssetUnsupportedError("the approved plan distributes no amortization to this tax year")
    return _Resolution(
        method_facts={"plan_annual_amount": annual_amount, "plan_total": plan.total},
        references=(f"approved-plan:{plan.approval_reference}",),
    )


def _resolve_useful_life(asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS art. 12.2: a definite-life intangible amortizes over that life."""
    useful_life = asset_revision.amortization.useful_life
    if useful_life is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError("a definite-life election requires its useful-life evidence")
    if useful_life.ends_on <= asset_revision.in_service_date:
        raise ActividadAssetValidationError("a definite useful life must end after the asset enters service")
    return _Resolution(
        method_facts={"useful_life_ends_on": useful_life.ends_on},
        references=(f"useful-life-evidence:{useful_life.evidence_reference}",),
    )


def _resolve_twentieth_limit(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply the LIS art. 12.2 one-twentieth ceiling to its two intangible cases."""
    if asset_revision.amortization.small_enterprise is not None:
        raise ActividadAssetUnsupportedError(_INDEFINITE_ACCELERATION_REFUSAL)
    parameter_id = (
        _GOODWILL_RATE_ID
        if asset_revision.amortization.method is AmortizationMethod.GOODWILL
        else _INDEFINITE_LIFE_RATE_ID
    )
    rate = parameters.value(parameter_id) / Decimal("100")
    return _Resolution(method_facts={"annual_rate": rate}, references=(parameters.reference(parameter_id),))


def _resolve_low_value(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Resolve the LIS art. 12.3.e EUR 300 / EUR 25,000 branch for a new element."""
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError("low-value free depreciation applies only to new elements")
    election = asset_revision.amortization.low_value
    if election is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError("low-value free depreciation requires explicit election evidence")
    return _Resolution(
        method_facts={
            "free_depreciation_unit_threshold": parameters.value(_LOW_VALUE_THRESHOLD_ID),
            "free_depreciation_annual_cap": parameters.value(_LOW_VALUE_ANNUAL_CAP_ID),
            "low_value": election,
        },
        references=(parameters.reference(_LOW_VALUE_THRESHOLD_ID), parameters.reference(_LOW_VALUE_ANNUAL_CAP_ID)),
    )


def _resolve_research_development_free(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS art. 12.3.b/c: R&D elements other than buildings amortize freely."""
    class_key = asset_revision.amortization.authority_class_key
    references: tuple[str, ...] = ()
    if asset_revision.asset_kind is AssetKind.MATERIAL:
        if class_key is None:
            raise ActividadAssetIncompleteError("material R&D free depreciation requires a table class")
        if _class_flag(parameters, _BUILDING_CLASS_ID, class_key):
            raise ActividadAssetUnsupportedError("R&D free depreciation excludes buildings (LIS art. 12.3.b)")
        references = (parameters.reference(_BUILDING_CLASS_ID, class_key),)
    return _Resolution(method_facts={}, references=references)


def _resolve_research_development_building(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
) -> _Resolution:
    """Apply LIS art. 12.3.b: an R&D building amortizes linearly over its period."""
    class_key = asset_revision.amortization.authority_class_key
    if class_key is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError("an R&D building election requires its table class")
    if not _class_flag(parameters, _BUILDING_CLASS_ID, class_key):
        raise ActividadAssetValidationError("the R&D building method requires a building table class")
    period = parameters.value(_RND_BUILDING_PERIOD_ID)
    return _Resolution(
        method_facts={"annual_rate": Decimal("1") / period},
        references=(parameters.reference(_BUILDING_CLASS_ID, class_key), parameters.reference(_RND_BUILDING_PERIOD_ID)),
    )


def _resolve_charging_infrastructure(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS DA 18a.2: new charging points entering service in the enrolled periods."""
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError("charging-infrastructure free depreciation applies only to new elements")
    first_year = parameters.value(_CHARGING_FIRST_YEAR_ID)
    last_year = parameters.value(_CHARGING_LAST_YEAR_ID)
    if not first_year <= Decimal(asset_revision.in_service_date.year) <= last_year:
        raise ActividadAssetUnsupportedError(
            "charging infrastructure must enter service in a tax period LIS DA 18a.2 enrols",
        )
    return _Resolution(
        method_facts={},
        references=(parameters.reference(_CHARGING_FIRST_YEAR_ID), parameters.reference(_CHARGING_LAST_YEAR_ID)),
    )


__all__ = ["resolve_activity_asset_schedule_authority"]
