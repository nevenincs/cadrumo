"""Registry parameter identities and lookup for activity-asset schedules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...renta.actividad_asset.election import AmortizationMethod, DirectEstimationRegime
from ...renta.actividad_asset.errors import ActividadAssetUnsupportedError, ActividadAssetValidationError
from ...renta.actividad_asset.lifecycle import AssetKind
from .formula_runtime_ops import resolve_dated_value, resolve_keyed_bracket
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
_EMPLOYMENT_PRIOR_MONTHS_ID = f"{_PREFIX}-erd-empleo-plantilla-meses-anteriores"
_EMPLOYMENT_FOLLOWING_MONTHS_ID = f"{_PREFIX}-erd-empleo-plantilla-meses-siguientes"
_EMPLOYMENT_MAINTAINED_MONTHS_ID = f"{_PREFIX}-erd-empleo-plantilla-meses-mantenimiento"
_EMPLOYMENT_INCREASE_DECIMALS_ID = f"{_PREFIX}-erd-empleo-incremento-decimales"
_RENEWABLE_PRIOR_MONTHS_ID = f"{_PREFIX}-renovables-plantilla-meses-anteriores"
_RENEWABLE_FOLLOWING_MONTHS_ID = f"{_PREFIX}-renovables-plantilla-meses-siguientes"
_LATER_AFFECTATION_PERIOD_ID = "renta-actividad-afectacion-posterior-enajenacion-plazo-anos"
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
        _EMPLOYMENT_PRIOR_MONTHS_ID,
        _EMPLOYMENT_FOLLOWING_MONTHS_ID,
        _EMPLOYMENT_MAINTAINED_MONTHS_ID,
        _EMPLOYMENT_INCREASE_DECIMALS_ID,
        _RENEWABLE_PRIOR_MONTHS_ID,
        _RENEWABLE_FOLLOWING_MONTHS_ID,
        _LATER_AFFECTATION_PERIOD_ID,
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

    def class_flag(self, parameter_id: str, class_key: str) -> bool:
        """Read a table class's yes-or-no classification, refusing a class the registry leaves unclassified."""
        flag = self.keyed(parameter_id, class_key)
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

    def requires_vehicle_declaration(self, asset_kind: AssetKind, class_key: str) -> bool:
        """Say whether a material asset of this table class is charged only on a vehicle affectation declaration."""
        return asset_kind is AssetKind.MATERIAL and self.class_flag(_RESTRICTED_VEHICLE_CLASS_ID, class_key)

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


_REFUSED_METHOD_LOCALE_KEYS: dict[AmortizationMethod, str] = {
    AmortizationMethod.JUSTIFIED_AMOUNT: "ledger.actividad_asset.errors.justified_amount_unvalidated",
    AmortizationMethod.ENTITY_REGIME_FREE: "ledger.actividad_asset.errors.entity_regime_not_individual",
}

# These identities and the resolver are shared with sibling registry modules.
# Keep their cross-module API explicit instead of importing implementation-private
# names from this module.
ACTIVITY_ASSET_BUILDING_CLASS_ID = _BUILDING_CLASS_ID
ACTIVITY_ASSET_CHARGING_FIRST_YEAR_ID = _CHARGING_FIRST_YEAR_ID
ACTIVITY_ASSET_CHARGING_LAST_YEAR_ID = _CHARGING_LAST_YEAR_ID
ACTIVITY_ASSET_COEFFICIENT_IDS = _COEFFICIENT_IDS
ACTIVITY_ASSET_ELECTRIC_VEHICLE_FIRST_YEAR_ID = _ELECTRIC_VEHICLE_FIRST_YEAR_ID
ACTIVITY_ASSET_ELECTRIC_VEHICLE_LAST_YEAR_ID = _ELECTRIC_VEHICLE_LAST_YEAR_ID
ACTIVITY_ASSET_EMPLOYMENT_FOLLOWING_MONTHS_ID = _EMPLOYMENT_FOLLOWING_MONTHS_ID
ACTIVITY_ASSET_EMPLOYMENT_INCREASE_DECIMALS_ID = _EMPLOYMENT_INCREASE_DECIMALS_ID
ACTIVITY_ASSET_EMPLOYMENT_INVESTMENT_PER_UNIT_ID = _EMPLOYMENT_INVESTMENT_PER_UNIT_ID
ACTIVITY_ASSET_EMPLOYMENT_MAINTAINED_MONTHS_ID = _EMPLOYMENT_MAINTAINED_MONTHS_ID
ACTIVITY_ASSET_EMPLOYMENT_PRIOR_MONTHS_ID = _EMPLOYMENT_PRIOR_MONTHS_ID
ACTIVITY_ASSET_ERD_INDEFINITE_MULTIPLIER_ID = _ERD_INDEFINITE_MULTIPLIER_ID
ACTIVITY_ASSET_ERD_MULTIPLIER_ID = _ERD_MULTIPLIER_ID
ACTIVITY_ASSET_ERD_TURNOVER_ID = _ERD_TURNOVER_ID
ACTIVITY_ASSET_FURNITURE_CLASS_ID = _FURNITURE_CLASS_ID
ACTIVITY_ASSET_GOODWILL_RATE_ID = _GOODWILL_RATE_ID
ACTIVITY_ASSET_INDEFINITE_LIFE_RATE_ID = _INDEFINITE_LIFE_RATE_ID
ACTIVITY_ASSET_INTANGIBLE_CLASS_ID = _INTANGIBLE_CLASS_ID
ACTIVITY_ASSET_LATER_AFFECTATION_PERIOD_ID = _LATER_AFFECTATION_PERIOD_ID
ACTIVITY_ASSET_LONG_PERIOD_ID = _LONG_PERIOD_ID
ACTIVITY_ASSET_LOW_VALUE_ANNUAL_CAP_ID = _LOW_VALUE_ANNUAL_CAP_ID
ACTIVITY_ASSET_LOW_VALUE_THRESHOLD_ID = _LOW_VALUE_THRESHOLD_ID
ACTIVITY_ASSET_MATERIAL_CLASS_ID = _MATERIAL_CLASS_ID
ACTIVITY_ASSET_MEDIUM_PERIOD_ID = _MEDIUM_PERIOD_ID
ACTIVITY_ASSET_METHOD_ADMISSION_IDS = _METHOD_ADMISSION_IDS
ACTIVITY_ASSET_MINIMUM_PERCENTAGE_ID = _MINIMUM_PERCENTAGE_ID
ACTIVITY_ASSET_PERIOD_IDS = _PERIOD_IDS
ACTIVITY_ASSET_REFUSED_METHOD_LOCALE_KEYS = _REFUSED_METHOD_LOCALE_KEYS
ACTIVITY_ASSET_RENEWABLE_AVAILABILITY_ID = _RENEWABLE_AVAILABILITY_ID
ACTIVITY_ASSET_RENEWABLE_FIRST_YEAR_ID = _RENEWABLE_FIRST_YEAR_ID
ACTIVITY_ASSET_RENEWABLE_FOLLOWING_MONTHS_ID = _RENEWABLE_FOLLOWING_MONTHS_ID
ACTIVITY_ASSET_RENEWABLE_INVESTMENT_CAP_ID = _RENEWABLE_INVESTMENT_CAP_ID
ACTIVITY_ASSET_RENEWABLE_LAST_YEAR_ID = _RENEWABLE_LAST_YEAR_ID
ACTIVITY_ASSET_RENEWABLE_PRIOR_MONTHS_ID = _RENEWABLE_PRIOR_MONTHS_ID
ACTIVITY_ASSET_RESTRICTED_VEHICLE_CLASS_ID = _RESTRICTED_VEHICLE_CLASS_ID
ACTIVITY_ASSET_RND_BUILDING_PERIOD_ID = _RND_BUILDING_PERIOD_ID
ACTIVITY_ASSET_SHIFT_HOURS_ID = _SHIFT_HOURS_ID
ACTIVITY_ASSET_USED_BUILDING_AGE_ID = _USED_BUILDING_AGE_ID
ACTIVITY_ASSET_USED_MULTIPLIER_ID = _USED_MULTIPLIER_ID
ACTIVITY_ASSET_WEIGHTING_ID = _WEIGHTING_ID
ActivityAssetParameters = _Parameters

__all__ = [
    "ACTIVITY_ASSET_BUILDING_CLASS_ID",
    "ACTIVITY_ASSET_CHARGING_FIRST_YEAR_ID",
    "ACTIVITY_ASSET_CHARGING_LAST_YEAR_ID",
    "ACTIVITY_ASSET_COEFFICIENT_IDS",
    "ACTIVITY_ASSET_ELECTRIC_VEHICLE_FIRST_YEAR_ID",
    "ACTIVITY_ASSET_ELECTRIC_VEHICLE_LAST_YEAR_ID",
    "ACTIVITY_ASSET_EMPLOYMENT_FOLLOWING_MONTHS_ID",
    "ACTIVITY_ASSET_EMPLOYMENT_INCREASE_DECIMALS_ID",
    "ACTIVITY_ASSET_EMPLOYMENT_INVESTMENT_PER_UNIT_ID",
    "ACTIVITY_ASSET_EMPLOYMENT_MAINTAINED_MONTHS_ID",
    "ACTIVITY_ASSET_EMPLOYMENT_PRIOR_MONTHS_ID",
    "ACTIVITY_ASSET_ERD_INDEFINITE_MULTIPLIER_ID",
    "ACTIVITY_ASSET_ERD_MULTIPLIER_ID",
    "ACTIVITY_ASSET_ERD_TURNOVER_ID",
    "ACTIVITY_ASSET_FURNITURE_CLASS_ID",
    "ACTIVITY_ASSET_GOODWILL_RATE_ID",
    "ACTIVITY_ASSET_INDEFINITE_LIFE_RATE_ID",
    "ACTIVITY_ASSET_INTANGIBLE_CLASS_ID",
    "ACTIVITY_ASSET_LATER_AFFECTATION_PERIOD_ID",
    "ACTIVITY_ASSET_LONG_PERIOD_ID",
    "ACTIVITY_ASSET_LOW_VALUE_ANNUAL_CAP_ID",
    "ACTIVITY_ASSET_LOW_VALUE_THRESHOLD_ID",
    "ACTIVITY_ASSET_MATERIAL_CLASS_ID",
    "ACTIVITY_ASSET_MEDIUM_PERIOD_ID",
    "ACTIVITY_ASSET_METHOD_ADMISSION_IDS",
    "ACTIVITY_ASSET_MINIMUM_PERCENTAGE_ID",
    "ACTIVITY_ASSET_PARAMETER_IDS",
    "ACTIVITY_ASSET_PERIOD_IDS",
    "ACTIVITY_ASSET_REFUSED_METHOD_LOCALE_KEYS",
    "ACTIVITY_ASSET_RENEWABLE_AVAILABILITY_ID",
    "ACTIVITY_ASSET_RENEWABLE_FIRST_YEAR_ID",
    "ACTIVITY_ASSET_RENEWABLE_FOLLOWING_MONTHS_ID",
    "ACTIVITY_ASSET_RENEWABLE_INVESTMENT_CAP_ID",
    "ACTIVITY_ASSET_RENEWABLE_LAST_YEAR_ID",
    "ACTIVITY_ASSET_RENEWABLE_PRIOR_MONTHS_ID",
    "ACTIVITY_ASSET_RESTRICTED_VEHICLE_CLASS_ID",
    "ACTIVITY_ASSET_RND_BUILDING_PERIOD_ID",
    "ACTIVITY_ASSET_SHIFT_HOURS_ID",
    "ACTIVITY_ASSET_USED_BUILDING_AGE_ID",
    "ACTIVITY_ASSET_USED_MULTIPLIER_ID",
    "ACTIVITY_ASSET_WEIGHTING_ID",
    "ActivityAssetParameters",
    "activity_asset_parameter_of_reference",
]
