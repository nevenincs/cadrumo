"""Registry-resolved thresholds for Modelo 720 and Modelo 721 foreign assets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

from ..core import ForeignAssetObligationGroup
from ..core.resources import resources
from ..domain.calculations.registry import (
    ModeloRevision,
    ParameterDefinition,
    RegistryValidationError,
    resolve_parameter,
)

_ANNUAL_PERIOD = "0A"
_INITIAL_PARAMETER_IDS = {
    "720": "modelo-720-asset-declaration-threshold-eur",
    "721": "modelo-721-asset-declaration-threshold-eur",
}
_REDECLARATION_PARAMETER_IDS = {
    "720": "modelo-720-redeclaration-increment-threshold-eur",
    "721": "modelo-721-redeclaration-increment-threshold-eur",
}
_GROUPS_BY_MODELO = {
    "720": (
        ForeignAssetObligationGroup.CUENTAS,
        ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS,
        ForeignAssetObligationGroup.INMUEBLES,
    ),
    "721": (ForeignAssetObligationGroup.MONEDAS_VIRTUALES,),
}


@dataclass(frozen=True, slots=True)
class ForeignAssetDeclarationThreshold:
    """One selected revision's declaration and re-declaration limits for a bloque."""

    group: ForeignAssetObligationGroup
    initial_declaration_floor_eur: Decimal
    redeclaration_increase_delta_eur: Decimal
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


def foreign_asset_declaration_thresholds(
    *,
    modelo: str,
    filing_year: int,
) -> Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold]:
    """Resolve foreign-asset thresholds from the selected bundled registry revision."""
    snapshot = resources().modelos.authority.snapshot(
        modelo,
        filing_year=filing_year,
        period=_ANNUAL_PERIOD,
        on=date(filing_year, 12, 31),
    )
    return foreign_asset_declaration_thresholds_for_revision(
        modelo=modelo,
        revision=snapshot.revision,
        filing_date=date(filing_year, 12, 31),
    )


def foreign_asset_declaration_thresholds_for_revision(
    *,
    modelo: str,
    revision: ModeloRevision,
    filing_date: date,
) -> Mapping[ForeignAssetObligationGroup, ForeignAssetDeclarationThreshold]:
    """Resolve the threshold parameters declared by one already-selected revision."""
    groups = _GROUPS_BY_MODELO.get(modelo)
    initial_parameter_id = _INITIAL_PARAMETER_IDS.get(modelo)
    redeclaration_parameter_id = _REDECLARATION_PARAMETER_IDS.get(modelo)
    if groups is None or initial_parameter_id is None or redeclaration_parameter_id is None:
        raise RegistryValidationError(f"modelo {modelo!r} has no foreign-asset threshold parameter contract")

    parameters = {parameter.id: parameter for parameter in revision.parameters}
    initial = _required_parameter(parameters, initial_parameter_id, modelo)
    redeclaration = _required_parameter(parameters, redeclaration_parameter_id, modelo)
    date_context = {"filing_period": filing_date}
    initial_value = resolve_parameter(initial, date_context)
    redeclaration_value = resolve_parameter(redeclaration, date_context)
    legal_refs = tuple(sorted(set(initial.legal_refs) | set(redeclaration.legal_refs)))
    source_refs = tuple(sorted(set(initial.source_refs) | set(redeclaration.source_refs)))
    thresholds = {
        group: ForeignAssetDeclarationThreshold(
            group=group,
            initial_declaration_floor_eur=initial_value,
            redeclaration_increase_delta_eur=redeclaration_value,
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
        for group in groups
    }
    return MappingProxyType(thresholds)


def _required_parameter(
    parameters: Mapping[str, ParameterDefinition],
    parameter_id: str,
    modelo: str,
) -> ParameterDefinition:
    try:
        return parameters[parameter_id]
    except KeyError as exc:
        raise RegistryValidationError(
            f"modelo {modelo} revision is missing foreign-asset parameter {parameter_id!r}",
        ) from exc


__all__ = [
    "ForeignAssetDeclarationThreshold",
    "foreign_asset_declaration_thresholds",
    "foreign_asset_declaration_thresholds_for_revision",
]
