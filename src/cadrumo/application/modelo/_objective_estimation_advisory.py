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

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core.decimal.coercion import coerce_decimal_strict
from ...core.modelo import Modelo
from ...domain.calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.deadlines.models import IrpfEstimationRegime, TaxpayerProfile
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
    from ...domain.modelos.work_unit import WorkUnit

_SETTLED_YEAR_MIN = 2016
_SETTLED_YEAR_MAX = 2026
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
    authority: ValidatedRegistryAuthority | None = None,
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
        authority: Optional validated authority for resolving each threshold at
            the filing-period coordinate.

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

    findings: list[ModeloVerificationFinding] = []
    for profile_field, parameter_id, raw_value in declared_values:
        if raw_value is None:
            continue
        declared = _as_decimal(raw_value, profile_field)
        threshold_fact = _resolve_objective_estimation_threshold(
            parameter_id=parameter_id,
            filing_year=work_unit.filing_year,
            authority=authority,
        )
        threshold = _as_decimal(threshold_fact.payload.value, parameter_id)
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
                legal_refs=threshold_fact.legal_refs,
                source_refs=threshold_fact.source_refs,
            ),
        )
    return tuple(findings)


def _uses_objective_estimation(profile: TaxpayerProfile) -> bool:
    return profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA


def _resolve_objective_estimation_threshold(
    *,
    parameter_id: str,
    filing_year: int,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedScalarFact:
    """Resolve an advisory threshold at the filing-year coordinate with legal provenance."""
    from ...domain.calculations.registry.errors import RegistryError

    if authority is None:
        from ...domain.calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        resolved = authority.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=parameter_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(filing_year, 12, 31),
            )
        )
    except RegistryError as exc:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"parameter_id": parameter_id, "filing_year": filing_year, "fact_resolved": False},
        ) from exc
    if not isinstance(resolved, ResolvedScalarFact):
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"parameter_id": parameter_id, "filing_year": filing_year, "fact_scalar": False},
        )
    if not resolved.legal_refs:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"parameter_id": parameter_id, "filing_year": filing_year, "fact_legal_refs": False},
        )
    return resolved


def _as_decimal(value: object, surface: str) -> Decimal:
    try:
        # DECIMAL-TEXT-RATIONALE-EO-THRESHOLD-COMPARISON: two callers, both
        # non-operator. ``parameter.value`` is a registry-authored legal
        # parameter, which is committed data in canonical dot-decimal form. The
        # profile-field caller reads a fact the profile write boundary already
        # promoted, the same posture the rule-3 exemption for
        # ``domain/deadlines/profiles.py`` records -- and it is the same
        # residual: the grammar has to be enforced where the string is still a
        # string, which is that boundary and not this comparison.
        return coerce_decimal_strict(value if isinstance(value, Decimal) else str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"surface": surface, "decimal_valid": False},
        ) from exc


__all__ = ["_objective_estimation_exclusion_advisory_findings"]
