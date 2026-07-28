"""Registry-backed declaration verification.

Verifies a parsed declaracion against the engine output for the same inputs.
The :class:`ValidatedRegistryAuthority` supplies the :class:`RegistrySnapshot`
used to run the formula engine over operator-provided casilla values.

The verifier consumes :class:`InboundDeclaracionObservation` values from the inbound
parser, selects the law-determined registry revision for the filing period,
calculates the snapshot with supplied :class:`BindingId` values, and emits a
local :class:`VerificationVerdict`. It does not perform live AEAT reads or
filing-state reconciliation.
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from ...adapters.inbound.declaracion import InboundDeclaracionObservation
from ...core import Period
from ...core.decimal import coerce_decimal
from ...core.logging import get_logger
from ...core.resources import bundled_path
from ...core.time import now
from ...domain.calculations.registry import (
    BindingId,
    CasillaId,
    InputKind,
    RegistrySnapshot,
    RegistrySnapshotError,
    RegistryValidationError,
    ValidatedRegistryAuthority,
    calculate_registry_snapshot,
    declared_casilla_ids,
)
from ...domain.period import calculation_filing_date
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
    def casilla_id(self) -> CasillaId: ...

    @property
    def computed_value(self) -> Decimal: ...

    @property
    def user_value(self) -> Decimal: ...

    @property
    def delta(self) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class _Discrepancy:
    casilla_id: CasillaId
    computed_value: Decimal
    user_value: Decimal
    delta: Decimal


def verify_declaracion(
    declaracion: InboundDeclaracionObservation,
    *,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    registry_root: Path | None = None,
) -> VerificationVerdict:
    """Compare the printed casilla values against a registry snapshot.

    **Deliberately unwired reference implementation. Do not delete as dead code.**

    This function has no production caller and no entrypoint surface, which is
    what makes it read as an abandoned build on a reachability sweep. It is
    not. It is the canonical statement of the registry-declared reconciliation
    scope -- the fold of a revision's verification expectations into a
    :class:`~domain.calculations.registry.RegistryVerificationPolicy`, and the
    rule that ``computed_casilla_ids`` is compared in full while
    ``reconcile_when_present_casilla_ids`` is compared only where the document
    actually prints it -- and other modules define their own behaviour by
    pointing here rather than restating it.

    Deleting it would leave those citations resolving to nothing, so the
    reference is load-bearing even though the call graph is empty. Wiring it
    remains available and is not foreclosed; it needs an operator verb designed
    under the current two-family command vocabulary, which is a separate
    decision from this one.

    Callers that cite it, confirmed by search rather than assumed:

    - :mod:`application.modelo._reconcile` and
      :mod:`application.modelo._reconcile_casilla` describe their own scoping
      as "the same policy" and as mirroring this treatment. They are the two
      production modules that depend on this definition.
    - :mod:`application.verification._schema` cites it for a different reason:
      its :class:`DiscrepancyCause` categories mirror this classifier, not its
      scope.
    - Seven Modelo 100 grounded-oracle tests under
      ``domain.calculations.registry.tests`` describe the projection they
      assert against as "the projection ``verify_declaracion`` consumes".

    The enrolled reconcile path is not a replacement and retiring this in its
    favour would lose a capability rather than remove a duplicate: it compares
    against a persisted :class:`~domain.modelos.CalculationRevision`, where
    this computes fresh from the printed inputs and needs no revision to exist.

    Args:
        declaracion: The parsed filing returned by
            :func:`cadrumo.adapters.inbound.declaracion.parse_declaracion`.
        binding_values: External :class:`BindingId` facts required for
            calculations that depend on facts not printed in the declaration.
        registry_root: Optional registry root override. Defaults to
            ``registry/aeat`` under the repository root.

    Returns:
        A frozen :class:`VerificationVerdict` carrying the status, every
        :class:`ClassifiedDiscrepancy`, the coverage fraction, a multilingual
        narrative key, and the UTC timestamp the verdict was produced.

    Raises:
        VerificationError: When the registry snapshot cannot be loaded for
            the declaracion's modelo and period.
    """
    period = _parse_period(declaracion.period, declaracion.ejercicio)
    snapshot = _load_snapshot(declaracion, period=period, registry_root=registry_root)
    _assert_snapshot_ref_matches(declaracion, snapshot, period=period)
    try:
        policy = snapshot.verification_policy()
    except RegistryValidationError as exc:
        raise VerificationError(
            translated_message="application.verification.errors.registry_policy_invalid",
            context={
                "modelo": declaracion.modelo,
                "period": _period_context(period),
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
                "period": _period_context(period),
            },
        )
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": calculation_filing_date(period)},
        binding_values=supplied_bindings,
    )
    unreliable_ids = {
        warning.casilla_id
        for warning in declaracion.warnings
        if warning.casilla_id is not None and warning.code in _UNRELIABLE_WARNING_CODES
    }
    registry_casilla_ids = declared_casilla_ids(snapshot.revision)
    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    discrepancies: list[ClassifiedDiscrepancy] = []
    for casilla_id, actual in sorted(extracted.items()):
        if casilla_id in registry_casilla_ids and casilla_id not in reconciled_casilla_ids:
            continue
        expected = result.values.get(casilla_id, actual)
        delta = actual - expected
        if abs(delta) <= policy.tolerance and casilla_id not in unreliable_ids and casilla_id in registry_casilla_ids:
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
                registry_casilla_ids=registry_casilla_ids,
                tolerance=policy.tolerance,
            ),
        )
    classified = tuple(discrepancies)
    coverage = _compute_coverage(declaracion, policy.computed_casilla_ids)
    status = _derive_status(classified, coverage, min_coverage=policy.min_coverage)
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )
    return VerificationVerdict(
        modelo=declaracion.modelo,
        period=period,
        registry_snapshot_id=f"registry:{snapshot.modelo.id}:{snapshot.revision.id}",
        verification_expectation_ids=policy.expectation_ids,
        status=status,
        discrepancies=classified,
        coverage=coverage,
        externally_grounded_casilla_ids=tuple(sorted(externally_grounded)),
        independently_grounded_fraction=independently_grounded_fraction,
        narrative=_compose_narrative(declaracion, status, classified, coverage),
        verified_at=now(),
    )


def _load_snapshot(
    declaracion: InboundDeclaracionObservation,
    *,
    period: Period,
    registry_root: Path | None,
) -> RegistrySnapshot:
    """Load the :class:`RegistrySnapshot` selected by declaracion modelo and period."""
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
                "period": _period_context(period),
                "ejercicio": declaracion.ejercicio or "",
                "error_type": type(exc).__name__,
            },
        ) from exc


def _assert_snapshot_ref_matches(
    declaracion: InboundDeclaracionObservation,
    snapshot: RegistrySnapshot,
    *,
    period: Period,
) -> None:
    """Assert the observation's stamped ref matches law-determined resolution."""
    ref = declaracion.registry_snapshot_ref
    observed = (ref.modelo, ref.revision_id, ref.modelo_year, ref.period)
    resolved = (snapshot.modelo.id, snapshot.revision.id, snapshot.filing_year, snapshot.period)
    if observed == resolved:
        return
    raise VerificationError(
        translated_message="application.verification.errors.registry_snapshot_ref_mismatch",
        context={
            "modelo": declaracion.modelo,
            "period": _period_context(period),
            "observed_ref": _snapshot_ref_context(*observed),
            "resolved_ref": _snapshot_ref_context(*resolved),
        },
    )


def _snapshot_ref_context(modelo: str, revision_id: str, modelo_year: int, period: str) -> str:
    """Return an operator-facing registry snapshot coordinate."""
    return f"registry:{modelo}:{revision_id}:{modelo_year}:{period}"


def _decimal_extracted_values(declaracion: InboundDeclaracionObservation) -> dict[CasillaId, Decimal]:
    """Return decimal printed values keyed by canonical :class:`CasillaId`."""
    extracted: dict[CasillaId, Decimal] = {}
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
        raise VerificationError(
            translated_message="application.verification.errors.period_mapping_failed",
            context={"period": _period_context(period), "ejercicio": ejercicio or ""},
        ) from exc


def _period_context(period: Period) -> str:
    """Return the primitive operator-facing period label for diagnostics."""
    return str(period)


def _classify_discrepancy(
    discrepancy: _DiscrepancyLike,
    *,
    unreliable_ids: AbstractSet[CasillaId],
    registry_casilla_ids: AbstractSet[CasillaId],
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
    elif casilla_id not in registry_casilla_ids:
        cause = DiscrepancyCause.UNMODELLED_RULE
        rationale = f"Casilla {casilla_id}: el registro no contempla esta casilla. Revisa el modelo antes de verificar."
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
    declaracion: InboundDeclaracionObservation,
    expected_casilla_ids: AbstractSet[CasillaId],
) -> float:
    """Return the fraction of registry casillas the extraction supplied.

    Returns ``0.0`` when the registry snapshot defines no casillas; this
    keeps the downstream coverage threshold in :func:`_derive_status`
    well-defined.
    """
    if not expected_casilla_ids:
        return 0.0
    provided_ids = {v.casilla_id for v in declaracion.values}
    covered = expected_casilla_ids & provided_ids
    return len(covered) / len(expected_casilla_ids)


def _derive_status(
    classified: tuple[ClassifiedDiscrepancy, ...],
    coverage: float,
    *,
    min_coverage: Decimal,
) -> VerificationStatus:
    """Map discrepancies and coverage onto a :class:`VerificationStatus`.

    Returns :attr:`VerificationStatus.NEEDS_REVIEW` when any discrepancy
    has a blocking cause (extraction-unreliable, unmodelled rule, or
    correctness-divergence) or when registry coverage drops below the
    active verification expectation threshold; otherwise
    :attr:`VerificationStatus.VERIFIED`.
    """
    blocking = {
        DiscrepancyCause.CORRECTNESS_DIVERGENCE,
        DiscrepancyCause.EXTRACTION_UNRELIABLE,
        DiscrepancyCause.UNMODELLED_RULE,
    }
    if any(c.cause in blocking for c in classified):
        return VerificationStatus.NEEDS_REVIEW
    coverage_decimal = coerce_decimal(coverage, default=Decimal("0")) or Decimal("0")
    if coverage_decimal < min_coverage:
        return VerificationStatus.NEEDS_REVIEW
    return VerificationStatus.VERIFIED


def _compose_narrative(
    declaracion: InboundDeclaracionObservation,
    status: VerificationStatus,
    classified: tuple[ClassifiedDiscrepancy, ...],
    coverage: float,
) -> str:
    """Return the locale key the operator sees after a verification run."""
    if status is VerificationStatus.VERIFIED:
        return "verification.status.verified"
    return "verification.status.needs_review"


__all__ = ["verify_declaracion"]
