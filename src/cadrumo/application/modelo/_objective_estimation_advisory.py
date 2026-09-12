"""Build objective-estimation exclusion advisories from :class:`TaxpayerProfile`.

The verification path calls this helper for each revision :class:`WorkUnit` and
workflow :class:`TaxpayerProfile`. It applies only to objective-estimation
profiles for the registry-declared settled official-source range. For those
years, the helper compares the
profile-declared prior-year objective-estimation volumes against dated governed
fact thresholds and emits non-blocking
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
from ...domain.calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    MappingFactQuery,
    ResolvedEntitySetFact,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
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


_OBJECTIVE_ESTIMATION_SETTLED_MIN_FACT_ID = "lirpf-objective-estimation-settled-year-min"
_OBJECTIVE_ESTIMATION_SETTLED_MAX_FACT_ID = "lirpf-objective-estimation-settled-year-max"
_OBJECTIVE_ESTIMATION_MODEL_SCOPE_FACT_ID = "modelo-objective-estimation-advisory-scope"
_OBJECTIVE_ESTIMATION_APPLICABILITY_MAP_FACT_ID = "lirpf-objective-estimation-exclusion-applicability-map"


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
    # fact-relocation: objective-estimation scope and applicability are resolved through registry authority; authored fact publication remains external.
    modelo = str(getattr(work_unit.modelo, "value", work_unit.modelo))
    if not _uses_objective_estimation(profile):
        return ()

    settled_year_min_fact = _resolve_objective_estimation_threshold(
        fact_id=_OBJECTIVE_ESTIMATION_SETTLED_MIN_FACT_ID,
        filing_year=work_unit.filing_year,
        authority=authority,
    )
    settled_year_max_fact = _resolve_objective_estimation_threshold(
        fact_id=_OBJECTIVE_ESTIMATION_SETTLED_MAX_FACT_ID,
        filing_year=work_unit.filing_year,
        authority=authority,
    )
    settled_year_min = _as_integer(
        settled_year_min_fact.payload.value,
        _OBJECTIVE_ESTIMATION_SETTLED_MIN_FACT_ID,
    )
    settled_year_max = _as_integer(
        settled_year_max_fact.payload.value,
        _OBJECTIVE_ESTIMATION_SETTLED_MAX_FACT_ID,
    )
    if not settled_year_min <= work_unit.filing_year <= settled_year_max:
        return ()

    affected_modelos_fact = _resolve_objective_estimation_model_scope(
        filing_year=work_unit.filing_year,
        authority=authority,
    )
    if modelo not in affected_modelos_fact.payload.entities:
        return ()

    profile_field_fact_map = _resolve_objective_estimation_profile_fact_map(
        filing_year=work_unit.filing_year,
        authority=authority,
    )
    declared_values = tuple(
        (profile_field, fact_id, getattr(profile, profile_field))
        for profile_field, fact_id in _profile_field_fact_pairs(profile_field_fact_map)
    )

    if all(raw_value is None for *_prefix, raw_value in declared_values):
        return ()

    findings: list[ModeloVerificationFinding] = []
    for profile_field, fact_id, raw_value in declared_values:
        if raw_value is None:
            continue
        declared = _as_decimal(raw_value, profile_field)
        threshold_fact = _resolve_objective_estimation_threshold(
            fact_id=fact_id,
            filing_year=work_unit.filing_year,
            authority=authority,
        )
        threshold = _as_decimal(threshold_fact.payload.value, fact_id)
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
                    "fact_id": fact_id,
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


def _resolve_objective_estimation_model_scope(
    *,
    filing_year: int,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedEntitySetFact:
    """Resolve the Modelo scope entity set at the filing-period coordinate."""
    from ...domain.calculations.registry.errors import RegistryError

    if authority is None:
        from ...domain.calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        resolved = authority.resolve_governed_fact(
            EntitySetFactQuery(
                fact_id=_OBJECTIVE_ESTIMATION_MODEL_SCOPE_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(filing_year, 12, 31),
            ),
        )
    except RegistryError as exc:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={
                "fact_id": _OBJECTIVE_ESTIMATION_MODEL_SCOPE_FACT_ID,
                "filing_year": filing_year,
                "fact_resolved": False,
            },
        ) from exc
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={
                "fact_id": _OBJECTIVE_ESTIMATION_MODEL_SCOPE_FACT_ID,
                "filing_year": filing_year,
                "fact_entity_set": False,
            },
        )
    if not resolved.legal_refs:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={
                "fact_id": _OBJECTIVE_ESTIMATION_MODEL_SCOPE_FACT_ID,
                "filing_year": filing_year,
                "fact_legal_refs": False,
            },
        )
    return resolved


def _resolve_objective_estimation_profile_fact_map(
    *,
    filing_year: int,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedMappingFact:
    """Resolve the profile-field to threshold-fact mapping from registry authority."""
    from ...domain.calculations.registry.errors import RegistryError

    if authority is None:
        from ...domain.calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        resolved = authority.resolve_governed_fact(
            MappingFactQuery(
                fact_id=_OBJECTIVE_ESTIMATION_APPLICABILITY_MAP_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(filing_year, 12, 31),
            ),
        )
    except RegistryError as exc:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={
                "fact_id": _OBJECTIVE_ESTIMATION_APPLICABILITY_MAP_FACT_ID,
                "filing_year": filing_year,
                "fact_resolved": False,
            },
        ) from exc
    if not isinstance(resolved, ResolvedMappingFact):
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={
                "fact_id": _OBJECTIVE_ESTIMATION_APPLICABILITY_MAP_FACT_ID,
                "filing_year": filing_year,
                "fact_mapping": False,
            },
        )
    if not resolved.legal_refs:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={
                "fact_id": _OBJECTIVE_ESTIMATION_APPLICABILITY_MAP_FACT_ID,
                "filing_year": filing_year,
                "fact_legal_refs": False,
            },
        )
    return resolved


def _profile_field_fact_pairs(resolved: ResolvedMappingFact) -> tuple[tuple[str, str], ...]:
    """Extract profile-field/fact-id pairs while ignoring descriptive label entries."""
    pairs: list[tuple[str, str]] = []
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise ModeloValidationError(
                translated_message="errors.error.error_modelos_validation",
                context={"fact_id": resolved.fact_id, "fact_mapping_entries": False},
            )
        if entry.key.endswith(".label"):
            continue
        pairs.append((entry.key, entry.value))
    if not pairs:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"fact_id": resolved.fact_id, "fact_mapping_entries": False},
        )
    return tuple(pairs)


def _resolve_objective_estimation_threshold(
    *,
    fact_id: str,
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
                fact_id=fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(filing_year, 12, 31),
            )
        )
    except RegistryError as exc:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"fact_id": fact_id, "filing_year": filing_year, "fact_resolved": False},
        ) from exc
    if not isinstance(resolved, ResolvedScalarFact):
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"fact_id": fact_id, "filing_year": filing_year, "fact_scalar": False},
        )
    if not resolved.legal_refs:
        raise ModeloValidationError(
            translated_message="errors.error.error_modelos_validation",
            context={"fact_id": fact_id, "filing_year": filing_year, "fact_legal_refs": False},
        )
    return resolved


def _as_integer(value: object, surface: str) -> int:
    if type(value) is int:
        return value
    raise ModeloValidationError(
        translated_message="errors.error.error_modelos_validation",
        context={"surface": surface, "integer_valid": False},
    )


def _as_decimal(value: object, surface: str) -> Decimal:
    try:
        # DECIMAL-TEXT-RATIONALE-EO-THRESHOLD-COMPARISON: two callers, both
        # non-operator. A governed fact payload is committed data in canonical
        # dot-decimal form. The
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
