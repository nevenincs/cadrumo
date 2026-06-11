"""Registry-backed declaration verification.

Verifies a parsed declaracion against the engine output for the same inputs.
The :class:`ValidatedRegistryAuthority` supplies the :class:`RegistrySnapshot`
used to run the formula engine over operator-provided casilla values.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from ...adapters.inbound.declaracion import DeclaracionObservation
from ...core import Period
from ...core.decimal import coerce_decimal
from ...core.logging import get_logger
from ...core.resources import bundled_path
from ...core.time import now
from ...domain.calculations.registry import (
    InputKind,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    ValidatedRegistryAuthority,
    calculate_registry_snapshot,
)
from ._errors import VerificationError
from ._schema import (
    ClassifiedDiscrepancy,
    DiscrepancyCause,
    VerificationStatus,
    VerificationVerdict,
)

_logger = get_logger(__name__)

_UNRELIABLE_WARNING_CODES: frozenset[str] = frozenset(
    {
        "bbox-fallback",
        "ambiguous-label",
        "value-unparseable",
        "casilla-not-found",
    },
)
"""Extractor warning codes that mark a casilla extraction as low-confidence."""


class _DiscrepancyLike(Protocol):
    @property
    def casilla_id(self) -> str: ...

    @property
    def computed_value(self) -> Decimal: ...

    @property
    def user_value(self) -> Decimal: ...

    @property
    def delta(self) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class _Discrepancy:
    casilla_id: str
    computed_value: Decimal
    user_value: Decimal
    delta: Decimal


def verify_declaracion(
    declaracion: DeclaracionObservation,
    *,
    binding_values: dict[str, Decimal] | None = None,
    registry_root: Path | None = None,
) -> VerificationVerdict:
    """Compare the printed casilla values against a registry snapshot.

    Args:
        declaracion: The parsed filing returned by
            :func:`aeat.adapters.inbound.declaracion.parse_declaracion`.
        binding_values: External registry binding facts required for
            calculations that depend on facts not printed in the declaration.
        registry_root: Optional registry root override. Defaults to
            ``registry/aeat`` under the repository root.

    Returns:
        A frozen :class:`aeat.application.verification.VerificationVerdict`
        carrying the status, every
        :class:`aeat.application.verification.ClassifiedDiscrepancy`,
        the coverage fraction, a multilingual narrative, and the UTC
        timestamp the verdict was produced.

    Raises:
        VerificationError: When the registry snapshot cannot be loaded for
            the declaracion's modelo and period.
    """
    period = _parse_period(declaracion.period, declaracion.ejercicio)
    snapshot = _load_snapshot(declaracion, period=period, registry_root=registry_root)
    try:
        policy = snapshot.verification_policy()
    except RegistryValidationError as exc:
        raise VerificationError(
            translated_message="application.verification.errors.registry_policy_invalid",
            context={
                "modelo": declaracion.modelo,
                "period": declaracion.period,
                "error_type": type(exc).__name__,
            },
        ) from exc
    extracted = _decimal_extracted_values(declaracion)
    inputs = {
        casilla.id: extracted[casilla.id]
        for casilla in snapshot.revision.casillas
        if casilla.input_kind != InputKind.COMPUTED and casilla.id in extracted
    }
    # Bindings that feed a `bound` casilla are resolved by the calculation
    # engine from the casilla input itself, so they are not required as
    # external `binding_values`. Only bindings consumed purely inside
    # formulas (no bound casilla) must be supplied by the operator.
    bound_casilla_binding_ids = {
        casilla.binding
        for casilla in snapshot.revision.casillas
        if casilla.input_kind == InputKind.BOUND and casilla.binding is not None
    }
    supplied_bindings = binding_values or {}
    missing_bindings = sorted(
        binding.id
        for binding in snapshot.revision.bindings
        if binding.id not in supplied_bindings and binding.id not in bound_casilla_binding_ids
    )
    if missing_bindings:
        raise VerificationError(
            translated_message="application.verification.errors.missing_binding_values",
            context={
                "bindings": tuple(missing_bindings),
                "count": len(missing_bindings),
                "modelo": declaracion.modelo,
                "period": declaracion.period,
            },
        )
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": _period_end_date(period)},
        binding_values=supplied_bindings,
    )
    unreliable_ids = {
        warning.casilla_id
        for warning in declaracion.warnings
        if warning.casilla_id is not None and warning.code in _UNRELIABLE_WARNING_CODES
    }
    registry_casillas = {casilla.id for casilla in snapshot.revision.casillas}
    discrepancies: list[ClassifiedDiscrepancy] = []
    for casilla_id, actual in sorted(extracted.items()):
        if casilla_id in registry_casillas and casilla_id not in policy.computed_casillas:
            continue
        expected = result.values.get(casilla_id, actual)
        delta = actual - expected
        if abs(delta) <= policy.tolerance and casilla_id not in unreliable_ids and casilla_id in registry_casillas:
            continue
        discrepancies.append(
            _classify_discrepancy(
                _Discrepancy(
                    casilla_id=casilla_id,
                    computed_value=expected,
                    user_value=actual,
                    delta=delta,
                ),
                unreliable_ids=unreliable_ids,
                registry_casillas=registry_casillas,
                tolerance=policy.tolerance,
            ),
        )
    classified = tuple(discrepancies)
    coverage = _compute_coverage(declaracion, policy.computed_casillas)
    status = _derive_status(classified, coverage, min_coverage=policy.min_coverage)
    return VerificationVerdict(
        modelo=declaracion.modelo,
        period=period,
        registry_snapshot_id=f"registry:{snapshot.modelo.id}:{snapshot.revision.id}",
        verification_expectation_ids=policy.expectation_ids,
        status=status,
        discrepancies=classified,
        coverage=coverage,
        narrative=_compose_narrative(declaracion, status, classified, coverage),
        verified_at=now(),
    )


def _load_snapshot(
    declaracion: DeclaracionObservation,
    *,
    period: Period,
    registry_root: Path | None,
) -> RegistrySnapshot:
    try:
        from ...core.resources import resources

        if registry_root is None:
            authority = resources().modelos.authority
        else:
            authority = ValidatedRegistryAuthority.load(registry_root, source_root=bundled_path())
        return authority.snapshot(
            declaracion.modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
        )
    except RegistrySnapshotError as exc:
        raise VerificationError(
            translated_message="application.verification.errors.registry_snapshot_invalid",
            context={
                "modelo": declaracion.modelo,
                "period": declaracion.period,
                "ejercicio": declaracion.ejercicio or "",
                "error_type": type(exc).__name__,
            },
        ) from exc


def _decimal_extracted_values(declaracion: DeclaracionObservation) -> dict[str, Decimal]:
    extracted: dict[str, Decimal] = {}
    for value in declaracion.values:
        printed = value.printed_value
        if isinstance(printed, Decimal):
            extracted[value.casilla_id] = printed
        elif isinstance(printed, int) and not isinstance(printed, bool):
            extracted[value.casilla_id] = Decimal(printed)
    return extracted


def _parse_period(period: Period, ejercicio: str | None) -> Period:
    """Validate the typed filing period carried by the inbound declaration."""
    try:
        if ejercicio is None:
            raise ValueError("ejercicio is required for verification period mapping")
        filing_year = int(ejercicio)
        if period.filing_year != filing_year:
            raise ValueError("period filing year must match ejercicio")
        return period
    except ValueError as exc:
        raise RegistrySnapshotError(
            translated_message="application.verification.errors.period_mapping_failed",
            context={"period": period, "ejercicio": ejercicio or ""},
        ) from exc


def _period_end_date(period: Period) -> date:
    """Return the verification filing date while preserving legacy semantics."""
    code = period.registry_token
    if code in {"1T", "2T", "3T", "4T", "0A"}:
        return period.end_date
    if code in {
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
    }:
        return period.start_date
    if code == "1P":
        return date(period.filing_year, 4, 30)
    if code == "2P":
        return date(period.filing_year, 10, 31)
    if code == "3P":
        return date(period.filing_year, 12, 31)
    raise RegistrySnapshotError(
        translated_message="application.verification.errors.period_mapping_failed",
        context={"period": code, "ejercicio": str(period.filing_year)},
    )


def _classify_discrepancy(
    discrepancy: _DiscrepancyLike,
    *,
    unreliable_ids: set[str],
    registry_casillas: set[str],
    tolerance: Decimal,
) -> ClassifiedDiscrepancy:
    """Assign one of the four :class:`DiscrepancyCause` categories.

    The classifier prefers extraction-unreliability over rounding so that
    a casilla flagged by the extractor is never silently classified as a
    rounding miss. Casillas absent from the registry snapshot are routed to
    :attr:`DiscrepancyCause.UNMODELLED_RULE` regardless of delta size.
    """
    casilla_id = discrepancy.casilla_id
    delta = discrepancy.delta
    abs_delta = abs(delta)

    rationale: str
    if casilla_id in unreliable_ids:
        cause = DiscrepancyCause.EXTRACTION_UNRELIABLE
        rationale = (
            f"Casilla {casilla_id}: el extractor ha marcado este valor como poco fiable. Revisa manualmente el PDF."
        )
    elif casilla_id not in registry_casillas:
        cause = DiscrepancyCause.UNMODELLED_RULE
        rationale = f"Casilla {casilla_id}: el registro no contempla esta casilla. Se acepta el valor extraido."
    elif abs_delta < 10 * tolerance:
        cause = DiscrepancyCause.ROUNDING
        rationale = f"Casilla {casilla_id}: diferencia dentro del margen de redondeo ({abs_delta} €)."
    else:
        cause = DiscrepancyCause.CORRECTNESS_DIVERGENCE
        rationale = f"Casilla {casilla_id}: diferencia significativa ({abs_delta} EUR). Revisa el PDF o el registro."

    return ClassifiedDiscrepancy(
        casilla_id=casilla_id,
        expected=discrepancy.computed_value,
        actual=discrepancy.user_value,
        delta=delta,
        cause=cause,
        cause_rationale=rationale,
    )


def _compute_coverage(
    declaracion: DeclaracionObservation,
    expected_casillas: AbstractSet[str],
) -> float:
    """Return the fraction of registry casillas the extraction supplied.

    Returns ``0.0`` when the registry snapshot defines no casillas; this
    keeps the downstream coverage threshold in :func:`_derive_status`
    well-defined.
    """
    if not expected_casillas:
        return 0.0
    provided_ids = {v.casilla_id for v in declaracion.values}
    covered = expected_casillas & provided_ids
    return len(covered) / len(expected_casillas)


def _derive_status(
    classified: tuple[ClassifiedDiscrepancy, ...],
    coverage: float,
    *,
    min_coverage: Decimal,
) -> VerificationStatus:
    """Map discrepancies and coverage onto a :class:`VerificationStatus`.

    Returns :attr:`VerificationStatus.NEEDS_REVIEW` when any discrepancy
    has a blocking cause (extraction-unreliable or
    correctness-divergence) or when registry coverage drops below the
    active verification expectation threshold; otherwise
    :attr:`VerificationStatus.VERIFIED`.
    """
    blocking = {
        DiscrepancyCause.CORRECTNESS_DIVERGENCE,
        DiscrepancyCause.EXTRACTION_UNRELIABLE,
    }
    if any(c.cause in blocking for c in classified):
        return VerificationStatus.NEEDS_REVIEW
    coverage_decimal = coerce_decimal(coverage, default=Decimal("0")) or Decimal("0")
    if coverage_decimal < min_coverage:
        return VerificationStatus.NEEDS_REVIEW
    return VerificationStatus.VERIFIED


def _compose_narrative(
    declaracion: DeclaracionObservation,
    status: VerificationStatus,
    classified: tuple[ClassifiedDiscrepancy, ...],
    coverage: float,
) -> str:
    """Return the locale key the operator sees after a verification run."""
    if status is VerificationStatus.VERIFIED:
        return "verification.status.verified"
    return "verification.status.needs_review"


__all__ = ["verify_declaracion"]
