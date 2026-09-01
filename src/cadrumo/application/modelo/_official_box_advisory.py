"""Calculate-path collector for registry-authored official-box advisories.

The collector is intentionally revision-driven: it scans the
:class:`ModeloRevision` for ADVISORY ``implies_any_nonzero`` verification
predicates and mirrors the same predicate shape as a non-blocking
:class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic` on the
calculate path. The verification predicate remains the single source of truth
for any total-to-official-box mapping, so calculate diagnostics and verify
findings cannot drift: the fire condition is not restated here but taken from
:func:`~cadrumo.application.modelo._verification_predicates.evaluate_advisory_predicate_fires`,
the same evaluator the verify gate runs. That call is what makes the sentence
above structurally true rather than a claim -- this collector once carried its
own copy of the antecedent/consequent test, which agreed with the verification
side only for as long as nobody edited either.

Modelo 303's former post-2022 revision used this mechanism in Stage 1, when
ledger-backed semantic totals could be positive while manual official
Diseño-de-Registros cuota boxes stayed zero. Stage 2 now projects those boxes
from their semantic sources and retired the Stage-1 ADVISORY predicates, so this
collector normally emits no M303 official-box diagnostics for that revision.

See Also:
    :mod:`~cadrumo.application.modelo._calculation_diagnostics`
        Post-calculation coordinator that calls this collector with the engine
        casilla values.
    :mod:`~cadrumo.application.modelo.verification_actions`
        Verification predicate parser/evaluator whose ``implies_any_nonzero``
        shape this collector mirrors.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.schema import ModeloRevision
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
    :class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic` with
    ``reason = "official_box_unpopulated"``, naming the positive antecedent
    casilla and the unpopulated official boxes so the operator-facing surface
    can instruct the transcription.

    Args:
        revision: The :class:`ModeloRevision` whose ADVISORY
            ``implies_any_nonzero`` predicates are evaluated. If the revision
            has retired those predicates, no diagnostic is emitted.
        casilla_values: The computed engine values keyed by :class:`CasillaId`
            and used to test the predicates, so both the semantic antecedent
            (e.g. ``iva.cuota-devengada-total``) and the official box ids
            (e.g. ``09``) resolve.

    See Also:
        :func:`~cadrumo.application.modelo.verification_actions._evaluate_predicate_expression`:
            Verification-side evaluator for the same predicate DSL.
    """
    # Lazy imports avoid the calculate/verification action cycle. The domain
    # registry owns predicate syntax; the verification module owns evaluation.
    from ...domain.calculations.registry.schema_verification import (
        VerificationPredicateOperator,
        parse_verification_predicate_expression,
    )
    from ._verification_predicates import evaluate_advisory_predicate_fires

    diagnostics: list[CalculationSourceDiagnostic] = []
    for predicate in revision.verification_predicates:
        if predicate.finding_kind != "ADVISORY":
            continue
        parsed = parse_verification_predicate_expression(predicate.expression)
        if parsed is None or parsed.operator is not VerificationPredicateOperator.IMPLIES_ANY_NONZERO:
            continue
        ids = parsed.casilla_ids
        if len(ids) < 2:
            continue
        # The fire condition is the verification side's, called rather than
        # restated: this collector and the verify gate must answer identically
        # for the same casilla values, and a second copy of the antecedent /
        # consequent test is how they would stop doing so. The regex and the id
        # parser above are still needed here to name the boxes in the message.
        if not evaluate_advisory_predicate_fires(predicate.expression, casilla_values):
            continue
        antecedent_id = ids[0]
        consequent_ids = ids[1:]
        antecedent = casilla_values.get(antecedent_id, Decimal(0))
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
