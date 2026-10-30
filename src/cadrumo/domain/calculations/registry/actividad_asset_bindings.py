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
from collections.abc import Callable, Mapping
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
    RenewableSelfConsumptionEvidence,
    SmallEnterpriseEvidence,
)
from ...renta.actividad_asset.errors import (
    ActividadAssetAcceleratedDa18DepreciationError,
    ActividadAssetError,
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
from .errors import RegistryValidationError
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .formula_runtime_ops import resolve_dated_value, resolve_keyed_bracket
from .governed_fact_scope import GovernedFactSource
from .schema import ModeloRevision
from .schema_base import DateAxis, ThresholdComparison
from .schema_formula import ParameterDefinition
from .schema_references import LegalReference, governed_period_span

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

_REFUSED_METHOD_LOCALE_KEYS: dict[AmortizationMethod, str] = {
    AmortizationMethod.JUSTIFIED_AMOUNT: "ledger.actividad_asset.errors.justified_amount_unvalidated",
    AmortizationMethod.ENTITY_REGIME_FREE: "ledger.actividad_asset.errors.entity_regime_not_individual",
}
_SIMPLIFIED_INTANGIBLE_TABLE_METHOD_LOCALE_KEY = "ledger.actividad_asset.errors.simplified_intangible_table_method"
_UNDETERMINED_ADMISSION_LOCALE_KEYS: dict[tuple[DirectEstimationRegime, AssetKind, AmortizationMethod], str] = {
    (DirectEstimationRegime.SIMPLIFIED, AssetKind.INTANGIBLE, AmortizationMethod.CONSTANT_PERCENTAGE): (
        _SIMPLIFIED_INTANGIBLE_TABLE_METHOD_LOCALE_KEY
    ),
    (DirectEstimationRegime.SIMPLIFIED, AssetKind.INTANGIBLE, AmortizationMethod.SUM_OF_DIGITS): (
        _SIMPLIFIED_INTANGIBLE_TABLE_METHOD_LOCALE_KEY
    ),
}
_ELECTRIC_MOBILITY_PROVISION_ID = "ley-27-2014:da-18"
_ELECTRIC_MOBILITY_METHODS: frozenset[AmortizationMethod] = frozenset(
    {AmortizationMethod.ELECTRIC_VEHICLE_FREE, AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE},
)
"""The free-depreciation methods LIS DA 18 grants new electric vehicles and charging points."""


@dataclass(frozen=True, slots=True)
class _Parameters:
    by_id: dict[str, ParameterDefinition]
    revision_id: str
    tax_year: int

    def require(self, parameter_id: str) -> ParameterDefinition:
        if parameter_id not in ACTIVITY_ASSET_PARAMETER_IDS:
            raise ActividadAssetValidationError(
                context={"parameter_id": parameter_id},
                translated_message="ledger.actividad_asset.errors.parameter_not_declared",
            )
        parameter = self.by_id.get(parameter_id)
        if parameter is None:
            raise ActividadAssetUnsupportedError(
                context={"parameter_id": parameter_id, "revision_id": self.revision_id},
                translated_message="ledger.actividad_asset.errors.parameter_absent",
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
                context={"parameter_id": parameter_id, "tax_year": self.tax_year},
                translated_message="ledger.actividad_asset.errors.parameter_not_resolvable_for_year",
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
                context={"parameter_id": parameter_id, "axis": axis.value, "on_date": on.isoformat()},
                translated_message="ledger.actividad_asset.errors.parameter_not_resolvable_for_date",
            ) from exc
        return resolved.value

    def reference(self, parameter_id: str, key: str | None = None) -> str:
        suffix = f"{_PARAMETER_KEY_SEPARATOR}{key}" if key is not None else ""
        return f"{_parameter_reference_prefix(self.revision_id)}{parameter_id}{suffix}"


_PARAMETER_KEY_SEPARATOR = ":key:"


def _parameter_reference_prefix(revision_id: str) -> str:
    return f"modelo-100:{revision_id}:parameter:"


def activity_asset_parameter_of_reference(reference: str, *, revision_id: str) -> str | None:
    """Name the registry parameter one ``source_reference`` entry of a schedule authority cites.

    Returns:
        The parameter id, or ``None`` for an entry that is not a parameter of that
        revision, such as the approved-plan or useful-life evidence an operator supplied.
    """
    prefix = _parameter_reference_prefix(revision_id)
    if not reference.startswith(prefix):
        return None
    return reference[len(prefix) :].partition(_PARAMETER_KEY_SEPARATOR)[0]


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
    legal_reference: Callable[[str], LegalReference],
) -> ScheduleAuthority:
    """Validate one revision's election and resolve its tax-year authority.

    ``workforce`` is the taxpayer profile's declared average workforce per
    calendar year; only the workforce-conditioned incentives read it, and an
    undeclared year they need refuses rather than counting as zero.

    ``legal_reference`` reads one published legal-catalogue declaration.  Only
    an electric-mobility election the edition does not enrol reads it, to tell
    a tax period LIS DA 18 governs from one it does not.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    if modelo_revision.valid_from.year > tax_year:
        raise ActividadAssetUnsupportedError(
            context={"revision_id": modelo_revision.id, "tax_year": tax_year},
            translated_message="ledger.actividad_asset.errors.revision_begins_after_tax_year",
        )
    election = asset_revision.amortization
    refusal = _REFUSED_METHOD_LOCALE_KEYS.get(election.method)
    if refusal is not None:
        raise ActividadAssetUnsupportedError(translated_message=refusal)
    parameters = _Parameters(
        by_id={parameter.id: parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    admission_reference = _require_method_admitted(parameters, asset_revision, legal_reference)
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


@dataclass(frozen=True, slots=True)
class ActivityAssetDisposalBounds:
    """What the registry supplies for one service year of a baja's reduction of cost.

    A null coefficient means the year has no maximum period, fixed percentage or
    table class, so it counts only what was deducted.
    """

    minimum_coefficient: Decimal | None = None
    maximum_coefficient: Decimal | None = None
    useful_life_ends_on: date | None = None


def resolve_activity_asset_disposal_bounds(
    modelo_revision: ModeloRevision,
    *,
    tax_year: int,
    asset_revision: ActivityAssetRevision,
) -> ActivityAssetDisposalBounds:
    """Read one year's minimum and maximum coefficient for a baja, without judging the election.

    A baja looks back over years the element's election may no longer resolve in,
    so what the edition cannot supply stays absent rather than refused.
    """
    parameters = _Parameters(
        by_id={parameter.id: parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    election = asset_revision.amortization
    try:
        if election.method in {AmortizationMethod.GOODWILL, AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE}:
            parameter_id = (
                _GOODWILL_RATE_ID if election.method is AmortizationMethod.GOODWILL else _INDEFINITE_LIFE_RATE_ID
            )
            rate = parameters.value(parameter_id) / Decimal("100")
            return ActivityAssetDisposalBounds(minimum_coefficient=rate, maximum_coefficient=rate)
        if election.method is AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING:
            rate = Decimal("1") / parameters.value(_RND_BUILDING_PERIOD_ID)
            return ActivityAssetDisposalBounds(minimum_coefficient=rate, maximum_coefficient=rate)
        if election.method is AmortizationMethod.INTANGIBLE_USEFUL_LIFE:
            useful_life = election.useful_life
            return ActivityAssetDisposalBounds(useful_life_ends_on=None if useful_life is None else useful_life.ends_on)
        if election.authority_class_key is None:
            return ActivityAssetDisposalBounds()
        bounds = _table_bounds(parameters, asset_revision)
    except ActividadAssetError:
        return ActivityAssetDisposalBounds()
    return ActivityAssetDisposalBounds(minimum_coefficient=bounds.minimum, maximum_coefficient=bounds.maximum)


def _require_method_admitted(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    legal_reference: Callable[[str], LegalReference],
) -> str:
    election = asset_revision.amortization
    parameter_id = _METHOD_ADMISSION_IDS[election.regime]
    key = f"{asset_revision.asset_kind.value}:{election.method.value}"
    admitted = parameters.keyed(parameter_id, key)
    undetermined = _UNDETERMINED_ADMISSION_LOCALE_KEYS.get(
        (election.regime, asset_revision.asset_kind, election.method)
    )
    if admitted is None and undetermined is not None:
        raise ActividadAssetUnsupportedError(
            context={"method": election.method.value},
            translated_message=undetermined,
        )
    if admitted is None:
        _refuse_accelerated_electric_mobility_period(parameters, asset_revision, legal_reference)
        raise ActividadAssetUnsupportedError(
            context={
                "method": election.method.value,
                "asset_kind": asset_revision.asset_kind.value,
                "regime": election.regime.value,
            },
            translated_message="ledger.actividad_asset.errors.method_not_enrolled_for_kind",
        )
    if admitted == Decimal("0"):
        legal = ", ".join(parameters.require(parameter_id).legal_refs)
        raise ActividadAssetUnsupportedError(
            context={
                "method": election.method.value,
                "asset_kind": asset_revision.asset_kind.value,
                "regime": election.regime.value,
                "legal": legal,
            },
            translated_message="ledger.actividad_asset.errors.method_excluded_by_law",
        )
    if admitted != Decimal("1"):
        raise ActividadAssetValidationError(
            context={"admission_key": key},
            translated_message="ledger.actividad_asset.errors.method_admission_invalid",
        )
    return parameters.reference(parameter_id, key)


def _refuse_accelerated_electric_mobility_period(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    legal_reference: Callable[[str], LegalReference],
) -> None:
    """Refuse an unenrolled electric-mobility election in a period LIS DA 18 governs.

    LIS DA 18 granted new electric vehicles and charging points accelerated
    depreciation, at twice the maximum linear coefficient, before it granted
    free depreciation.  An edition that enrols no free method for a period
    the provision governs therefore leaves that period under the accelerated
    regime, which stays outside the method set.  A period before the
    provision governs keeps the generic refusal, because no DA 18 regime
    reaches it; vehicles and charging installations are material assets, so
    an intangible election keeps it too.
    """
    election = asset_revision.amortization
    if election.method not in _ELECTRIC_MOBILITY_METHODS or asset_revision.asset_kind is not AssetKind.MATERIAL:
        return
    provision = legal_reference(_ELECTRIC_MOBILITY_PROVISION_ID)
    governs_from, governs_to = governed_period_span(provision)
    period_end = date(parameters.tax_year, 12, 31)
    if governs_from <= period_end and (governs_to is None or period_end <= governs_to):
        raise _accelerated_da18_refusal(asset_revision, tax_year=parameters.tax_year, provision_id=provision.id)


def _accelerated_da18_refusal(
    asset_revision: ActivityAssetRevision,
    *,
    tax_year: int,
    provision_id: str,
) -> ActividadAssetAcceleratedDa18DepreciationError:
    """Name the LIS DA 18 accelerated regime a claim falls under, which the product does not compute."""
    method = asset_revision.amortization.method.value
    return ActividadAssetAcceleratedDa18DepreciationError(
        translated_message="ledger.actividad_asset.errors.accelerated_da18_depreciation",
        context={
            "asset_id": asset_revision.asset_id,
            "method": method,
            "tax_year": tax_year,
            "legal_reference": provision_id,
        },
    )


def _resolve_method(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    workforce: tuple[PlantillaMediaYear, ...],
) -> _Resolution:
    method = asset_revision.amortization.method
    resolver = _METHOD_RESOLVERS.get(method)
    if resolver is None:
        raise ActividadAssetUnsupportedError(
            context={"method": method.value},
            translated_message="ledger.actividad_asset.errors.method_without_resolver",
        )
    return resolver(parameters, asset_revision, workforce)


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
        raise ActividadAssetIncompleteError(
            context={"method": election.method.value},
            translated_message="ledger.actividad_asset.errors.table_class_required",
        )
    kind_reference = _require_class_matches_kind(parameters, class_key, asset_revision.asset_kind)
    coefficient_id = _COEFFICIENT_IDS[election.regime]
    period_id = _PERIOD_IDS[election.regime]
    maximum_percent = parameters.keyed(coefficient_id, class_key)
    period_years = parameters.keyed(period_id, class_key)
    if maximum_percent is None or period_years is None:
        raise ActividadAssetUnsupportedError(
            context={"class_key": class_key, "regime": election.regime.value},
            translated_message="ledger.actividad_asset.errors.table_class_not_enrolled",
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
            context={"class_key": class_key, "asset_kind": asset_kind.value},
            translated_message="ledger.actividad_asset.errors.table_class_wrong_kind",
        )
    return parameters.reference(parameter_id, class_key)


def _class_flag(parameters: _Parameters, parameter_id: str, class_key: str) -> bool:
    flag = parameters.keyed(parameter_id, class_key)
    if flag is None:
        raise ActividadAssetUnsupportedError(
            context={"class_key": class_key},
            translated_message="ledger.actividad_asset.errors.table_class_without_group_classification",
        )
    if flag not in {Decimal("0"), Decimal("1")}:
        raise ActividadAssetValidationError(
            context={"class_key": class_key},
            translated_message="ledger.actividad_asset.errors.table_class_group_not_a_flag",
        )
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
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.used_building_requires_construction_date"
        )
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
    original_price = election.used_original_price
    if original_price is not None:
        _require_original_price_route(parameters, asset_revision, bounds.class_key, used_multiplier)
    if used_multiplier is not None and _is_used_for_amortization(parameters, asset_revision, bounds.class_key):
        if election.shift_hours_per_day is not None:
            raise ActividadAssetUnsupportedError(
                translated_message="ledger.actividad_asset.errors.multi_shift_with_used_asset_unsupported",
            )
        if original_price is None:
            maximum *= used_multiplier
            references.append(parameters.reference(_USED_MULTIPLIER_ID, used_key))
    if election.small_enterprise is not None:
        maximum *= _small_enterprise_multiplier(parameters, asset_revision, references)
    if election.shift_hours_per_day is not None:
        shift_hours = parameters.keyed(_SHIFT_HOURS_ID, election.regime.value)
        if shift_hours is None:
            raise ActividadAssetUnsupportedError(
                context={"regime": election.regime.value},
                translated_message="ledger.actividad_asset.errors.multi_shift_not_enrolled",
            )
        if election.shift_hours_per_day <= shift_hours:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.multi_shift_requires_extra_shift"
            )
        maximum = bounds.minimum + (bounds.maximum - bounds.minimum) * election.shift_hours_per_day / shift_hours
        references.append(parameters.reference(_SHIFT_HOURS_ID, election.regime.value))
    coefficient = _elected_coefficient(election, minimum=bounds.minimum, maximum=maximum)
    method_facts: dict[str, object] = {
        "annual_rate": min(coefficient, Decimal("1")),
        "maximum_period_ends_on": add_fractional_years(asset_revision.in_service_date, bounds.period_years),
    }
    if original_price is not None:
        method_facts["original_price_basis"] = original_price.original_price * asset_revision.basis.allocation_share()
    return _Resolution(method_facts=method_facts, references=tuple(references))


def _require_original_price_route(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    class_key: str,
    used_multiplier: Decimal | None,
) -> None:
    """Refuse an originating-price election unless RIS art. 4.3 treats the element as used.

    The article's letters b and c apply to an element "adquirido usado" and
    exempt a building under ten years old from being one.  Where the edition
    enrols no used-asset rule for the modality there is no authority to judge
    that by, so the election refuses rather than assuming the article applies.
    """
    election = asset_revision.amortization
    context = {"asset_id": asset_revision.asset_id, "regime": election.regime.value}
    if asset_revision.acquired_condition is not AcquiredCondition.USED:
        raise ActividadAssetUnsupportedError(
            context=context,
            translated_message="ledger.actividad_asset.errors.used_original_price_requires_used_asset",
        )
    if used_multiplier is None:
        raise ActividadAssetUnsupportedError(
            context=context,
            translated_message="ledger.actividad_asset.errors.used_original_price_not_enrolled",
        )
    if not _is_used_for_amortization(parameters, asset_revision, class_key):
        raise ActividadAssetUnsupportedError(
            context=context,
            translated_message="ledger.actividad_asset.errors.used_original_price_requires_used_asset",
        )


def _small_enterprise_multiplier(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    references: list[str],
) -> Decimal:
    """Validate LIS arts. 101 and 103.1 and return the acceleration multiplier."""
    evidence = asset_revision.amortization.small_enterprise
    if evidence is None:  # defensive: callers check presence first
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.reduced_size_evidence_required"
        )
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.reduced_size_acceleration_new_only"
        )
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
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.asset_made_available_after_in_service"
        )
    threshold, comparison = parameters.scalar(_ERD_TURNOVER_ID)
    if _reaches(evidence.prior_period_net_turnover, threshold, comparison):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.reduced_size_turnover_reached"
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
            context={"elected": elected, "minimum": minimum, "maximum": maximum},
            translated_message="ledger.actividad_asset.errors.elected_coefficient_out_of_range",
        )
    return elected


def _require_not_building_or_furniture(parameters: _Parameters, bounds: _TableBounds, provision: str) -> None:
    if _class_flag(parameters, _BUILDING_CLASS_ID, bounds.class_key) or _class_flag(
        parameters,
        _FURNITURE_CLASS_ID,
        bounds.class_key,
    ):
        raise ActividadAssetUnsupportedError(
            context={"provision": provision},
            translated_message="ledger.actividad_asset.errors.method_excludes_buildings_and_furniture",
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
        raise ActividadAssetUnsupportedError(
            context={"band": band},
            translated_message="ledger.actividad_asset.errors.constant_percentage_weighting_not_enrolled",
        )
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
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.sum_of_digits_period_required"
        )
    shortest = math.ceil(Decimal("1") / bounds.maximum)
    longest = bounds.period_years
    if not shortest <= period <= longest:
        raise ActividadAssetValidationError(
            context={"period": period, "shortest": shortest, "longest": longest},
            translated_message="ledger.actividad_asset.errors.sum_of_digits_period_out_of_range",
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
        raise ActividadAssetIncompleteError(translated_message="ledger.actividad_asset.errors.approved_plan_required")
    if plan.submitted_on > date(parameters.tax_year, 12, 31):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.approved_plan_not_yet_effective"
        )
    annual_amount = plan.amount_for(parameters.tax_year)
    if annual_amount is None:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.approved_plan_without_distribution"
        )
    return _Resolution(
        method_facts={"plan_annual_amount": annual_amount, "plan_total": plan.total},
        references=(f"approved-plan:{plan.approval_reference}",),
    )


def _resolve_useful_life(asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS art. 12.2: a definite-life intangible amortizes over that life."""
    useful_life = asset_revision.amortization.useful_life
    if useful_life is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.useful_life_evidence_required"
        )
    if useful_life.ends_on <= asset_revision.in_service_date:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.useful_life_must_end_after_service"
        )
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
        raise ActividadAssetUnsupportedError(translated_message="ledger.actividad_asset.errors.low_value_new_only")
    election = asset_revision.amortization.low_value
    if election is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.low_value_election_required"
        )
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
            raise ActividadAssetIncompleteError(
                translated_message="ledger.actividad_asset.errors.research_development_free_table_class_required"
            )
        if _class_flag(parameters, _BUILDING_CLASS_ID, class_key):
            raise ActividadAssetUnsupportedError(
                translated_message="ledger.actividad_asset.errors.research_development_free_excludes_buildings"
            )
        references = (parameters.reference(_BUILDING_CLASS_ID, class_key),)
    return _Resolution(method_facts={}, references=references)


def _resolve_research_development_building(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
) -> _Resolution:
    """Apply LIS art. 12.3.b: an R&D building amortizes linearly over its period."""
    class_key = asset_revision.amortization.authority_class_key
    if class_key is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.research_development_building_table_class_required"
        )
    if not _class_flag(parameters, _BUILDING_CLASS_ID, class_key):
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.research_development_building_requires_building_class"
        )
    period = parameters.value(_RND_BUILDING_PERIOD_ID)
    return _Resolution(
        method_facts={
            "annual_rate": Decimal("1") / period,
            "maximum_period_ends_on": add_fractional_years(asset_revision.in_service_date, period),
        },
        references=(parameters.reference(_BUILDING_CLASS_ID, class_key), parameters.reference(_RND_BUILDING_PERIOD_ID)),
    )


def _resolve_charging_infrastructure(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS DA 18a.2: new charging points entering service in the enrolled periods."""
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.charging_infrastructure_new_only"
        )
    first_year = parameters.value(_CHARGING_FIRST_YEAR_ID)
    last_year = parameters.value(_CHARGING_LAST_YEAR_ID)
    if not first_year <= Decimal(asset_revision.in_service_date.year) <= last_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.charging_infrastructure_period_not_enrolled"
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
                context={"asset_id": asset_revision.asset_id, "class_key": class_key},
                translated_message="ledger.actividad_asset.errors.vehicle_affectation_required_for_class",
                vehicle_affectation_recovery=VehicleAffectationRecovery(
                    asset_id=asset_revision.asset_id,
                    revision_id=asset_revision.revision_id,
                    class_key=class_key,
                ),
            )
        if election.method is AmortizationMethod.ELECTRIC_VEHICLE_FREE:
            raise ActividadAssetIncompleteError(
                translated_message="ledger.actividad_asset.errors.electric_vehicle_declaration_required"
            )
        return references
    require_vehicle_affected(affectation)
    return references


def _resolve_electric_vehicle(parameters: _Parameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply LIS DA 18a.1: new electric vehicles entering service in the enrolled periods."""
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.electric_vehicle_new_only"
        )
    affectation = asset_revision.vehicle_affectation
    if affectation is None or affectation.electric_propulsion is None:
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.electric_vehicle_propulsion_required"
        )
    first_year = parameters.value(_ELECTRIC_VEHICLE_FIRST_YEAR_ID)
    last_year = parameters.value(_ELECTRIC_VEHICLE_LAST_YEAR_ID)
    if not first_year <= Decimal(asset_revision.in_service_date.year) <= last_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.electric_vehicle_period_not_enrolled"
        )
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
        raise ActividadAssetUnsupportedError(translated_message="ledger.actividad_asset.errors.job_creation_new_only")
    evidence = asset_revision.amortization.small_enterprise
    if evidence is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.job_creation_reduced_size_evidence_required"
        )
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
    evidence, class_key = _renewable_support(asset_revision)
    _validate_renewable_installation(parameters, asset_revision, evidence, class_key)
    entry_year = asset_revision.in_service_date.year
    first_year = parameters.value(_RENEWABLE_FIRST_YEAR_ID)
    last_year = parameters.value(_RENEWABLE_LAST_YEAR_ID)
    if not first_year <= Decimal(entry_year) <= last_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_entry_year_not_enrolled"
        )
    if entry_year != parameters.tax_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_only_in_entry_period"
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


def _renewable_support(
    asset_revision: ActivityAssetRevision,
) -> tuple[RenewableSelfConsumptionEvidence, str]:
    evidence = asset_revision.amortization.renewable_self_consumption
    class_key = asset_revision.amortization.authority_class_key
    if evidence is None or class_key is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.renewable_evidence_required"
        )
    return evidence, class_key


def _validate_renewable_installation(
    parameters: _Parameters,
    asset_revision: ActivityAssetRevision,
    evidence: RenewableSelfConsumptionEvidence,
    class_key: str,
) -> None:
    if _class_flag(parameters, _BUILDING_CLASS_ID, class_key):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_excludes_buildings"
        )
    if evidence.purpose is RenewableInstallationPurpose.THERMAL_OWN_USE and not evidence.replaces_fossil_installation:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_thermal_requires_fossil_replacement"
        )
    if evidence.required_by_building_code:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_mandatory_installation_unsupported"
        )
    if evidence.made_available_on > asset_revision.in_service_date:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.asset_made_available_after_in_service"
        )
    if parameters.on_date(_RENEWABLE_AVAILABILITY_ID, DateAxis.TRANSACTION_DATE, evidence.made_available_on) != Decimal(
        "1",
    ):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_made_available_before_admitted_date"
        )


_MethodResolver = Callable[[_Parameters, ActivityAssetRevision, tuple[PlantillaMediaYear, ...]], _Resolution]
_METHOD_RESOLVERS: dict[AmortizationMethod, _MethodResolver] = {
    AmortizationMethod.LINEAR: lambda parameters, revision, _: _resolve_linear(parameters, revision),
    AmortizationMethod.CONSTANT_PERCENTAGE: lambda parameters, revision, _: _resolve_constant_percentage(
        parameters, revision
    ),
    AmortizationMethod.SUM_OF_DIGITS: lambda parameters, revision, _: _resolve_sum_of_digits(parameters, revision),
    AmortizationMethod.APPROVED_PLAN: lambda parameters, revision, _: _resolve_approved_plan(parameters, revision),
    AmortizationMethod.INTANGIBLE_USEFUL_LIFE: lambda _, revision, __: _resolve_useful_life(revision),
    AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE: lambda parameters, revision, _: _resolve_twentieth_limit(
        parameters, revision
    ),
    AmortizationMethod.GOODWILL: lambda parameters, revision, _: _resolve_twentieth_limit(parameters, revision),
    AmortizationMethod.LOW_VALUE_FREE: lambda parameters, revision, _: _resolve_low_value(parameters, revision),
    AmortizationMethod.RESEARCH_DEVELOPMENT_FREE: lambda parameters, revision, _: _resolve_research_development_free(
        parameters, revision
    ),
    AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING: lambda parameters, revision, _: (
        _resolve_research_development_building(parameters, revision)
    ),
    AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE: lambda parameters, revision, _: _resolve_charging_infrastructure(
        parameters, revision
    ),
    AmortizationMethod.ELECTRIC_VEHICLE_FREE: lambda parameters, revision, _: _resolve_electric_vehicle(
        parameters, revision
    ),
    AmortizationMethod.SMALL_ENTERPRISE_EMPLOYMENT_FREE: lambda parameters, revision, workforce: (
        _resolve_employment_free(parameters, revision, workforce)
    ),
    AmortizationMethod.RENEWABLE_SELF_CONSUMPTION_FREE: lambda parameters, revision, workforce: _resolve_renewable_free(
        parameters, revision, workforce
    ),
}


@dataclass(frozen=True, slots=True)
class ActivityAssetTableGroup:
    """One amortization table class with the corridor RIS art. 4.1 draws from it."""

    class_key: str
    maximum_coefficient: Decimal
    minimum_coefficient: Decimal
    maximum_period_years: Decimal
    class_label: str


@dataclass(frozen=True, slots=True)
class ActivityAssetFormOptions:
    """What one Modelo 100 edition admits for an asset kind, modality and tax year.

    ``class_labels`` names every table class of the modality, not only the
    classes this asset kind admits, because an election keeps its class under a
    method the table does not bound.
    """

    methods: tuple[AmortizationMethod, ...]
    table_groups: tuple[ActivityAssetTableGroup, ...]
    class_labels: Mapping[str, str]


_CLASS_LABELS_FACT = StringMappingFact(
    fact_id="renta-actividad-inmovilizado-amortizacion-clase-denominacion",
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(
        subject="activity-asset table class names", value_whitespace=MappingValueWhitespace.STRIP
    ),
)
_CLASS_LABEL_PREFIXES: dict[DirectEstimationRegime, str] = {
    DirectEstimationRegime.NORMAL: "normal.",
    DirectEstimationRegime.SIMPLIFIED: "simplificada.",
}


def resolve_activity_asset_class_labels(
    authority: GovernedFactSource,
    *,
    regime: DirectEstimationRegime,
    tax_year: int,
) -> Mapping[str, str]:
    """Read the official names of a modality's table classes for the end of a tax year.

    Returns:
        Each class key mapped to the name its legal table gives it.
    """
    prefix = _CLASS_LABEL_PREFIXES[regime]
    entries = _CLASS_LABELS_FACT.resolve_entries(authority, effective_date=date(tax_year, 12, 31))
    return {key.removeprefix(prefix): name for key, name in entries.items() if key.startswith(prefix)}


def activity_asset_form_options(
    modelo_revision: ModeloRevision,
    *,
    tax_year: int,
    asset_kind: AssetKind,
    regime: DirectEstimationRegime,
    class_labels: Mapping[str, str],
) -> ActivityAssetFormOptions:
    """Read the admitted methods and table groups from the same parameters the resolver charges by.

    Raises:
        RegistryValidationError: When an offered table class has no official name.
    """
    parameters = _Parameters(
        by_id={parameter.id: parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    # Inside the resolver a missing row is a refusal; for a form it only means "not offered".
    methods = tuple(
        method
        for method in AmortizationMethod
        if method not in _REFUSED_METHOD_LOCALE_KEYS
        and parameters.keyed(_METHOD_ADMISSION_IDS[regime], f"{asset_kind.value}:{method.value}") == Decimal("1")
    )
    kind_parameter = _INTANGIBLE_CLASS_ID if asset_kind is AssetKind.INTANGIBLE else _MATERIAL_CLASS_ID
    groups: list[ActivityAssetTableGroup] = []
    for class_key in sorted({entry.key for entry in parameters.require(_COEFFICIENT_IDS[regime]).keyed_brackets}):
        maximum_percent = parameters.keyed(_COEFFICIENT_IDS[regime], class_key)
        period_years = parameters.keyed(_PERIOD_IDS[regime], class_key)
        if (
            maximum_percent is None
            or period_years is None
            or parameters.keyed(kind_parameter, class_key) != Decimal("1")
        ):
            continue
        class_label = class_labels.get(class_key)
        if class_label is None:
            raise RegistryValidationError(
                f"table class {class_key!r} has no official name for modality {regime.value!r}"
            )
        groups.append(
            ActivityAssetTableGroup(
                class_key=class_key,
                maximum_coefficient=maximum_percent / Decimal("100"),
                minimum_coefficient=Decimal("1") / period_years,
                maximum_period_years=period_years,
                class_label=class_label,
            ),
        )
    return ActivityAssetFormOptions(methods=methods, table_groups=tuple(groups), class_labels=class_labels)


__all__ = [
    "ACTIVITY_ASSET_PARAMETER_IDS",
    "ActivityAssetFormOptions",
    "ActivityAssetTableGroup",
    "activity_asset_form_options",
    "activity_asset_parameter_of_reference",
    "resolve_activity_asset_class_labels",
    "resolve_activity_asset_schedule_authority",
]
