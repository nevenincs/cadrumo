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

from ....core.money.rounding import round_to_cents
from ...renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    RenewableInstallationPurpose,
    SmallEnterpriseEvidence,
)
from ...renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
    VehicleAffectationRecovery,
)
from ...renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...renta.actividad_asset.schedule import ScheduleAuthority, add_fractional_years, add_years
from ...renta.actividad_asset.vehicle_affectation import require_vehicle_affected
from ...renta.actividad_asset.workforce import job_creation_increase, renewable_workforce_maintained
from ...user_profile.plantilla_media import PlantillaMediaYear
from .formula_runtime_ops import resolve_dated_value, resolve_keyed_bracket
from .schema import ModeloRevision
from .schema_base import DateAxis, ThresholdComparison
from .schema_formula import ParameterDefinition

_PREFIX = "renta-actividad-inmovilizado-amortizacion"
_COEFFICIENT_IDS: dict[DirectEstimationRegime, str] = {
    DirectEstimationRegime.NORMAL: f"{_PREFIX}-normal-coeficiente-lineal-maximo",
    DirectEstimationRegime.SIMPLIFIED: f"{_PREFIX}-simplificada-coeficiente-lineal-maximo",
}
_PERIOD_IDS: dict[DirectEstimationRegime, str] = {
    DirectEstimationRegime.NORMAL: f"{_PREFIX}-normal-periodo-maximo-anos",
    DirectEstimationRegime.SIMPLIFIED: f"{_PREFIX}-simplificada-periodo-maximo-anos",
}
_METHOD_ADMISSION_IDS: dict[DirectEstimationRegime, str] = {
    DirectEstimationRegime.NORMAL: f"{_PREFIX}-normal-metodo-admitido",
    DirectEstimationRegime.SIMPLIFIED: f"{_PREFIX}-simplificada-metodo-admitido",
}
_BUILDING_CLASS_ID = f"{_PREFIX}-clase-edificio"
_MATERIAL_CLASS_ID = f"{_PREFIX}-clase-admite-material"
_INTANGIBLE_CLASS_ID = f"{_PREFIX}-clase-admite-intangible"
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
_ERD_INDEFINITE_MULTIPLIER_ID = f"{_PREFIX}-erd-intangible-indefinido-multiplicador"
_RND_BUILDING_PERIOD_ID = f"{_PREFIX}-idi-edificio-periodo"
_CHARGING_FIRST_YEAR_ID = f"{_PREFIX}-infraestructura-recarga-primer-ejercicio"
_CHARGING_LAST_YEAR_ID = f"{_PREFIX}-infraestructura-recarga-ultimo-ejercicio"
_ELECTRIC_VEHICLE_FIRST_YEAR_ID = f"{_PREFIX}-vehiculo-electrico-primer-ejercicio"
_ELECTRIC_VEHICLE_LAST_YEAR_ID = f"{_PREFIX}-vehiculo-electrico-ultimo-ejercicio"
_RESTRICTED_VEHICLE_CLASS_ID = f"{_PREFIX}-clase-vehiculo-restringido"
_EMPLOYMENT_INVESTMENT_PER_UNIT_ID = f"{_PREFIX}-erd-empleo-inversion-por-unidad-plantilla"
_RENEWABLE_INVESTMENT_CAP_ID = f"{_PREFIX}-renovables-inversion-maxima"
_RENEWABLE_FIRST_YEAR_ID = f"{_PREFIX}-renovables-primer-ejercicio"
_RENEWABLE_LAST_YEAR_ID = f"{_PREFIX}-renovables-ultimo-ejercicio"
_RENEWABLE_AVAILABILITY_ID = f"{_PREFIX}-renovables-puesta-a-disposicion-admitida"
_INDEFINITE_LIFE_RATE_ID = "renta-actividad-inmovilizado-intangible-vida-util-no-estimable-limite-anual"
_GOODWILL_RATE_ID = "renta-actividad-fondo-comercio-amortizacion-limite-anual"
_LOW_VALUE_THRESHOLD_ID = "renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-umbral-unitario"
_LOW_VALUE_ANNUAL_CAP_ID = "renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-limite-anual"

ACTIVITY_ASSET_PARAMETER_IDS: frozenset[str] = frozenset(
    {
        *_COEFFICIENT_IDS.values(),
        *_PERIOD_IDS.values(),
        *_METHOD_ADMISSION_IDS.values(),
        _BUILDING_CLASS_ID,
        _MATERIAL_CLASS_ID,
        _INTANGIBLE_CLASS_ID,
        _FURNITURE_CLASS_ID,
        _WEIGHTING_ID,
        _MEDIUM_PERIOD_ID,
        _LONG_PERIOD_ID,
        _MINIMUM_PERCENTAGE_ID,
        _USED_MULTIPLIER_ID,
        _USED_BUILDING_AGE_ID,
        _SHIFT_HOURS_ID,
        _ERD_TURNOVER_ID,
        _ERD_MULTIPLIER_ID,
        _ERD_INDEFINITE_MULTIPLIER_ID,
        _RND_BUILDING_PERIOD_ID,
        _CHARGING_FIRST_YEAR_ID,
        _CHARGING_LAST_YEAR_ID,
        _ELECTRIC_VEHICLE_FIRST_YEAR_ID,
        _ELECTRIC_VEHICLE_LAST_YEAR_ID,
        _RESTRICTED_VEHICLE_CLASS_ID,
        _EMPLOYMENT_INVESTMENT_PER_UNIT_ID,
        _RENEWABLE_INVESTMENT_CAP_ID,
        _RENEWABLE_FIRST_YEAR_ID,
        _RENEWABLE_LAST_YEAR_ID,
        _RENEWABLE_AVAILABILITY_ID,
        _INDEFINITE_LIFE_RATE_ID,
        _GOODWILL_RATE_ID,
        _LOW_VALUE_THRESHOLD_ID,
        _LOW_VALUE_ANNUAL_CAP_ID,
    },
)
"""Every Modelo 100 parameter this resolver may read, and the only ones it can.

The resolver reads parameters outside any formula, so this set is how the
registry's orphan check knows they are consumed; reading an id outside it
refuses, so the set cannot fall behind the code.
"""

_REFUSED_METHODS: dict[AmortizationMethod, str] = {
    AmortizationMethod.JUSTIFIED_AMOUNT: (
        "LIS art. 12.1.e admits an amount the taxpayer justifies, but no registry authority can validate that "
        "justification, and an unvalidated caller amount cannot become a filing-grade charge"
    ),
    AmortizationMethod.ENTITY_REGIME_FREE: (
        "LIS art. 12.3.a and 12.3.d apply to sociedades laborales and explotaciones asociativas prioritarias, "
        "which are entities rather than individual taxpayers"
    ),
}
_SIMPLIFIED_INTANGIBLE_TABLE_METHOD_REFUSAL = (
    "is not admitted for intangible assets in the simplified modality because the official sources do not "
    "settle which table it weights: RIRPF art. 30.1a restricts only material assets to the simplified linear "
    "table; the simplified table (Orden of 27 March 1998) lists information systems and programs at 26% over "
    "10 years; RIS arts. 5.1 and 6.1 derive the constant percentage and the digit period from the LIS art. "
    "12.1.a table (33% over 6 years); and the AEAT 2025 manual's simplified-modality section and its "
    "normal-modality method section give no simplified intangible example"
)
_UNDETERMINED_ADMISSIONS: dict[tuple[DirectEstimationRegime, AssetKind, AmortizationMethod], str] = {
    (DirectEstimationRegime.SIMPLIFIED, AssetKind.INTANGIBLE, AmortizationMethod.CONSTANT_PERCENTAGE): (
        _SIMPLIFIED_INTANGIBLE_TABLE_METHOD_REFUSAL
    ),
    (DirectEstimationRegime.SIMPLIFIED, AssetKind.INTANGIBLE, AmortizationMethod.SUM_OF_DIGITS): (
        _SIMPLIFIED_INTANGIBLE_TABLE_METHOD_REFUSAL
    ),
}


@dataclass(frozen=True, slots=True)
class _Parameters:
    by_id: dict[str, ParameterDefinition]
    revision_id: str
    tax_year: int

    def require(self, parameter_id: str) -> ParameterDefinition:
        if parameter_id not in ACTIVITY_ASSET_PARAMETER_IDS:
            raise ActividadAssetValidationError(
                f"activity-asset parameter {parameter_id!r} is not in the resolver's declared read set",
            )
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

    def on_date(self, parameter_id: str, axis: DateAxis, on: date) -> Decimal:
        """Resolve a value keyed to an event date rather than to the filing period."""
        try:
            resolved = resolve_dated_value(self.require(parameter_id), {axis.value: on})
        except ActividadAssetUnsupportedError:
            raise
        except Exception as exc:
            raise ActividadAssetUnsupportedError(
                f"activity-asset authority parameter {parameter_id!r} is not resolvable for {axis.value} {on}",
            ) from exc
        return resolved.value

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
    workforce: tuple[PlantillaMediaYear, ...],
) -> ScheduleAuthority:
    """Validate one revision's election and resolve its tax-year authority.

    ``workforce`` is the taxpayer profile's declared average workforce per
    calendar year; only the workforce-conditioned incentives read it, and an
    undeclared year they need refuses rather than counting as zero.
    """
    if modelo_revision.id != str(tax_year):
        raise ActividadAssetUnsupportedError(
            f"Modelo 100 revision {modelo_revision.id} does not govern tax year {tax_year}",
        )
    election = asset_revision.amortization
    refusal = _REFUSED_METHODS.get(election.method)
    if refusal is not None:
        raise ActividadAssetUnsupportedError(refusal)
    parameters = _Parameters(
        by_id={parameter.id: parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    admission_reference = _require_method_admitted(parameters, asset_revision)
    vehicle_references = _require_vehicle_affectation(parameters, asset_revision)
    resolution = _resolve_method(parameters, asset_revision, workforce)
    return ScheduleAuthority.model_validate(
        {
            "tax_year": tax_year,
            "asset_kind": asset_revision.asset_kind,
            "method": election.method,
            "election_fingerprint": election.fingerprint,
            "authority_generation": authority_generation,
            "source_reference": ";".join((admission_reference, *vehicle_references, *resolution.references)),
            **resolution.method_facts,
        },
    )


def _require_method_admitted(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> str:
    election = asset_revision.amortization
    parameter_id = _METHOD_ADMISSION_IDS[election.regime]
    key = f"{asset_revision.asset_kind.value}:{election.method.value}"
    admitted = parameters.keyed(parameter_id, key)
    undetermined = _UNDETERMINED_ADMISSIONS.get((election.regime, asset_revision.asset_kind, election.method))
    if admitted is None and undetermined is not None:
        raise ActividadAssetUnsupportedError(f"{election.method.value} {undetermined}")
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


def _resolve_method(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    workforce: tuple[PlantillaMediaYear, ...],
) -> _Resolution:
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
    if method is AmortizationMethod.ELECTRIC_VEHICLE_FREE:
        return _resolve_electric_vehicle(parameters, asset_revision)
    if method is AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE:
        return _resolve_employment_free(parameters, asset_revision, workforce)
    if method is AmortizationMethod.RENEWABLE_SELF_CONSUMPTION_FREE:
        return _resolve_renewable_free(parameters, asset_revision, workforce)
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
    kind_reference = _require_class_matches_kind(parameters, class_key, asset_revision.asset_kind)
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
        references=(
            parameters.reference(coefficient_id, class_key),
            parameters.reference(period_id, class_key),
            kind_reference,
        ),
    )


def _require_class_matches_kind(parameters: _Parameters, class_key: str, asset_kind: AssetKind) -> str:
    """Refuse a table class the registry does not admit for the asset's kind."""
    parameter_id = _INTANGIBLE_CLASS_ID if asset_kind is AssetKind.INTANGIBLE else _MATERIAL_CLASS_ID
    if not _class_flag(parameters, parameter_id, class_key):
        raise ActividadAssetUnsupportedError(
            f"table class {class_key!r} does not classify {asset_kind.value} assets",
        )
    return parameters.reference(parameter_id, class_key)


def _class_flag(parameters: _Parameters, parameter_id: str, class_key: str) -> bool:
    flag = parameters.keyed(parameter_id, class_key)
    if flag is None:
        raise ActividadAssetUnsupportedError(f"table class {class_key!r} has no enrolled group classification")
    if flag not in {Decimal("0"), Decimal("1")}:
        raise ActividadAssetValidationError(f"group classification of {class_key!r} is not a flag")
    return flag == Decimal("1")


def _is_used_for_amortization(parameters: _Parameters, asset_revision: ActivityAssetRevision, class_key: str) -> bool:
    """Apply RIS art. 4.3: a building under the minimum age is not a used asset.

    Callers ask only where a used-asset multiplier is enrolled, so a used
    building elsewhere never has to evidence its construction date.
    """
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
    used_key = f"{election.regime.value}:{asset_revision.asset_kind.value}"
    used_multiplier = parameters.keyed(_USED_MULTIPLIER_ID, used_key)
    if used_multiplier is not None and _is_used_for_amortization(parameters, asset_revision, bounds.class_key):
        if election.shift_hours_per_day is not None:
            raise ActividadAssetUnsupportedError(
                "RIS art. 4 does not state how the multi-shift and used-asset coefficients combine",
            )
        maximum *= used_multiplier
        references.append(parameters.reference(_USED_MULTIPLIER_ID, used_key))
    if election.small_enterprise is not None:
        maximum *= _small_enterprise_multiplier(parameters, asset_revision, references)
    if election.shift_hours_per_day is not None:
        shift_hours = parameters.keyed(_SHIFT_HOURS_ID, election.regime.value)
        if shift_hours is None:
            raise ActividadAssetUnsupportedError(
                f"the RIS art. 4.2 multi-shift coefficient is not enrolled for the {election.regime.value} modality",
            )
        if election.shift_hours_per_day <= shift_hours:
            raise ActividadAssetValidationError("a multi-shift coefficient requires more than one normal shift a day")
        maximum = bounds.minimum + (bounds.maximum - bounds.minimum) * election.shift_hours_per_day / shift_hours
        references.append(parameters.reference(_SHIFT_HOURS_ID, election.regime.value))
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
    references.extend(
        (_require_reduced_size(parameters, asset_revision, evidence), parameters.reference(_ERD_MULTIPLIER_ID)),
    )
    return parameters.value(_ERD_MULTIPLIER_ID)


def _require_reduced_size(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    evidence: SmallEnterpriseEvidence,
) -> str:
    """Refuse unless the asset was made available in a LIS art. 101 period; return the threshold reference."""
    if evidence.made_available_on > asset_revision.in_service_date:
        raise ActividadAssetValidationError("an asset cannot enter service before it is made available")
    threshold, comparison = parameters.scalar(_ERD_TURNOVER_ID)
    if _reaches(evidence.prior_period_net_turnover, threshold, comparison):
        raise ActividadAssetUnsupportedError(
            "prior-period net turnover reaches the reduced-size threshold (LIS art. 101.1)",
        )
    return parameters.reference(_ERD_TURNOVER_ID)


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
    """Apply the LIS art. 12.2 one-twentieth ceiling to its two intangible cases.

    An element acquired in a reduced-size period deducts the LIS art. 103.5
    multiple of that amount.  Unlike art. 103.1, that paragraph does not
    require the element to be new.
    """
    election = asset_revision.amortization
    parameter_id = _GOODWILL_RATE_ID if election.method is AmortizationMethod.GOODWILL else _INDEFINITE_LIFE_RATE_ID
    rate = parameters.value(parameter_id) / Decimal("100")
    references = [parameters.reference(parameter_id)]
    evidence = election.small_enterprise
    if evidence is not None:
        references.append(_require_reduced_size(parameters, asset_revision, evidence))
        rate *= parameters.value(_ERD_INDEFINITE_MULTIPLIER_ID)
        references.append(parameters.reference(_ERD_INDEFINITE_MULTIPLIER_ID))
    return _Resolution(method_facts={"annual_rate": rate}, references=tuple(references))


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


def _require_vehicle_affectation(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> tuple[str, ...]:
    """Charge a vehicle only on a declaration that proves it affected (RIRPF art. 22).

    A material asset in a class that can hold a restricted vehicle, and every
    electric-vehicle election, requires the declaration; a declaration given
    elsewhere is still held to the same test.
    """
    election = asset_revision.amortization
    class_key = election.authority_class_key
    affectation = asset_revision.vehicle_affectation
    references: tuple[str, ...] = ()
    restricted = False
    if class_key is not None and asset_revision.asset_kind is AssetKind.MATERIAL:
        restricted = _class_flag(parameters, _RESTRICTED_VEHICLE_CLASS_ID, class_key)
        references = (parameters.reference(_RESTRICTED_VEHICLE_CLASS_ID, class_key),)
    if affectation is None:
        if restricted and class_key is not None:
            raise ActividadAssetIncompleteError(
                f"activity asset {asset_revision.asset_id!r} is in table class {class_key!r}, which can hold a "
                "vehicle RIRPF art. 22.4 restricts, so it requires a vehicle affectation declaration",
                vehicle_affectation_recovery=VehicleAffectationRecovery(
                    asset_id=asset_revision.asset_id,
                    revision_id=asset_revision.revision_id,
                    class_key=class_key,
                ),
            )
        if election.method is AmortizationMethod.ELECTRIC_VEHICLE_FREE:
            raise ActividadAssetIncompleteError("electric-vehicle free depreciation requires a vehicle declaration")
        return references
    require_vehicle_affected(affectation)
    return references


def _resolve_electric_vehicle(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS DA 18a.1: new electric vehicles entering service in the enrolled periods."""
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError("electric-vehicle free depreciation applies only to new vehicles")
    affectation = asset_revision.vehicle_affectation
    if affectation is None or affectation.electric_propulsion is None:
        raise ActividadAssetIncompleteError(
            "electric-vehicle free depreciation requires the vehicle's annex II propulsion type",
        )
    first_year = parameters.value(_ELECTRIC_VEHICLE_FIRST_YEAR_ID)
    last_year = parameters.value(_ELECTRIC_VEHICLE_LAST_YEAR_ID)
    if not first_year <= Decimal(asset_revision.in_service_date.year) <= last_year:
        raise ActividadAssetUnsupportedError("the vehicle must enter service in a tax period LIS DA 18a.1 enrols")
    return _Resolution(
        method_facts={},
        references=(
            parameters.reference(_ELECTRIC_VEHICLE_FIRST_YEAR_ID),
            parameters.reference(_ELECTRIC_VEHICLE_LAST_YEAR_ID),
        ),
    )


def _workforce_references(years: tuple[PlantillaMediaYear, ...]) -> tuple[str, ...]:
    """Name each declared year a workforce test used, with its observed or committed state.

    A committed year is a forecast the taxpayer must regularise if it is not
    met (LIS art. 102.4, DA 17a.7), so its state travels with the charge.
    """
    return tuple(f"taxpayer-profile:irpf.plantilla_media:{item.year}:{item.state.value}" for item in years)


def _resolve_employment_free(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    workforce: tuple[PlantillaMediaYear, ...],
) -> _Resolution:
    """Apply LIS art. 102.1: new elements of a reduced-size period, capped by the workforce increase.

    The investment that may benefit is the enrolled amount per unit of the
    average-workforce increase, the increase calculated with two decimals.
    """
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError(
            "job-creating free depreciation applies only to new elements (LIS art. 102.1)"
        )
    evidence = asset_revision.amortization.small_enterprise
    if evidence is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError("job-creating free depreciation requires its reduced-size evidence")
    turnover_reference = _require_reduced_size(parameters, asset_revision, evidence)
    increase = job_creation_increase(workforce, entry_year=asset_revision.in_service_date.year)
    per_unit = parameters.value(_EMPLOYMENT_INVESTMENT_PER_UNIT_ID)
    return _Resolution(
        method_facts={"free_depreciation_investment_cap": round_to_cents(per_unit * increase.increase)},
        references=(
            turnover_reference,
            parameters.reference(_EMPLOYMENT_INVESTMENT_PER_UNIT_ID),
            *_workforce_references(increase.years),
        ),
    )


def _resolve_renewable_free(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    workforce: tuple[PlantillaMediaYear, ...],
) -> _Resolution:
    """Apply LIS DA 17a: a renewable installation charges freely only in the period it enters service.

    An amount not taken in that period cannot be taken freely later, so the
    entry year must be the tax year as well as a year the period enrols.
    """
    election = asset_revision.amortization
    evidence = election.renewable_self_consumption
    class_key = election.authority_class_key
    if evidence is None or class_key is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError("renewable free depreciation requires its table class and evidence")
    if _class_flag(parameters, _BUILDING_CLASS_ID, class_key):
        raise ActividadAssetUnsupportedError("buildings cannot use renewable free depreciation (LIS DA 17a.1)")
    if evidence.purpose is RenewableInstallationPurpose.THERMAL_OWN_USE and not evidence.replaces_fossil_installation:
        raise ActividadAssetUnsupportedError(
            "a thermal installation qualifies only when it replaces one using fossil energy (LIS DA 17a.1)",
        )
    if evidence.required_by_building_code:
        raise ActividadAssetUnsupportedError(
            "an installation the Codigo Tecnico de la Edificacion makes mandatory qualifies only for the cost "
            "share above the mandatory power (LIS DA 17a.5), and charging that share is not supported",
        )
    if evidence.made_available_on > asset_revision.in_service_date:
        raise ActividadAssetValidationError("an asset cannot enter service before it is made available")
    if parameters.on_date(_RENEWABLE_AVAILABILITY_ID, DateAxis.TRANSACTION_DATE, evidence.made_available_on) != Decimal(
        "1",
    ):
        raise ActividadAssetUnsupportedError(
            "the installation was made available before the date LIS DA 17a.1 admits installations from",
        )
    entry_year = asset_revision.in_service_date.year
    first_year = parameters.value(_RENEWABLE_FIRST_YEAR_ID)
    last_year = parameters.value(_RENEWABLE_LAST_YEAR_ID)
    if not first_year <= Decimal(entry_year) <= last_year:
        raise ActividadAssetUnsupportedError("the installation must enter service in a year LIS DA 17a.1 enrols")
    if entry_year != parameters.tax_year:
        raise ActividadAssetUnsupportedError(
            "renewable free depreciation applies only in the tax period the installation enters service "
            "(LIS DA 17a.1); an amount not taken then cannot be taken freely later",
        )
    maintenance = renewable_workforce_maintained(workforce, entry_year=entry_year)
    return _Resolution(
        method_facts={"free_depreciation_investment_cap": parameters.value(_RENEWABLE_INVESTMENT_CAP_ID)},
        references=(
            parameters.reference(_BUILDING_CLASS_ID, class_key),
            parameters.reference(_RENEWABLE_AVAILABILITY_ID),
            parameters.reference(_RENEWABLE_FIRST_YEAR_ID),
            parameters.reference(_RENEWABLE_LAST_YEAR_ID),
            parameters.reference(_RENEWABLE_INVESTMENT_CAP_ID),
            f"renewable-documentation:{evidence.documentation_kind.value}:{evidence.documentation_reference}",
            *_workforce_references(maintenance.years),
        ),
    )


__all__ = ["ACTIVITY_ASSET_PARAMETER_IDS", "resolve_activity_asset_schedule_authority"]
