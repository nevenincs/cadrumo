"""Build objective-estimation exclusion advisories from :class:`TaxpayerProfile`.

The verification path calls this helper for each revision :class:`WorkUnit` and
workflow :class:`TaxpayerProfile`. It applies only to objective-estimation
profiles for Modelo 100 and Modelo 131 in the settled official-source range
(filing years 2016-2026). For those years, the helper compares the
profile-declared prior-year objective-estimation volumes against the bundled
legal-parameter thresholds and emits non-blocking
:class:`ModeloVerificationFinding` warnings when a declared volume exceeds a
threshold.

See Also:
    :func:`~application.modelo._verification_actions._collect_revision_verification_findings`:
        Verification collector that appends these advisories after predicate and
        reduction-advisory checks.
    :class:`TaxpayerProfile`:
        Carries the objective-estimation regime flag and prior-year volume facts.
    :class:`WorkUnit`:
        Supplies the modelo code and filing year that bound the advisory scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core import Modelo
from ...core.decimal import coerce_decimal_strict
from ...core.resources import bundled_path
from ...domain.calculations.registry.loader import load_legal_parameters_only
from ...domain.deadlines import IrpfEstimationRegime, TaxpayerProfile
from ...domain.modelos import (
    ModeloValidationError,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema_references import LegalParameter

    from ...domain.calculations.registry.ids import SourceRefId
    from ...domain.modelos import WorkUnit

_SETTLED_YEAR_MIN = 2016
_SETTLED_YEAR_MAX = 2026
_AFFECTED_MODELOS = frozenset({Modelo.M100.value, Modelo.M131.value})
_AEAT_RENTA_2025_MANUAL_SOURCE_REF: SourceRefId = "aeat-renta-2025-manual-parte1"

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
        "objective_estimation_prior_year_agri_livestock_forest_gross_eur",
        "lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur",
        "rendimientos integros de actividades agricolas, ganaderas y forestales",
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
    """Return warnings for objective-estimation exclusion excesses.

    The helper is deliberately advisory-only: exceeding a settled exclusion
    magnitude suggests the taxpayer may have left estimación objetiva, but the
    operator still needs to review the underlying activity-volume evidence. The
    helper therefore emits :class:`ModeloVerificationFinding` rows with
    ``kind=ADVISORY`` and ``severity=WARNING`` rather than blocking verification.

    Args:
        work_unit: The :class:`WorkUnit` whose modelo and filing year determine
            whether the settled official-source advisory applies.
        profile: The :class:`TaxpayerProfile` providing the IRPF estimation
            regime and objective-estimation prior-year volume facts.

    Returns:
        A tuple of :class:`ModeloVerificationFinding` warnings, one per exceeded
        settled official-source threshold.

    See Also:
        :mod:`~application.modelo._verification_actions`:
            Calls this helper while collecting revision verification findings.
        :class:`TaxpayerProfile`:
            Owns the profile fields read by the advisory.
    """
    modelo = str(getattr(work_unit.modelo, "value", work_unit.modelo))
    if modelo not in _AFFECTED_MODELOS:
        return ()
    if not _uses_objective_estimation(profile):
        return ()
    if not _SETTLED_YEAR_MIN <= work_unit.filing_year <= _SETTLED_YEAR_MAX:
        return ()

    declared_values = tuple(
        (profile_field, parameter_id, getattr(profile, profile_field))
        for profile_field, parameter_id, _label in _PARAMETER_BY_PROFILE_FIELD
    )
    if all(raw_value is None for *_prefix, raw_value in declared_values):
        return ()

    parameters = load_legal_parameters_only(bundled_path("registry", "aeat"))
    findings: list[ModeloVerificationFinding] = []
    for profile_field, parameter_id, raw_value in declared_values:
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
                message_locale_key="application.modelo.findings.objective_estimation_exclusion_threshold_exceeded",
                message_facts={
                    "modelo_id": modelo,
                    "filing_year": work_unit.filing_year,
                    "profile_field_id": profile_field,
                    "parameter_id": parameter_id,
                    "declared": declared,
                    "threshold": threshold,
                },
                legal_refs=parameter.legal_refs,
                source_refs=_scope_source_refs(work_unit.filing_year),
            ),
        )
    return tuple(findings)


def _uses_objective_estimation(profile: TaxpayerProfile) -> bool:
    return profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA


def _require_parameter(parameters: Mapping[str, LegalParameter], parameter_id: str) -> LegalParameter:
    parameter = parameters.get(parameter_id)
    if parameter is None:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"parameter_id": parameter_id, "parameter_present": False},
        )
    return parameter


def _scope_source_refs(filing_year: int) -> tuple[SourceRefId, ...]:
    if filing_year in (2025, 2026):
        return (_AEAT_RENTA_2025_MANUAL_SOURCE_REF,)
    return ()


def _as_decimal(value: object, surface: str) -> Decimal:
    try:
        # DECIMAL-TEXT-RATIONALE-EO-THRESHOLD-COMPARISON: two callers, both
        # non-operator. ``parameter.value`` is a registry-authored legal
        # parameter, which is committed data in canonical dot-decimal form. The
        # profile-field caller reads a fact the profile write boundary already
        # promoted, the same posture the rule-3 exemption for
        # ``domain/deadlines/_profiles.py`` records -- and it is the same
        # residual: the grammar has to be enforced where the string is still a
        # string, which is that boundary and not this comparison.
        return coerce_decimal_strict(value if isinstance(value, Decimal) else str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"surface": surface, "decimal_valid": False},
        ) from exc


__all__ = ["_objective_estimation_exclusion_advisory_findings"]
