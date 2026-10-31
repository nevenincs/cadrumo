"""Compare filed receipt totals and declaration casillas with saved calculations.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CadrumoError
from .reconcile_casilla import CasillaDivergence, CasillaDivergenceKind, detect_casilla_divergences
from .reconciliation_records import ModeloReconciliationAdvisory, ModeloReconciliationDiff, ModeloReconciliationDiffKind

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
    from ...domain.calculations.registry.schema_verification import RegistryVerificationPolicy
    from ...domain.justificante.schema import Justificante
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit
    from .reconciliation_parsing import ReconciliationDeclaracionObservation


class ReconciliationDeclaracionSourceUnsupportedError(CadrumoError):
    """Raised when a declaración reconcile targets a modelo not yet enrolled.

    Casilla-level declaración reconciliation is enrolled one modelo at a time
    through the registry role
    :data:`cadrumo.application.modelo.reconciliation._DECLARATION_RECONCILE_ROLE`; an unenrolled modelo
    refuses cleanly rather than silently degrading to a header-only compare.
    """


def _totals_not_reconciled(reason: str, *, modelo: str, detail: str = "") -> ModeloReconciliationAdvisory:
    """Advisory: the filed totals were not value-reconciled against the engine.

    Emitted when the revision declares no ``reconciliation_total_casilla_ids``
    map, no persisted calculation revision exists, the receipt printed no total,
    or the receipt's total kind is unmapped. The verdict stays scoped to
    identity; this advisory prevents a false green by disclosing that the filed
    amount was not checked against the computed result.
    """
    context = {"reason": reason, "modelo": modelo}
    if detail:
        context["detail"] = detail
    return ModeloReconciliationAdvisory(
        code="totals_not_reconciled",
        message=(
            f"filed totals were not reconciled against the computed result for modelo {modelo} "
            f"({reason}); verdict reflects receipt identity only"
        ),
        context=context,
    )


def reconcile_receipt_totals(
    *,
    work_unit: WorkUnit,
    justificante: Justificante,
    revision: CalculationRevision | None,
    operation: PinnedAuthorityOperation,
) -> tuple[list[ModeloReconciliationDiff], list[ModeloReconciliationAdvisory]]:
    """Reconcile the receipt total against the canonical computed result casilla.

    Resolves the registry snapshot for ``work_unit``, reads the
    ``reconciliation_total_casilla_ids`` map its verification expectations
    declare (the same map ``calculation_result_summary`` consumes), and
    compares the receipt's printed total against
    ``revision.casilla_values[target_casilla]`` at the expectation's declared
    tolerance. ``revision`` is the persisted revision the caller asserts was
    presented; ``None`` means no such revision exists. A divergence is a typed
    ``total`` diff carrying the reconciling expectation's ``legal_refs`` /
    ``source_refs``. Every branch that cannot perform the comparison returns a
    ``totals_not_reconciled`` advisory instead of silently passing.

    Args:
        work_unit: The filing coordinate whose snapshot is resolved.
        justificante: The stored receipt carrying the printed total.
        revision: The presented
            :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
            or ``None`` when none exists.
        operation: The generation-pinned authority the snapshot is read under.

    Returns:
        The typed diffs and advisories the comparison produced.
    """
    modelo = str(work_unit.modelo)
    try:
        targets = _total_targets_for_work_unit(work_unit, operation=operation)
    except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
        return [], [_totals_not_reconciled("snapshot_unavailable", modelo=modelo)]
    if not targets:
        return [], [_totals_not_reconciled("map_not_declared", modelo=modelo)]

    receipt_kind, receipt_total = _receipt_total(justificante)
    if receipt_kind is None or receipt_total is None:
        return [], [_totals_not_reconciled("receipt_has_no_total", modelo=modelo)]

    target = targets.get(receipt_kind)
    if target is None:
        return [], [_totals_not_reconciled("receipt_kind_unmapped", modelo=modelo, detail=receipt_kind)]

    computed = revision.casilla_values.get(target.casilla_id) if revision is not None else None
    if computed is None:
        return [], [_totals_not_reconciled("no_persisted_revision", modelo=modelo)]

    # The receipt prints a non-negative magnitude under its ingresar/devolver
    # heading; the result casilla carries its own sign convention. Compare the
    # magnitudes so a devolver casilla stored negative still reconciles, while a
    # genuine sign flip (result 0 vs a printed total) still surfaces.
    if abs(receipt_total - abs(computed)) <= target.tolerance:
        return [], []
    return (
        [
            ModeloReconciliationDiff(
                field_name=f"total_{receipt_kind}",
                work_unit_value=_format_decimal(abs(computed)),
                evidence_value=_format_decimal(receipt_total),
                kind=f"total_{receipt_kind}_mismatch",
                diff_kind=ModeloReconciliationDiffKind.TOTAL,
                legal_refs=target.legal_refs,
                source_refs=target.source_refs,
            ),
        ],
        [],
    )


class _TotalTarget:
    """A declared receipt-total → canonical result-casilla reconciliation target."""

    __slots__ = ("casilla_id", "legal_refs", "source_refs", "tolerance")

    def __init__(
        self,
        *,
        casilla_id: str,
        tolerance: Decimal,
        legal_refs: tuple[str, ...],
        source_refs: tuple[str, ...],
    ) -> None:
        self.casilla_id = casilla_id
        self.tolerance = tolerance
        self.legal_refs = legal_refs
        self.source_refs = source_refs


def _total_targets_for_work_unit(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[str, _TotalTarget]:
    """Collect the ``{ingresar|devolver: _TotalTarget}`` map from the snapshot.

    First declaration wins per kind (mirroring ``calculation_result_summary``),
    so a revision that repeats a total across expectations resolves
    deterministically to one target casilla.
    """
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    snapshot = resolve_registry_snapshot_for_work_unit(work_unit, operation=operation)
    # Deliberately NOT folded through fold_reconciliation_total_casilla_ids.
    # That fold answers "which casilla is the total for this kind" and returns
    # the mapping alone; this site needs the tolerance, legal_refs and
    # source_refs of the EXPECTATION THAT DECLARED THE KIND, and the fold
    # discards that linkage. Consuming it here would mean re-deriving the owning
    # expectation from the casilla id, which is the coupling the fold removes.
    targets: dict[str, _TotalTarget] = {}
    for expectation in snapshot.revision.verification_expectations:
        for kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
            targets.setdefault(
                str(kind),
                _TotalTarget(
                    casilla_id=casilla_id,
                    tolerance=Decimal(expectation.tolerance),
                    legal_refs=tuple(expectation.legal_refs),
                    source_refs=tuple(expectation.source_refs),
                ),
            )
    return targets


def _declaracion_registry_context(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[RegistrySnapshot, RegistryVerificationPolicy] | None:
    """Resolve the registry snapshot and folded policy for a declaration compare."""
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    try:
        snapshot = resolve_registry_snapshot_for_work_unit(work_unit, operation=operation)
        policy = snapshot.verification_policy()
    except (LookupError, KeyError, AttributeError, ValueError, CadrumoError):
        return None
    return snapshot, policy


def _declaracion_reconcilable_scope(
    policy: RegistryVerificationPolicy,
    *,
    revision_casillas: Mapping[str, CasillaDefinition],
) -> dict[str, None]:
    """Return computed casillas that have an observable printed counterpart.

    A casilla carrying an export exemption files no slot on the official
    record, so the printed declaración cannot carry it either and the
    extraction profile never targets it. Comparing it against a PDF asserts a
    comparison this surface cannot perform: ``filed`` can never hold the id,
    so every such casilla yields ``MISSING_IN_FILED`` whatever the taxpayer
    declared, including when the computed value is non-zero.

    Excluding them silences nothing observable. The two FEEDS_ADDRESSED_CASILLA
    cases are already reconciled under the numbered box their projection
    addresses, while the NOT_IN_RECORD_DESIGN cases have no printed
    counterpart to observe. Deliberately do not collapse them into id
    alignment: the semantic source is exempt precisely because it feeds the
    addressed box, so merging the two ids would leave that exemption with no
    subject.
    """
    return {
        casilla_id: None
        for casilla_id in policy.computed_casilla_ids
        if getattr(revision_casillas.get(casilla_id), "export_exemption_reason", None) is None
    }


def _declaracion_present_scope(
    policy: RegistryVerificationPolicy,
    *,
    computed_values: Mapping[str, Decimal],
    filed_values: Mapping[str, Decimal],
) -> dict[str, None]:
    """Return reconcile-when-present casillas carried by both sides."""
    return {
        casilla_id: None
        for casilla_id in policy.reconcile_when_present_casilla_ids
        if casilla_id in computed_values and casilla_id in filed_values
    }


def _declaracion_divergences(
    *,
    policy: RegistryVerificationPolicy,
    revision_casillas: Mapping[str, CasillaDefinition],
    computed_values: Mapping[str, Decimal],
    filed_values: Mapping[str, Decimal],
) -> tuple[CasillaDivergence, ...]:
    """Compare required casillas, then optional casillas present on both sides."""
    reconcilable = _declaracion_reconcilable_scope(policy, revision_casillas=revision_casillas)
    divergences = detect_casilla_divergences(
        computed=computed_values,
        filed=filed_values,
        scope=reconcilable,
        tolerance=policy.tolerance,
    )
    present_on_both = _declaracion_present_scope(
        policy,
        computed_values=computed_values,
        filed_values=filed_values,
    )
    if present_on_both:
        divergences += detect_casilla_divergences(
            computed=computed_values,
            filed=filed_values,
            scope=present_on_both,
            tolerance=policy.tolerance,
        )
    return divergences


def reconcile_declaracion_casillas(
    *,
    revision: CalculationRevision | None,
    work_unit: WorkUnit,
    declaracion: ReconciliationDeclaracionObservation,
    operation: PinnedAuthorityOperation,
) -> tuple[list[ModeloReconciliationDiff], list[ModeloReconciliationAdvisory]]:
    """Compare every registry-reconciled casilla against the filed declaración.

    Resolves the registry snapshot for ``work_unit`` and folds its verification
    expectations into the canonical
    :class:`~domain.calculations.registry.schema_verification.RegistryVerificationPolicy` — the
    registry's own declared reconciliation scope, never an ad
    hoc casilla list. ``computed_casilla_ids`` (the coverage-gated set) is
    compared in full, so a casilla the computed revision resolved but the
    declaración omitted surfaces as ``MISSING_IN_FILED``.
    ``reconcile_when_present_casilla_ids`` is value-reconciled only when the
    declaración actually prints it (omission is
    legitimate — that is exactly why the casilla is excluded from the coverage
    denominator — so it never surfaces ``MISSING_IN_FILED``).

    Reads the persisted filed / verified
    :class:`~CalculationRevision` (never a fresh
    calculation), decodes the declaración's
    :class:`ReconciliationCasillaObservation` rows into decimals, and
    delegates the comparison to
    :func:`application.modelo.reconcile_casilla.detect_casilla_divergences`.
    Every branch that cannot perform the comparison returns a
    ``totals_not_reconciled``-shaped advisory instead of silently passing
    (``no-silent-under-declaration``); the advisory code is reused across the
    total and casilla surfaces because both disclose the same thing — a
    comparison the reconcile could not perform.
    """
    return reconcile_casilla_values(
        revision=revision,
        work_unit=work_unit,
        filed_values=_decimal_declaracion_values(declaracion),
        operation=operation,
    )


def reconcile_casilla_values(
    *,
    revision: CalculationRevision | None,
    work_unit: WorkUnit,
    filed_values: Mapping[str, Decimal],
    operation: PinnedAuthorityOperation,
) -> tuple[list[ModeloReconciliationDiff], list[ModeloReconciliationAdvisory]]:
    """Share the registry comparison between parsed PDFs and stored file observations.

    Takes ``revision`` as a :class:`CalculationRevision`.
    """
    modelo = str(work_unit.modelo)
    registry_context = _declaracion_registry_context(work_unit, operation=operation)
    if registry_context is None:
        return [], [_totals_not_reconciled("snapshot_unavailable", modelo=modelo)]
    snapshot, policy = registry_context
    if not policy.computed_casilla_ids and not policy.reconcile_when_present_casilla_ids:
        return [], [_totals_not_reconciled("map_not_declared", modelo=modelo)]

    if revision is None:
        return [], [_totals_not_reconciled("no_persisted_revision", modelo=modelo)]

    from ...domain.calculations.registry.casilla_membership import casillas_by_id

    revision_casillas = casillas_by_id(snapshot.revision)
    computed_values: Mapping[str, Decimal] = revision.casilla_values
    if not _declaracion_reconcilable_scope(
        policy, revision_casillas=revision_casillas
    ) and not _declaracion_present_scope(policy, computed_values=computed_values, filed_values=filed_values):
        return [], [_totals_not_reconciled("no_comparable_casillas", modelo=modelo)]
    divergences = _declaracion_divergences(
        policy=policy,
        revision_casillas=revision_casillas,
        computed_values=computed_values,
        filed_values=filed_values,
    )
    diffs = [_casilla_divergence_diff(divergence, revision_casillas=revision_casillas) for divergence in divergences]
    return diffs, []


_CASILLA_DIVERGENCE_KIND_TOKEN: dict[CasillaDivergenceKind, str] = {
    CasillaDivergenceKind.VALUE_MISMATCH: "casilla_value_mismatch",
    CasillaDivergenceKind.MISSING_IN_FILED: "casilla_missing_in_filed",
    CasillaDivergenceKind.EXTRA_IN_FILED: "casilla_extra_in_filed",
}


def _casilla_divergence_diff(
    divergence: CasillaDivergence,
    *,
    revision_casillas: Mapping[str, CasillaDefinition],
) -> ModeloReconciliationDiff:
    """Project one :class:`CasillaDivergence` onto a typed :class:`ModeloReconciliationDiff`.

    Grounds the diff in the casilla's own registry-declared ``legal_refs`` /
    ``source_refs``, so the per-casilla divergence carries the same legal
    grounding a ``total`` diff carries (``aeat-calculation-grounding``).

    A divergence is always drawn from ``computed_casilla_ids``, so its casilla
    is always declared in the revision. Falling back to empty grounding when the
    lookup missed would emit a value diff that claims no legal basis, which
    ``ModeloReconciliationDiff`` now refuses; the miss is surfaced here as a
    named failure rather than laundered into an ungrounded record.

    Raises:
        ReconciliationDeclaracionSourceUnsupportedError: The divergence names a
            casilla the revision does not declare, so no grounding exists.
    """
    casilla = revision_casillas.get(divergence.casilla_id)
    if casilla is None:
        raise ReconciliationDeclaracionSourceUnsupportedError(
            translated_message="errors.refused.reconciliation_declaration_source_unsupported",
            context={
                "casilla_id": divergence.casilla_id,
                "declared_by_revision": False,
            },
        )
    legal_refs = tuple(casilla.legal_refs)
    source_refs = tuple(casilla.source_refs)
    return ModeloReconciliationDiff(
        field_name=divergence.casilla_id,
        work_unit_value=_format_decimal(divergence.computed_value) if divergence.computed_value is not None else "",
        evidence_value=_format_decimal(divergence.filed_value) if divergence.filed_value is not None else "",
        kind=_CASILLA_DIVERGENCE_KIND_TOKEN[divergence.kind],
        diff_kind=ModeloReconciliationDiffKind.CASILLA,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _decimal_declaracion_values(declaracion: ReconciliationDeclaracionObservation) -> dict[str, Decimal]:
    """Return decimal printed values keyed by canonical casilla id.

    A declaración's :class:`ReconciliationCasillaObservation` rows may
    carry a ``Decimal``, an ``int``, or a non-numeric printed value (text/enum
    casillas); only the numeric rows participate in a value-level reconcile.
    """
    values: dict[str, Decimal] = {}
    for extracted in declaracion.values:
        printed = extracted.printed_value
        if isinstance(printed, Decimal):
            values[extracted.casilla_id] = printed
        elif isinstance(printed, int) and not isinstance(printed, bool):
            values[extracted.casilla_id] = Decimal(printed)
    return values


def _receipt_total(justificante: Justificante) -> tuple[str | None, Decimal | None]:
    """Return the receipt's printed total as a ``(kind, magnitude)`` pair.

    A justificante prints at most one of ``total_a_ingresar`` /
    ``total_a_devolver``. ``ingresar`` takes precedence when both are present.
    """
    if justificante.total_a_ingresar is not None:
        return "ingresar", abs(justificante.total_a_ingresar)
    if justificante.total_a_devolver is not None:
        return "devolver", abs(justificante.total_a_devolver)
    return None, None


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"
