"""Build objective-estimation exclusion advisories from :class:`TaxpayerProfile`.

The check compares profile-declared prior-year objective-estimation volumes
with registry legal parameters before emitting
:class:`ModeloVerificationFinding` warnings for affected modelo work units.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core import Modelo
from ...core.resources import resources
from ...domain.deadlines import IrpfEstimationRegime, TaxpayerProfile
from ...domain.modelos._errors import ModeloValidationError
from ...domain.modelos._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry import LegalParameter
    from ...domain.modelos._work_unit import WorkUnit

_SETTLED_YEAR_MIN = 2016
_SETTLED_YEAR_MAX = 2024
_AFFECTED_MODELOS = frozenset({Modelo.M100.value, Modelo.M131.value})

_PARAMETER_BY_PROFILE_FIELD = (
    (
        "objective_estimation_prior_year_gross_income_eur",
        "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur",
        "rendimientos integros del conjunto de actividades economicas",
    ),
    (
        "objective_estimation_prior_year_invoice_gross_income_eur",
        "lirpf-dt-32:eo-exclusion-rendimientos-factura-eur",
        "rendimientos integros de operaciones con obligacion de factura",
    ),
    (
        "objective_estimation_prior_year_purchases_eur",
        "lirpf-dt-32:eo-exclusion-compras-eur",
        "volumen de compras en bienes y servicios",
    ),
)


def _objective_estimation_exclusion_advisory_findings(
    *,
    work_unit: WorkUnit,
    profile: TaxpayerProfile,
) -> tuple[ModeloVerificationFinding, ...]:
    modelo = str(getattr(work_unit.modelo, "value", work_unit.modelo))
    if modelo not in _AFFECTED_MODELOS:
        return ()
    if not _uses_objective_estimation(profile):
        return ()
    if not _SETTLED_YEAR_MIN <= work_unit.filing_year <= _SETTLED_YEAR_MAX:
        return ()

    declared_values = tuple(
        (profile_field, parameter_id, label, getattr(profile, profile_field))
        for profile_field, parameter_id, label in _PARAMETER_BY_PROFILE_FIELD
    )
    if all(raw_value is None for *_prefix, raw_value in declared_values):
        return ()

    parameters = resources().legal_parameters.singleton
    findings: list[ModeloVerificationFinding] = []
    for profile_field, parameter_id, label, raw_value in declared_values:
        if raw_value is None:
            continue
        declared = _as_decimal(raw_value, profile_field)
        parameter = _require_parameter(parameters, parameter_id)
        threshold = _as_decimal(parameter.value, parameter_id)
        if declared <= threshold:
            continue
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message=(
                    "estimacion objetiva declared volume exceeds the settled DT 32 exclusion magnitude: "
                    f"modelo={modelo} year={work_unit.filing_year} field={profile_field} "
                    f"declared={declared} EUR threshold={threshold} EUR ({label})."
                ),
                next_action=(
                    "Review whether estimacion objetiva remains applicable for this filing year. If the "
                    "exclusion applies, update the IRPF estimation regime/profile before filing; if it does not, "
                    "retain the supporting activity-volume evidence."
                ),
                legal_refs=tuple(str(ref) for ref in parameter.legal_refs),
            ),
        )
    return tuple(findings)


def _uses_objective_estimation(profile: TaxpayerProfile) -> bool:
    return profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA or profile.uses_objective_estimation_irpf


def _require_parameter(parameters: Mapping[str, LegalParameter], parameter_id: str) -> LegalParameter:
    parameter = parameters.get(parameter_id)
    if parameter is None:
        raise ModeloValidationError(f"missing legal parameter {parameter_id!r} for objective-estimation advisory")
    return parameter


def _as_decimal(value: object, surface: str) -> Decimal:
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ModeloValidationError(f"invalid decimal value {value!r} for {surface}") from exc


__all__ = ["_objective_estimation_exclusion_advisory_findings"]
