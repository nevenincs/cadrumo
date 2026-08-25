"""Deterministic child-amount derivation for evidence-driven splits.

The model proposes per-child *proportions* (fractions); the system derives the
per-child euro amounts in :func:`derive_child_amounts` so they sum EXACTLY to the
parent gross to the cent (the remainder lands on the last child). The model never
emits a euro amount (``llm-selects-system-derives-tax-numbers``). This bridges
:func:`~cadrumo.application.ledger.llm_classification.suggest_evidence_split` to
:func:`~cadrumo.application.ledger.actions_split_merge.split_transaction`, whose
children must sum to the parent magnitude exactly.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from ...core.money import round_to_cents

__all__ = ["derive_child_amounts"]


def derive_child_amounts(gross: Decimal, proportions: Sequence[Decimal]) -> tuple[Decimal, ...]:
    """Split ``gross`` into per-child amounts matching ``proportions``.

    Each amount is :func:`~cadrumo.core.money.round_to_cents` applied to
    ``gross * proportion``; the final child absorbs the rounding remainder so the
    amounts sum to ``gross`` exactly. Flow direction is inherited from the parent
    transaction outside this helper, never encoded in the amount sign.

    Args:
        gross: The parent transaction gross as a non-negative magnitude.
        proportions: Per-child fractions (each in ``(0, 1]``, summing to ~1.0).

    A single proportion (``1.0``) is the "no split warranted" verdict and yields
    ``(gross,)`` — the whole amount on one child. The caller
    (:func:`~cadrumo.application.ledger.llm_classification.suggest_evidence_split`)
    surfaces that verdict for review and never drives a one-way split through
    :func:`~cadrumo.application.ledger.actions_split_merge.split_transaction`;
    :func:`~cadrumo.application.ledger.llm_classification.apply_evidence_split`
    refuses a single-child suggestion.

    Returns:
        Per-child amounts, in child order, summing exactly to ``gross``.

    Raises:
        ValueError: When no proportions are supplied or ``gross`` is negative.
    """
    if not proportions:
        raise ValueError("a split proposal needs at least one child")
    if gross < Decimal("0"):
        raise ValueError("split parent amount must be a non-negative magnitude")
    amounts = [round_to_cents(gross * proportion) for proportion in proportions[:-1]]
    amounts.append(gross - sum(amounts, Decimal("0")))
    return tuple(amounts)
