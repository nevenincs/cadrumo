"""Calculate-path collector for registry-authored official-box advisories.

The collector is intentionally revision-driven: it scans the
:class:`ModeloRevision` for ADVISORY ``implies_any_nonzero`` verification
predicates and mirrors the same predicate shape as a non-blocking
:class:`aeat.application.aggregation.CalculationSourceDiagnostic` on the
calculate path. The verification predicate remains the single source of truth
for any total-to-official-box mapping, so calculate diagnostics and verify
findings cannot drift.

Modelo 303's 2023-y-siguientes revision used this mechanism in Stage 1, when
ledger-backed semantic totals could be positive while manual official
Diseño-de-Registros cuota boxes stayed zero. Stage 2 now projects those boxes
from their semantic sources and retired the Stage-1 ADVISORY predicates, so this
collector normally emits no M303 official-box diagnostics for that revision.

See Also:
    :mod:`aeat.application.modelo._calculation_diagnostics`
        Post-calculation coordinator that calls this collector with the engine
        casilla values.
    :mod:`aeat.application.modelo._verification_actions`
        Verification predicate parser/evaluator whose ``implies_any_nonzero``
        shape this collector mirrors.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...domain.calculations.registry import CasillaId, ModeloRevision
from ..aggregation import CalculationSourceDiagnostic

__all__ = ["collect_official_box_unpopulated_diagnostics"]


def collect_official_box_unpopulated_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for ADVISORY ``implies_any_nonzero`` predicates that fire.

    A predicate fires when its antecedent (a computed total) is strictly
    positive while every listed consequent (the official numbered boxes) is
    zero. Each fired predicate yields one
    :class:`aeat.application.aggregation.CalculationSourceDiagnostic` with
    ``reason = "official_box_unpopulated"``, naming the positive antecedent
    casilla and the unpopulated official boxes so the operator-facing surface
    can instruct the transcription.

    Args:
        revision: The :class:`ModeloRevision` whose ADVISORY
            ``implies_any_nonzero`` predicates are evaluated. If the revision
            has retired those predicates, no diagnostic is emitted.
        casilla_values: The computed engine values keyed by ``CasillaId`` and
            used to test the predicates, so both the semantic antecedent (e.g.
            ``iva.cuota-devengada-total``) and the official box ids (e.g.
            ``09``) resolve.

    See Also:
        :func:`aeat.application.modelo._verification_actions._evaluate_predicate_expression`
            Verification-side evaluator for the same predicate DSL.
    """
    # Lazy import to avoid a module-load cycle: _verification_actions imports from
    # _calculation_actions, which imports this module at top level. The predicate
    # regex + parser are the single source of truth for the predicate DSL shape.
    from ._verification_actions import (
        _PREDICATE_IMPLIES_ANY_NONZERO,
        _parse_predicate_casilla_ids,
    )

    diagnostics: list[CalculationSourceDiagnostic] = []
    for predicate in revision.verification_predicates:
        if predicate.finding_kind != "ADVISORY":
            continue
        match = _PREDICATE_IMPLIES_ANY_NONZERO.match(predicate.expression.strip())
        if match is None:
            continue
        ids = _parse_predicate_casilla_ids(match.group("ids"))
        if len(ids) < 2:
            continue
        antecedent_id = ids[0]
        consequent_ids = ids[1:]
        antecedent = casilla_values.get(antecedent_id, Decimal(0))
        if antecedent <= Decimal(0):
            continue
        if any(casilla_values.get(cid, Decimal(0)) != Decimal(0) for cid in consequent_ids):
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="official_box_unpopulated",
                source_kind="official_diseno_boxes",
                message=(
                    f"computed total {antecedent_id!r} = {antecedent} is positive but the official "
                    f"Diseño-de-Registros boxes {consequent_ids!r} are all zero; the calculate path does "
                    f"not auto-populate the official numbered boxes — transcribe the cuota before filing"
                ),
                casilla_id=antecedent_id,
            ),
        )
    return tuple(diagnostics)
