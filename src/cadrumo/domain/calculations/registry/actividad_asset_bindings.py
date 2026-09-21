"""Resolve 2025 activity-asset schedule authority from registry parameters."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import override

from pydantic import BaseModel, Field

from ...renta.actividad_asset.errors import ActividadAssetUnsupportedError
from ...renta.actividad_asset.lifecycle import AssetKind
from ...renta.actividad_asset.schedule import (
    AmortizationMethod,
    FreeDepreciationElection,
    ScheduleAuthority,
)
from .formula_runtime_ops import resolve_dated_value, resolve_keyed_bracket
from .schema import ModeloRevision
from .schema_formula import ParameterDefinition


class DirectEstimationRegime(StrEnum):
    """The two 2025 common-regime direct-estimation authority tables."""

    NORMAL = "normal"
    SIMPLIFIED = "simplified"


class ActivityAssetAmortizationMethod(StrEnum):
    """Supported 2025 direct-estimation methods selected before forecasting."""

    LINEAR = "linear"
    LOW_VALUE_FREE = "low_value_free"


class ActivityAssetAuthoritySelection(BaseModel):
    """Exact registry selector supplied by an already-classified asset."""

    regime: DirectEstimationRegime
    asset_kind: AssetKind
    authority_class_key: str = Field(min_length=1, max_length=128)
    method: ActivityAssetAmortizationMethod = ActivityAssetAmortizationMethod.LINEAR
    free_depreciation_election: FreeDepreciationElection | None = None

    @override
    def model_post_init(self, __context: object) -> None:
        """Refuse an implicit or ineligible low-value election."""
        if self.method is ActivityAssetAmortizationMethod.LOW_VALUE_FREE:
            if self.asset_kind is not AssetKind.MATERIAL:
                raise ValueError("low-value free depreciation is limited to material assets")
            if self.free_depreciation_election is None:
                raise ValueError("low-value free depreciation requires an explicit election")
        elif self.free_depreciation_election is not None:
            raise ValueError("linear authority selection cannot carry a free-depreciation election")


_PARAMETER_IDS = {
    DirectEstimationRegime.NORMAL: "renta-actividad-inmovilizado-amortizacion-normal-coeficiente-lineal-maximo",
    DirectEstimationRegime.SIMPLIFIED: (
        "renta-actividad-inmovilizado-amortizacion-simplificada-coeficiente-lineal-maximo"
    ),
}

_LOW_VALUE_FREE_THRESHOLD_PARAMETER_ID = (
    "renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-umbral-unitario"
)
_LOW_VALUE_FREE_ANNUAL_CAP_PARAMETER_ID = (
    "renta-actividad-inmovilizado-material-nuevo-libertad-amortizacion-limite-anual"
)


def resolve_activity_asset_schedule_authority(
    revision: ModeloRevision,
    *,
    tax_year: int,
    selection: ActivityAssetAuthoritySelection,
    authority_generation: str,
) -> ScheduleAuthority:
    """Resolve an exact linear class key without a caller-authored rate.

    This initial resolver covers tabled software/audiovisual intangibles (and
    the simplified table's combined information-equipment/software class).
    The separately authored 5% non-estimable-life and goodwill parameters are
    not linear-table classes and remain unsupported here.
    """
    if tax_year != 2025 or revision.id != "2025":
        raise ActividadAssetUnsupportedError("activity-asset schedule authority supports only Modelo 100 revision 2025")
    parameters = {str(parameter.id): parameter for parameter in revision.parameters}
    if selection.method is ActivityAssetAmortizationMethod.LOW_VALUE_FREE:
        return _resolve_low_value_free_authority(
            parameters,
            tax_year=tax_year,
            selection=selection,
            authority_generation=authority_generation,
            revision_id=revision.id,
        )

    parameter_id = _PARAMETER_IDS[selection.regime]
    parameter = parameters.get(parameter_id)
    if parameter is None:
        raise ActividadAssetUnsupportedError(
            f"activity-asset authority parameter {parameter_id!r} is absent from Modelo 100 revision 2025",
        )
    rate_percent = resolve_keyed_bracket(
        parameter,
        key=selection.authority_class_key,
        filing_year=tax_year,
    )
    if rate_percent is None:
        raise ActividadAssetUnsupportedError(
            "activity-asset authority class is not enrolled for the selected 2025 direct-estimation regime",
        )
    if selection.asset_kind is AssetKind.INTANGIBLE and not _is_intangible_key(selection.authority_class_key):
        raise ActividadAssetUnsupportedError("intangible asset requires an enrolled intangible authority class")
    if selection.asset_kind is AssetKind.MATERIAL and _is_exclusively_intangible_key(selection.authority_class_key):
        raise ActividadAssetUnsupportedError("material asset cannot use an exclusively intangible authority class")
    return ScheduleAuthority(
        tax_year=tax_year,
        asset_kind=selection.asset_kind,
        annual_rate=rate_percent / 100,
        authority_generation=authority_generation,
        source_reference=f"modelo-100:{revision.id}:parameter:{parameter_id}:key:{selection.authority_class_key}",
    )


def _resolve_low_value_free_authority(
    parameters: dict[str, ParameterDefinition],
    *,
    tax_year: int,
    selection: ActivityAssetAuthoritySelection,
    authority_generation: str,
    revision_id: str,
) -> ScheduleAuthority:
    """Resolve the enacted €300 / €25,000 branch from published registry facts."""
    threshold_parameter = parameters.get(_LOW_VALUE_FREE_THRESHOLD_PARAMETER_ID)
    annual_cap_parameter = parameters.get(_LOW_VALUE_FREE_ANNUAL_CAP_PARAMETER_ID)
    if threshold_parameter is None or annual_cap_parameter is None:
        raise ActividadAssetUnsupportedError(
            "low-value free-depreciation authority is absent from Modelo 100 revision 2025",
        )
    # ``parameters`` originates from ModeloRevision and is deliberately checked
    # through the canonical scalar resolver, which also rejects malformed date
    # windows and parameter shapes.
    try:
        threshold = resolve_dated_value(threshold_parameter, {"filing_period": _filing_period_date(tax_year)}).value
        annual_cap = resolve_dated_value(annual_cap_parameter, {"filing_period": _filing_period_date(tax_year)}).value
    except Exception as exc:
        raise ActividadAssetUnsupportedError(
            "low-value free-depreciation authority is not resolvable for 2025",
        ) from exc
    election = selection.free_depreciation_election
    if election is None:  # defensive: selector validation proves this
        raise ActividadAssetUnsupportedError("low-value free depreciation requires explicit election evidence")
    return ScheduleAuthority(
        tax_year=tax_year,
        asset_kind=selection.asset_kind,
        annual_rate=None,
        authority_generation=authority_generation,
        source_reference=(
            f"modelo-100:{revision_id}:parameter:{_LOW_VALUE_FREE_THRESHOLD_PARAMETER_ID}"
            f":parameter:{_LOW_VALUE_FREE_ANNUAL_CAP_PARAMETER_ID}"
        ),
        method=AmortizationMethod.LOW_VALUE_FREE,
        free_depreciation_unit_threshold=threshold,
        free_depreciation_annual_cap=annual_cap,
        free_depreciation_election=election,
    )


def _filing_period_date(tax_year: int) -> date:
    """Provide the registry's filing-period coordinate for annual facts."""
    return date(tax_year, 12, 31)


def _is_intangible_key(key: str) -> bool:
    return key.startswith("intangible-") or key == "equipo-informacion-software"


def _is_exclusively_intangible_key(key: str) -> bool:
    return key.startswith("intangible-")


__all__ = [
    "ActivityAssetAmortizationMethod",
    "ActivityAssetAuthoritySelection",
    "DirectEstimationRegime",
    "resolve_activity_asset_schedule_authority",
]
