"""Foreign-asset re-declaration advisory helpers for Modelo 720 and 721.

See Also:
    :mod:`~application._foreign_asset_thresholds`
        Resolves the per-bloque declaration floors and re-declaration deltas
        from the effective registry revision.
    :class:`~domain.calculations.registry.RegistryModeloObservation`
        Registry-grounded observation envelope accepted as prior, current, and
        current-declaration evidence.
    :mod:`~application.calculations.tests.test_modelo_720_prior_year_baseline_fidelity`
        Exercises the Modelo 720 prior-year baseline advisory path with real
        observations and enrollment evidence.
    :mod:`~application.calculations.tests.test_modelo_721_cripto_extranjero_fidelity`
        Exercises the Modelo 721 token baseline sibling through the same
        advisory mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core import CasillaId, ForeignAssetObligationGroup, Modelo
from ...domain.calculations.registry import RegistryModeloObservation
from ...domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._foreign_asset_thresholds import foreign_asset_declaration_thresholds

_M720_VALUATION_CASILLA_GROUPS: Mapping[CasillaId, ForeignAssetObligationGroup] = {
    "cuentas.valoracion": ForeignAssetObligationGroup.CUENTAS,
    "valores.valoracion": ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS,
    "inmuebles.valoracion": ForeignAssetObligationGroup.INMUEBLES,
}
_M720_GROUP_LABELS: Mapping[ForeignAssetObligationGroup, str] = {
    ForeignAssetObligationGroup.CUENTAS: "cuentas",
    ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS: "valores, derechos, seguros e IIC",
    ForeignAssetObligationGroup.INMUEBLES: "inmuebles",
}

_M721_CUSTODIAN_NAME_CASILLA: CasillaId = "custodio.nombre-razon-social"
_M721_CUSTODIAN_COUNTRY_CASILLA: CasillaId = "custodio.codigo-pais"
_M721_CRYPTO_ASSET_CASILLA: CasillaId = "moneda.clave-token"
_M721_BALANCE_CASILLA: CasillaId = "moneda.saldo-31-diciembre"


@dataclass(frozen=True, slots=True)
class _RedeclarationPosition:
    key: tuple[str, ...]
    label: str
    group: ForeignAssetObligationGroup
    value_eur: Decimal


def modelo_720_redeclaration_advisory_findings(
    *,
    prior_observation: RegistryModeloObservation,
    current_observation: RegistryModeloObservation,
    current_declaration_observation: RegistryModeloObservation | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return non-blocking M720 re-declaration advisories for omitted grown groups.

    ``current_observation`` is the operator's current-year valuation evidence;
    ``current_declaration_observation`` is the current filed/declarable row set.
    When omitted, the current evidence is also treated as the current declaration,
    so a correctly present row produces no advisory.

    See Also:
        :func:`~application._foreign_asset_thresholds.foreign_asset_declaration_thresholds`
            Supplies the strict per-obligation-block re-declaration delta.
    """
    return _redeclaration_advisory_findings(
        modelo=Modelo.M720.value,
        prior_positions=_modelo_720_positions(prior_observation),
        current_positions=_modelo_720_positions(current_observation),
        declared_positions=_modelo_720_positions(current_declaration_observation or current_observation),
        filing_year=current_observation.filing_year,
    )


def modelo_721_redeclaration_advisory_findings(
    *,
    prior_observation: RegistryModeloObservation,
    current_observation: RegistryModeloObservation,
    current_declaration_observation: RegistryModeloObservation | None = None,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return non-blocking M721 re-declaration advisories for omitted grown tokens.

    See Also:
        :class:`~core._foreign_asset_obligation.ForeignAssetObligationGroup`
            Provides the ``MONEDAS_VIRTUALES`` group used for the Modelo 721
            re-declaration threshold.
    """
    return _redeclaration_advisory_findings(
        modelo=Modelo.M721.value,
        prior_positions=_modelo_721_positions(prior_observation),
        current_positions=_modelo_721_positions(current_observation),
        declared_positions=_modelo_721_positions(current_declaration_observation or current_observation),
        filing_year=current_observation.filing_year,
    )


def _redeclaration_advisory_findings(
    *,
    modelo: str,
    prior_positions: Mapping[tuple[str, ...], _RedeclarationPosition],
    current_positions: Mapping[tuple[str, ...], _RedeclarationPosition],
    declared_positions: Mapping[tuple[str, ...], _RedeclarationPosition],
    filing_year: int,
) -> tuple[ModeloVerificationFinding, ...]:
    thresholds = foreign_asset_declaration_thresholds(modelo=modelo, filing_year=filing_year)
    findings: list[ModeloVerificationFinding] = []
    for key in sorted(prior_positions):
        prior = prior_positions[key]
        current = current_positions.get(key)
        if current is None or key in declared_positions:
            continue

        threshold = thresholds[prior.group]
        delta_eur = current.value_eur - prior.value_eur
        if delta_eur <= threshold.redeclaration_increase_delta_eur:
            continue

        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message=(
                    f"Modelo {modelo} re-declaration advisory: {current.label} grew by "
                    f"{delta_eur} EUR over the prior declared baseline "
                    f"({prior.value_eur} -> {current.value_eur}) and is absent from "
                    "the current declaration."
                ),
                next_action=(
                    "Declare the grown foreign-asset position in the current filing "
                    "or record non-declarability evidence before filing."
                ),
                legal_refs=threshold.legal_refs,
                source_refs=threshold.source_refs,
            )
        )
    return tuple(findings)


def _modelo_720_positions(observation: RegistryModeloObservation) -> Mapping[tuple[str, ...], _RedeclarationPosition]:
    totals: dict[ForeignAssetObligationGroup, Decimal] = {}
    for item in observation.observations:
        group = _M720_VALUATION_CASILLA_GROUPS.get(item.casilla_id)
        if group is None:
            continue
        totals[group] = totals.get(group, Decimal("0")) + item.value

    return {
        (group.value,): _RedeclarationPosition(
            key=(group.value,),
            label=_M720_GROUP_LABELS[group],
            group=group,
            value_eur=value,
        )
        for group, value in totals.items()
    }


def _modelo_721_positions(observation: RegistryModeloObservation) -> Mapping[tuple[str, ...], _RedeclarationPosition]:
    positions: dict[tuple[str, ...], _RedeclarationPosition] = {}
    custodian_name = ""
    custodian_country = ""
    token = ""
    for item in observation.observations:
        value = _decimal_text(item.value)
        if item.casilla_id == _M721_CUSTODIAN_NAME_CASILLA:
            custodian_name = value
        elif item.casilla_id == _M721_CUSTODIAN_COUNTRY_CASILLA:
            custodian_country = value
        elif item.casilla_id == _M721_CRYPTO_ASSET_CASILLA:
            token = value
        elif item.casilla_id == _M721_BALANCE_CASILLA and token:
            key = (
                ForeignAssetObligationGroup.MONEDAS_VIRTUALES.value,
                custodian_name,
                custodian_country,
                token,
            )
            existing = positions.get(key)
            value_eur = item.value if existing is None else existing.value_eur + item.value
            positions[key] = _RedeclarationPosition(
                key=key,
                label=f"custodian {custodian_name}/{custodian_country} token {token}",
                group=ForeignAssetObligationGroup.MONEDAS_VIRTUALES,
                value_eur=value_eur,
            )
            token = ""
    return positions


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


__all__ = [
    "modelo_720_redeclaration_advisory_findings",
    "modelo_721_redeclaration_advisory_findings",
]
