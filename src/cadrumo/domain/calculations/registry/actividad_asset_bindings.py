"""Resolve 2025 activity-asset schedule authority from registry parameters."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ...renta.actividad_asset.errors import ActividadAssetUnsupportedError
from ...renta.actividad_asset.lifecycle import AssetKind
from ...renta.actividad_asset.schedule import ScheduleAuthority
from .formula_runtime_ops import resolve_keyed_bracket
from .schema import ModeloRevision


class DirectEstimationRegime(StrEnum):
    """The two 2025 common-regime direct-estimation authority tables."""

    NORMAL = "normal"
    SIMPLIFIED = "simplified"


class ActivityAssetAuthoritySelection(BaseModel):
    """Exact registry selector supplied by an already-classified asset."""

    regime: DirectEstimationRegime
    asset_kind: AssetKind
    authority_class_key: str = Field(min_length=1, max_length=128)


_PARAMETER_IDS = {
    DirectEstimationRegime.NORMAL: "renta-actividad-inmovilizado-amortizacion-normal-coeficiente-lineal-maximo",
    DirectEstimationRegime.SIMPLIFIED: (
        "renta-actividad-inmovilizado-amortizacion-simplificada-coeficiente-lineal-maximo"
    ),
}


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
    parameter_id = _PARAMETER_IDS[selection.regime]
    parameters = {str(parameter.id): parameter for parameter in revision.parameters}
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


def _is_intangible_key(key: str) -> bool:
    return key.startswith("intangible-") or key == "equipo-informacion-software"


def _is_exclusively_intangible_key(key: str) -> bool:
    return key.startswith("intangible-")


__all__ = [
    "ActivityAssetAuthoritySelection",
    "DirectEstimationRegime",
    "resolve_activity_asset_schedule_authority",
]
