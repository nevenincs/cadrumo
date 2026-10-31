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
from collections.abc import Callable
from dataclasses import dataclass, replace
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
    PercentFact,
    VehicleAffectationRecovery,
)
from ...renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...renta.actividad_asset.schedule import ScheduleAuthority, add_fractional_years, add_years
from ...renta.actividad_asset.vehicle_affectation import require_vehicle_affected
from ...renta.actividad_asset.workforce import (
    WorkforceWindows,
    job_creation_increase,
    renewable_workforce_maintained,
)
from ...user_profile.plantilla_media import PlantillaMediaYear
from .actividad_asset_parameters import (
    ACTIVITY_ASSET_BUILDING_CLASS_ID,
    ACTIVITY_ASSET_CHARGING_FIRST_YEAR_ID,
    ACTIVITY_ASSET_CHARGING_LAST_YEAR_ID,
    ACTIVITY_ASSET_COEFFICIENT_IDS,
    ACTIVITY_ASSET_ELECTRIC_VEHICLE_FIRST_YEAR_ID,
    ACTIVITY_ASSET_ELECTRIC_VEHICLE_LAST_YEAR_ID,
    ACTIVITY_ASSET_EMPLOYMENT_FOLLOWING_MONTHS_ID,
    ACTIVITY_ASSET_EMPLOYMENT_INCREASE_DECIMALS_ID,
    ACTIVITY_ASSET_EMPLOYMENT_INVESTMENT_PER_UNIT_ID,
    ACTIVITY_ASSET_EMPLOYMENT_MAINTAINED_MONTHS_ID,
    ACTIVITY_ASSET_EMPLOYMENT_PRIOR_MONTHS_ID,
    ACTIVITY_ASSET_ERD_INDEFINITE_MULTIPLIER_ID,
    ACTIVITY_ASSET_ERD_MULTIPLIER_ID,
    ACTIVITY_ASSET_ERD_TURNOVER_ID,
    ACTIVITY_ASSET_FURNITURE_CLASS_ID,
    ACTIVITY_ASSET_GOODWILL_RATE_ID,
    ACTIVITY_ASSET_INDEFINITE_LIFE_RATE_ID,
    ACTIVITY_ASSET_INTANGIBLE_CLASS_ID,
    ACTIVITY_ASSET_LATER_AFFECTATION_PERIOD_ID,
    ACTIVITY_ASSET_LONG_PERIOD_ID,
    ACTIVITY_ASSET_LOW_VALUE_ANNUAL_CAP_ID,
    ACTIVITY_ASSET_LOW_VALUE_THRESHOLD_ID,
    ACTIVITY_ASSET_MATERIAL_CLASS_ID,
    ACTIVITY_ASSET_MEDIUM_PERIOD_ID,
    ACTIVITY_ASSET_METHOD_ADMISSION_IDS,
    ACTIVITY_ASSET_MINIMUM_PERCENTAGE_ID,
    ACTIVITY_ASSET_PERIOD_IDS,
    ACTIVITY_ASSET_REFUSED_METHOD_LOCALE_KEYS,
    ACTIVITY_ASSET_RENEWABLE_AVAILABILITY_ID,
    ACTIVITY_ASSET_RENEWABLE_FIRST_YEAR_ID,
    ACTIVITY_ASSET_RENEWABLE_FOLLOWING_MONTHS_ID,
    ACTIVITY_ASSET_RENEWABLE_INVESTMENT_CAP_ID,
    ACTIVITY_ASSET_RENEWABLE_LAST_YEAR_ID,
    ACTIVITY_ASSET_RENEWABLE_PRIOR_MONTHS_ID,
    ACTIVITY_ASSET_RESTRICTED_VEHICLE_CLASS_ID,
    ACTIVITY_ASSET_RND_BUILDING_PERIOD_ID,
    ACTIVITY_ASSET_SHIFT_HOURS_ID,
    ACTIVITY_ASSET_USED_BUILDING_AGE_ID,
    ACTIVITY_ASSET_USED_MULTIPLIER_ID,
    ACTIVITY_ASSET_WEIGHTING_ID,
    ActivityAssetParameters,
)
from .schema import ModeloRevision
from .schema_base import DateAxis, ThresholdComparison
from .schema_references import LegalReference, governed_period_span

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
    refusal = ACTIVITY_ASSET_REFUSED_METHOD_LOCALE_KEYS.get(election.method)
    if refusal is not None:
        raise ActividadAssetUnsupportedError(translated_message=refusal)
    parameters = ActivityAssetParameters(
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
    edition_available: bool = True
    """False when no edition covers the year, so its figures are unknown rather than absent in law."""
    later_affectation_period_years: int | None = None
    """The LIRPF art. 28.3 period the edition states, or ``None`` when it states none."""


def resolve_activity_asset_disposal_bounds(
    modelo_revision: ModeloRevision,
    *,
    tax_year: int,
    asset_revision: ActivityAssetRevision,
) -> ActivityAssetDisposalBounds:
    """Read a :class:`ModeloRevision`'s minimum and maximum coefficient for a baja, without judging the election.

    A baja looks back over years the element's election may no longer resolve in,
    so what the edition cannot supply stays absent rather than refused.
    """
    parameters = ActivityAssetParameters(
        by_id={parameter.id: parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    return replace(
        _coefficient_bounds(parameters, asset_revision),
        later_affectation_period_years=_later_affectation_period_years(parameters),
    )


def _later_affectation_period_years(parameters: ActivityAssetParameters) -> int | None:
    try:
        return int(parameters.value(ACTIVITY_ASSET_LATER_AFFECTATION_PERIOD_ID))
    except ActividadAssetError:
        return None


def _coefficient_bounds(
    parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision
) -> ActivityAssetDisposalBounds:
    election = asset_revision.amortization
    try:
        if election.method in {AmortizationMethod.GOODWILL, AmortizationMethod.INTANGIBLE_INDEFINITE_LIFE}:
            parameter_id = (
                ACTIVITY_ASSET_GOODWILL_RATE_ID
                if election.method is AmortizationMethod.GOODWILL
                else ACTIVITY_ASSET_INDEFINITE_LIFE_RATE_ID
            )
            rate = parameters.value(parameter_id) / Decimal("100")
            return ActivityAssetDisposalBounds(minimum_coefficient=rate, maximum_coefficient=rate)
        if election.method is AmortizationMethod.RESEARCH_DEVELOPMENT_BUILDING:
            rate = Decimal("1") / parameters.value(ACTIVITY_ASSET_RND_BUILDING_PERIOD_ID)
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
    parameters: ActivityAssetParameters,
    asset_revision: ActivityAssetRevision,
    legal_reference: Callable[[str], LegalReference],
) -> str:
    election = asset_revision.amortization
    parameter_id = ACTIVITY_ASSET_METHOD_ADMISSION_IDS[election.regime]
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
    parameters: ActivityAssetParameters,
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
    parameters: ActivityAssetParameters,
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


def _table_bounds(parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision) -> _TableBounds:
    """Resolve the class's maximum coefficient and the one its maximum period implies."""
    election = asset_revision.amortization
    class_key = election.authority_class_key
    if class_key is None:
        raise ActividadAssetIncompleteError(
            context={"method": election.method.value},
            translated_message="ledger.actividad_asset.errors.table_class_required",
        )
    kind_reference = _require_class_matches_kind(parameters, class_key, asset_revision.asset_kind)
    coefficient_id = ACTIVITY_ASSET_COEFFICIENT_IDS[election.regime]
    period_id = ACTIVITY_ASSET_PERIOD_IDS[election.regime]
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


def _require_class_matches_kind(parameters: ActivityAssetParameters, class_key: str, asset_kind: AssetKind) -> str:
    """Refuse a table class the registry does not admit for the asset's kind."""
    parameter_id = (
        ACTIVITY_ASSET_INTANGIBLE_CLASS_ID if asset_kind is AssetKind.INTANGIBLE else ACTIVITY_ASSET_MATERIAL_CLASS_ID
    )
    if not parameters.class_flag(parameter_id, class_key):
        raise ActividadAssetUnsupportedError(
            context={"class_key": class_key, "asset_kind": asset_kind.value},
            translated_message="ledger.actividad_asset.errors.table_class_wrong_kind",
        )
    return parameters.reference(parameter_id, class_key)


def _is_used_for_amortization(
    parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision, class_key: str
) -> bool:
    """Apply RIS art. 4.3: a building under the minimum age is not a used asset.

    Callers ask only where a used-asset multiplier is enrolled, so a used
    building elsewhere never has to evidence its construction date.
    """
    if asset_revision.acquired_condition is not AcquiredCondition.USED:
        return False
    if not parameters.class_flag(ACTIVITY_ASSET_BUILDING_CLASS_ID, class_key):
        return True
    built = asset_revision.building_construction_date
    if built is None:
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.used_building_requires_construction_date"
        )
    minimum_age, comparison = parameters.scalar(ACTIVITY_ASSET_USED_BUILDING_AGE_ID)
    age = _whole_years_between(built, asset_revision.in_service_date)
    return _reaches(Decimal(age), minimum_age, comparison)


def _whole_years_between(start: date, end: date) -> int:
    years = end.year - start.year
    return years if add_years(start, years) <= end else years - 1


def _reaches(value: Decimal, threshold: Decimal, comparison: ThresholdComparison) -> bool:
    return value >= threshold if comparison is ThresholdComparison.INCLUSIVE else value > threshold


def _resolve_linear(parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    election = asset_revision.amortization
    bounds = _table_bounds(parameters, asset_revision)
    maximum = bounds.maximum
    references = list(bounds.references)
    used_key = f"{election.regime.value}:{asset_revision.asset_kind.value}"
    used_multiplier = parameters.keyed(ACTIVITY_ASSET_USED_MULTIPLIER_ID, used_key)
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
            references.append(parameters.reference(ACTIVITY_ASSET_USED_MULTIPLIER_ID, used_key))
    if election.small_enterprise is not None:
        maximum *= _small_enterprise_multiplier(parameters, asset_revision, references)
    if election.shift_hours_per_day is not None:
        maximum = _multi_shift_maximum(parameters, election.regime, election.shift_hours_per_day, bounds, references)
    coefficient = _elected_coefficient(election, minimum=bounds.minimum, maximum=maximum)
    method_facts: dict[str, object] = {
        "annual_rate": min(coefficient, Decimal("1")),
        "maximum_period_ends_on": add_fractional_years(asset_revision.in_service_date, bounds.period_years),
    }
    if original_price is not None:
        method_facts["original_price_basis"] = original_price.original_price * asset_revision.basis.allocation_share()
    return _Resolution(method_facts=method_facts, references=tuple(references))


def _multi_shift_maximum(
    parameters: ActivityAssetParameters,
    regime: DirectEstimationRegime,
    hours_per_day: Decimal,
    bounds: _TableBounds,
    references: list[str],
) -> Decimal:
    shift_hours = parameters.keyed(ACTIVITY_ASSET_SHIFT_HOURS_ID, regime.value)
    if shift_hours is None:
        raise ActividadAssetUnsupportedError(
            context={"regime": regime.value},
            translated_message="ledger.actividad_asset.errors.multi_shift_not_enrolled",
        )
    if hours_per_day <= shift_hours:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.multi_shift_requires_extra_shift"
        )
    maximum = bounds.minimum + (bounds.maximum - bounds.minimum) * hours_per_day / shift_hours
    references.append(parameters.reference(ACTIVITY_ASSET_SHIFT_HOURS_ID, regime.value))
    return maximum


def _require_original_price_route(
    parameters: ActivityAssetParameters,
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
    parameters: ActivityAssetParameters,
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
        (
            _require_reduced_size(parameters, asset_revision, evidence),
            parameters.reference(ACTIVITY_ASSET_ERD_MULTIPLIER_ID),
        ),
    )
    return parameters.value(ACTIVITY_ASSET_ERD_MULTIPLIER_ID)


def _require_reduced_size(
    parameters: ActivityAssetParameters,
    asset_revision: ActivityAssetRevision,
    evidence: SmallEnterpriseEvidence,
) -> str:
    """Refuse unless the asset was made available in a LIS art. 101 period; return the threshold reference."""
    if evidence.made_available_on > asset_revision.in_service_date:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.asset_made_available_after_in_service"
        )
    threshold, comparison = parameters.scalar(ACTIVITY_ASSET_ERD_TURNOVER_ID)
    if _reaches(evidence.prior_period_net_turnover, threshold, comparison):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.reduced_size_turnover_reached"
        )
    return parameters.reference(ACTIVITY_ASSET_ERD_TURNOVER_ID)


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
            context={
                "elected": PercentFact(elected),
                "minimum": PercentFact(minimum),
                "maximum": PercentFact(maximum),
            },
            translated_message="ledger.actividad_asset.errors.elected_coefficient_out_of_range",
        )
    return elected


def _require_not_building_or_furniture(
    parameters: ActivityAssetParameters, bounds: _TableBounds, provision: str
) -> None:
    if parameters.class_flag(ACTIVITY_ASSET_BUILDING_CLASS_ID, bounds.class_key) or parameters.class_flag(
        ACTIVITY_ASSET_FURNITURE_CLASS_ID,
        bounds.class_key,
    ):
        raise ActividadAssetUnsupportedError(
            context={"provision": provision},
            translated_message="ledger.actividad_asset.errors.method_excludes_buildings_and_furniture",
        )


def takes_used_double_coefficient(
    modelo_revision: ModeloRevision,
    *,
    tax_year: int,
    asset_revision: ActivityAssetRevision,
) -> bool:
    """Say whether an element's linear charge rests on RIS art. 4.3.a's multiplied maximum.

    A coefficient elected inside the ordinary corridor takes nothing from the multiplier,
    and an originating-price election is letter b or c.  An element the schedule refuses,
    such as a multi-shift used one or a building with no stated age, takes none either.

    Args:
        modelo_revision: The :class:`ModeloRevision` supplying the coefficient authority.
        tax_year: The year whose amortization charge is being assessed.
        asset_revision: The element's effective acquisition and amortization election.
    """
    election = asset_revision.amortization
    if (
        election.method is not AmortizationMethod.LINEAR
        or election.used_original_price is not None
        or election.shift_hours_per_day is not None
        or asset_revision.acquired_condition is not AcquiredCondition.USED
    ):
        return False
    parameters = ActivityAssetParameters(
        by_id={parameter.id: parameter for parameter in modelo_revision.parameters},
        revision_id=modelo_revision.id,
        tax_year=tax_year,
    )
    try:
        bounds = _table_bounds(parameters, asset_revision)
        multiplier = parameters.keyed(
            ACTIVITY_ASSET_USED_MULTIPLIER_ID, f"{election.regime.value}:{asset_revision.asset_kind.value}"
        )
        used = multiplier is not None and _is_used_for_amortization(parameters, asset_revision, bounds.class_key)
    except ActividadAssetError:
        return False
    return used and (election.linear_coefficient is None or election.linear_coefficient > bounds.maximum)


def _resolve_constant_percentage(
    parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision
) -> _Resolution:
    """Apply LIS art. 12.1.b and RIS art. 5 to the elected coefficient."""
    bounds = _table_bounds(parameters, asset_revision)
    _require_not_building_or_furniture(parameters, bounds, "RIS art. 5.2")
    coefficient = _elected_coefficient(asset_revision.amortization, minimum=bounds.minimum, maximum=bounds.maximum)
    period = Decimal("1") / coefficient
    medium_threshold, medium_comparison = parameters.scalar(ACTIVITY_ASSET_MEDIUM_PERIOD_ID)
    long_threshold, long_comparison = parameters.scalar(ACTIVITY_ASSET_LONG_PERIOD_ID)
    if _reaches(period, long_threshold, long_comparison):
        band = "periodo-largo"
    elif _reaches(period, medium_threshold, medium_comparison):
        band = "periodo-medio"
    else:
        band = "periodo-corto"
    weight = parameters.keyed(ACTIVITY_ASSET_WEIGHTING_ID, band)
    if weight is None:
        raise ActividadAssetUnsupportedError(
            context={"band": band},
            translated_message="ledger.actividad_asset.errors.constant_percentage_weighting_not_enrolled",
        )
    floor = parameters.value(ACTIVITY_ASSET_MINIMUM_PERCENTAGE_ID) / Decimal("100")
    percentage = min(max(coefficient * weight, floor), Decimal("1"))
    return _Resolution(
        method_facts={
            "annual_rate": percentage,
            "useful_life_ends_on": add_fractional_years(asset_revision.in_service_date, period),
        },
        references=(
            *bounds.references,
            parameters.reference(ACTIVITY_ASSET_BUILDING_CLASS_ID, bounds.class_key),
            parameters.reference(ACTIVITY_ASSET_FURNITURE_CLASS_ID, bounds.class_key),
            parameters.reference(ACTIVITY_ASSET_MEDIUM_PERIOD_ID),
            parameters.reference(ACTIVITY_ASSET_LONG_PERIOD_ID),
            parameters.reference(ACTIVITY_ASSET_WEIGHTING_ID, band),
            parameters.reference(ACTIVITY_ASSET_MINIMUM_PERCENTAGE_ID),
        ),
    )


def _resolve_sum_of_digits(parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision) -> _Resolution:
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
            parameters.reference(ACTIVITY_ASSET_BUILDING_CLASS_ID, bounds.class_key),
            parameters.reference(ACTIVITY_ASSET_FURNITURE_CLASS_ID, bounds.class_key),
        ),
    )


def _resolve_approved_plan(parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision) -> _Resolution:
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


def _resolve_twentieth_limit(parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision) -> _Resolution:
    """Apply the LIS art. 12.2 one-twentieth ceiling to its two intangible cases.

    An element acquired in a reduced-size period deducts the LIS art. 103.5
    multiple of that amount.  Unlike art. 103.1, that paragraph does not
    require the element to be new.
    """
    election = asset_revision.amortization
    parameter_id = (
        ACTIVITY_ASSET_GOODWILL_RATE_ID
        if election.method is AmortizationMethod.GOODWILL
        else ACTIVITY_ASSET_INDEFINITE_LIFE_RATE_ID
    )
    rate = parameters.value(parameter_id) / Decimal("100")
    references = [parameters.reference(parameter_id)]
    evidence = election.small_enterprise
    if evidence is not None:
        references.append(_require_reduced_size(parameters, asset_revision, evidence))
        rate *= parameters.value(ACTIVITY_ASSET_ERD_INDEFINITE_MULTIPLIER_ID)
        references.append(parameters.reference(ACTIVITY_ASSET_ERD_INDEFINITE_MULTIPLIER_ID))
    return _Resolution(method_facts={"annual_rate": rate}, references=tuple(references))


def _resolve_low_value(parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision) -> _Resolution:
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
            "free_depreciation_unit_threshold": parameters.value(ACTIVITY_ASSET_LOW_VALUE_THRESHOLD_ID),
            "free_depreciation_annual_cap": parameters.value(ACTIVITY_ASSET_LOW_VALUE_ANNUAL_CAP_ID),
            "low_value": election,
        },
        references=(
            parameters.reference(ACTIVITY_ASSET_LOW_VALUE_THRESHOLD_ID),
            parameters.reference(ACTIVITY_ASSET_LOW_VALUE_ANNUAL_CAP_ID),
        ),
    )


def _resolve_research_development_free(
    parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision
) -> _Resolution:
    """Apply LIS art. 12.3.b/c: R&D elements other than buildings amortize freely."""
    class_key = asset_revision.amortization.authority_class_key
    references: tuple[str, ...] = ()
    if asset_revision.asset_kind is AssetKind.MATERIAL:
        if class_key is None:
            raise ActividadAssetIncompleteError(
                translated_message="ledger.actividad_asset.errors.research_development_free_table_class_required"
            )
        if parameters.class_flag(ACTIVITY_ASSET_BUILDING_CLASS_ID, class_key):
            raise ActividadAssetUnsupportedError(
                translated_message="ledger.actividad_asset.errors.research_development_free_excludes_buildings"
            )
        references = (parameters.reference(ACTIVITY_ASSET_BUILDING_CLASS_ID, class_key),)
    return _Resolution(method_facts={}, references=references)


def _resolve_research_development_building(
    parameters: ActivityAssetParameters,
    asset_revision: ActivityAssetRevision,
) -> _Resolution:
    """Apply LIS art. 12.3.b: an R&D building amortizes linearly over its period."""
    class_key = asset_revision.amortization.authority_class_key
    if class_key is None:  # defensive: election validation proves unreachable
        raise ActividadAssetIncompleteError(
            translated_message="ledger.actividad_asset.errors.research_development_building_table_class_required"
        )
    if not parameters.class_flag(ACTIVITY_ASSET_BUILDING_CLASS_ID, class_key):
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.research_development_building_requires_building_class"
        )
    period = parameters.value(ACTIVITY_ASSET_RND_BUILDING_PERIOD_ID)
    return _Resolution(
        method_facts={
            "annual_rate": Decimal("1") / period,
            "maximum_period_ends_on": add_fractional_years(asset_revision.in_service_date, period),
        },
        references=(
            parameters.reference(ACTIVITY_ASSET_BUILDING_CLASS_ID, class_key),
            parameters.reference(ACTIVITY_ASSET_RND_BUILDING_PERIOD_ID),
        ),
    )


def _resolve_charging_infrastructure(
    parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision
) -> _Resolution:
    """Apply LIS DA 18a.2: new charging points entering service in the enrolled periods."""
    if asset_revision.acquired_condition is not AcquiredCondition.NEW:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.charging_infrastructure_new_only"
        )
    first_year = parameters.value(ACTIVITY_ASSET_CHARGING_FIRST_YEAR_ID)
    last_year = parameters.value(ACTIVITY_ASSET_CHARGING_LAST_YEAR_ID)
    if not first_year <= Decimal(asset_revision.in_service_date.year) <= last_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.charging_infrastructure_period_not_enrolled"
        )
    return _Resolution(
        method_facts={},
        references=(
            parameters.reference(ACTIVITY_ASSET_CHARGING_FIRST_YEAR_ID),
            parameters.reference(ACTIVITY_ASSET_CHARGING_LAST_YEAR_ID),
        ),
    )


def _require_vehicle_affectation(
    parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision
) -> tuple[str, ...]:
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
        restricted = parameters.class_flag(ACTIVITY_ASSET_RESTRICTED_VEHICLE_CLASS_ID, class_key)
        references = (parameters.reference(ACTIVITY_ASSET_RESTRICTED_VEHICLE_CLASS_ID, class_key),)
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


def _resolve_electric_vehicle(
    parameters: ActivityAssetParameters, asset_revision: ActivityAssetRevision
) -> _Resolution:
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
    first_year = parameters.value(ACTIVITY_ASSET_ELECTRIC_VEHICLE_FIRST_YEAR_ID)
    last_year = parameters.value(ACTIVITY_ASSET_ELECTRIC_VEHICLE_LAST_YEAR_ID)
    if not first_year <= Decimal(asset_revision.in_service_date.year) <= last_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.electric_vehicle_period_not_enrolled"
        )
    return _Resolution(
        method_facts={},
        references=(
            parameters.reference(ACTIVITY_ASSET_ELECTRIC_VEHICLE_FIRST_YEAR_ID),
            parameters.reference(ACTIVITY_ASSET_ELECTRIC_VEHICLE_LAST_YEAR_ID),
        ),
    )


def _workforce_references(years: tuple[PlantillaMediaYear, ...]) -> tuple[str, ...]:
    """Name each declared year a workforce test used, with its observed or committed state.

    A committed year is a forecast the taxpayer must regularise if it is not
    met (LIS art. 102.4, DA 17a.7), so its state travels with the charge.
    """
    return tuple(f"taxpayer-profile:irpf.plantilla_media:{item.year}:{item.state.value}" for item in years)


def _resolve_employment_free(
    parameters: ActivityAssetParameters,
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
    increase = job_creation_increase(
        workforce,
        entry_year=asset_revision.in_service_date.year,
        windows=WorkforceWindows(
            prior_months=int(parameters.value(ACTIVITY_ASSET_EMPLOYMENT_PRIOR_MONTHS_ID)),
            following_months=int(parameters.value(ACTIVITY_ASSET_EMPLOYMENT_FOLLOWING_MONTHS_ID)),
            maintained_months=int(parameters.value(ACTIVITY_ASSET_EMPLOYMENT_MAINTAINED_MONTHS_ID)),
        ),
        increase_decimal_places=int(parameters.value(ACTIVITY_ASSET_EMPLOYMENT_INCREASE_DECIMALS_ID)),
    )
    per_unit = parameters.value(ACTIVITY_ASSET_EMPLOYMENT_INVESTMENT_PER_UNIT_ID)
    return _Resolution(
        method_facts={"free_depreciation_investment_cap": round_to_cents(per_unit * increase.increase)},
        references=(
            turnover_reference,
            parameters.reference(ACTIVITY_ASSET_EMPLOYMENT_INVESTMENT_PER_UNIT_ID),
            parameters.reference(ACTIVITY_ASSET_EMPLOYMENT_PRIOR_MONTHS_ID),
            parameters.reference(ACTIVITY_ASSET_EMPLOYMENT_FOLLOWING_MONTHS_ID),
            parameters.reference(ACTIVITY_ASSET_EMPLOYMENT_MAINTAINED_MONTHS_ID),
            parameters.reference(ACTIVITY_ASSET_EMPLOYMENT_INCREASE_DECIMALS_ID),
            *_workforce_references(increase.years),
        ),
    )


def _resolve_renewable_free(
    parameters: ActivityAssetParameters,
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
    first_year = parameters.value(ACTIVITY_ASSET_RENEWABLE_FIRST_YEAR_ID)
    last_year = parameters.value(ACTIVITY_ASSET_RENEWABLE_LAST_YEAR_ID)
    if not first_year <= Decimal(entry_year) <= last_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_entry_year_not_enrolled"
        )
    if entry_year != parameters.tax_year:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_only_in_entry_period"
        )
    maintenance = renewable_workforce_maintained(
        workforce,
        entry_year=entry_year,
        windows=WorkforceWindows(
            prior_months=int(parameters.value(ACTIVITY_ASSET_RENEWABLE_PRIOR_MONTHS_ID)),
            following_months=int(parameters.value(ACTIVITY_ASSET_RENEWABLE_FOLLOWING_MONTHS_ID)),
        ),
    )
    return _Resolution(
        method_facts={"free_depreciation_investment_cap": parameters.value(ACTIVITY_ASSET_RENEWABLE_INVESTMENT_CAP_ID)},
        references=(
            parameters.reference(ACTIVITY_ASSET_BUILDING_CLASS_ID, class_key),
            parameters.reference(ACTIVITY_ASSET_RENEWABLE_AVAILABILITY_ID),
            parameters.reference(ACTIVITY_ASSET_RENEWABLE_FIRST_YEAR_ID),
            parameters.reference(ACTIVITY_ASSET_RENEWABLE_LAST_YEAR_ID),
            parameters.reference(ACTIVITY_ASSET_RENEWABLE_INVESTMENT_CAP_ID),
            parameters.reference(ACTIVITY_ASSET_RENEWABLE_PRIOR_MONTHS_ID),
            parameters.reference(ACTIVITY_ASSET_RENEWABLE_FOLLOWING_MONTHS_ID),
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
    parameters: ActivityAssetParameters,
    asset_revision: ActivityAssetRevision,
    evidence: RenewableSelfConsumptionEvidence,
    class_key: str,
) -> None:
    if parameters.class_flag(ACTIVITY_ASSET_BUILDING_CLASS_ID, class_key):
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
    if parameters.on_date(
        ACTIVITY_ASSET_RENEWABLE_AVAILABILITY_ID, DateAxis.TRANSACTION_DATE, evidence.made_available_on
    ) != Decimal(
        "1",
    ):
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.renewable_made_available_before_admitted_date"
        )


_MethodResolver = Callable[
    [ActivityAssetParameters, ActivityAssetRevision, tuple[PlantillaMediaYear, ...]], _Resolution
]
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


__all__ = [
    "resolve_activity_asset_schedule_authority",
    "takes_used_double_coefficient",
]
