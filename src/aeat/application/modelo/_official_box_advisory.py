"""Calculate-path advisory for unpopulated official Diseño-de-Registros boxes.

The Modelo 303 2023-y-siguientes revision (and any future revision that follows
the same two-layer pattern) carries both a semantic aggregate casilla layer that
the ledger source mesh populates and feeds into the resultado chain, and the
official Diseño-de-Registros numbered boxes (``input_kind = "manual"``) that the
operator transcribes to the AEAT sede. A ledger-driven calculate folds real cuota
into the semantic layer while every official numbered box stays zero — a silent
under-declaration (``no-silent-under-declaration``): the human files the numbered
boxes (all zero) outside the application.

This module surfaces that contradiction on the calculate path as a non-blocking
:class:`~aeat.application.aggregation.CalculationSourceDiagnostic`. It reuses the
revision's ADVISORY ``implies_any_nonzero`` verification predicates as the SINGLE
source of truth for the total→constituent mapping (the same predicates the verify
gate evaluates), so the calculate advisory and the verify finding cannot drift.
A predicate "fires" — and therefore an advisory is emitted — exactly when the
antecedent (a computed total) is strictly positive and every listed consequent
(the official numbered boxes) is zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...domain.calculations.registry import ModeloRevision
from ..aggregation import CalculationSourceDiagnostic

__all__ = ["collect_official_box_unpopulated_diagnostics"]


def collect_official_box_unpopulated_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[str, Decimal],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisories for ADVISORY ``implies_any_nonzero`` predicates that fire.

    A predicate fires when its antecedent (a computed total) is strictly
    positive while every listed consequent (the official numbered boxes) is
    zero. Each fired predicate yields one
    :class:`~aeat.application.aggregation.CalculationSourceDiagnostic` with
    ``reason = "official_box_unpopulated"``, naming the positive antecedent
    casilla and the unpopulated official boxes so the operator-facing surface
    can instruct the transcription.

    Args:
        revision: The :class:`ModeloRevision` whose ADVISORY
            ``implies_any_nonzero`` predicates are evaluated.
        casilla_values: The computed casilla values (engine result) to test
            the predicates against — keyed by casilla id, so both the semantic
            antecedent (e.g. ``iva.cuota-devengada-total``) and the official
            box ids (e.g. ``09``) resolve.
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
