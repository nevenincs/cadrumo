"""Standing gate: no casilla contributes twice to the same additive total.

A total that adds the same box twice over-states it, and a total that references
its own target is circular. Neither refuses anything at runtime -- both simply
produce a number -- so the failure is silent and, for a devengado or cuota total,
in the over-declaration direction.

The walk descends only through genuinely additive structure (``add``, ``sum``,
``subtract``, ``negate``), tracking the effective sign, and stops at selection
and scaling operators (``max``, ``min``, ``if_then_else``, ``percent`` and the
rest). That boundary matters: a casilla appearing in both branches of an
``if_then_else``, or as both a cap and a capped value under ``min``, is ordinary
modelling and only one branch contributes. Requiring a repeated *sign* likewise
keeps ``A - A`` style normalisations legal; what is refused is one box counted
twice in the same direction.

Leaves are canonicalised before comparison. A formula may name a casilla by its
registry id or by its printed number -- modelo 303's cuota-devengada-total does
both in one expression, mixing ``iva.repercutido.general`` with ``18`` -- so a
comparison on the raw leaf text would miss exactly the double count that is
hardest to see by eye.

This axis carries no known instance: the sweep that motivated the gate found zero
across every compiled formula. It is a ratchet, not a repair.
"""

from __future__ import annotations

from collections import Counter

import pytest

from ..authority import bundled_authority
from ..schema_formula import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Operators whose operands genuinely accumulate into one sum.
_SUMMING = frozenset({"add", "sum", "subtract", "negate"})


def _signed_additive_leaves(
    expression: FormulaExpression,
    sign: int = 1,
    collected: list[tuple[str, int]] | None = None,
) -> list[tuple[str, int]]:
    """Return every casilla leaf reachable through purely additive structure, with its sign."""
    if collected is None:
        collected = []
    operator = str(expression.op).lower() if expression.op else None

    if operator is None:
        if expression.casilla_id:
            collected.append((str(expression.casilla_id), sign))
        return collected

    if operator not in _SUMMING:
        # A selection or scaling node: at most one operand reaches the total, so
        # a repeat below it is not a double count.
        return collected

    for index, argument in enumerate(expression.args or ()):
        operand_sign = sign
        if operator == "negate" or (operator == "subtract" and index > 0):
            operand_sign = -sign
        _signed_additive_leaves(argument, operand_sign, collected)
    return collected


def _double_counts() -> tuple[list[str], list[str], int]:
    """Walk every compiled formula. Returns (double counts, self references, scanned)."""
    doubled: list[str] = []
    circular: list[str] = []
    scanned = 0

    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            canonical = {
                str(casilla.number): str(casilla.id)
                for casilla in revision.casillas
                if getattr(casilla, "number", None) is not None
            }

            def canonicalise(leaf: object, mapping: dict[str, str] = canonical) -> str:
                return mapping.get(str(leaf), str(leaf))

            for formula in revision.formulas or ():
                scanned += 1
                leaves = [
                    (canonicalise(leaf), leaf_sign) for leaf, leaf_sign in _signed_additive_leaves(formula.expression)
                ]

                if canonicalise(formula.target_casilla_id) in {leaf for leaf, _ in leaves}:
                    circular.append(
                        f"{modelo.id} [{revision_id}] {formula.id}: "
                        f"target {formula.target_casilla_id} appears in its own expression"
                    )

                for (casilla_id, leaf_sign), occurrences in Counter(leaves).items():
                    if occurrences > 1:
                        doubled.append(
                            f"{modelo.id} [{revision_id}] {formula.id}: "
                            f"{casilla_id} contributes {occurrences} times with sign {leaf_sign:+d}"
                        )

    return doubled, circular, scanned


def test_no_casilla_contributes_twice_to_one_additive_total() -> None:
    """One box counted twice in the same direction over-states the total silently."""
    doubled, _, scanned = _double_counts()

    # Anti-vacuity: a walk that reached no formula would pass while proving
    # nothing. A floor, not a pinned tally.
    assert scanned >= 500, f"walk reached only {scanned} formulas; the gate is not seeing the registry"

    assert not doubled, "casillas double-counted inside one additive total:\n" + "\n".join(
        f"  {row}" for row in doubled
    )


def test_no_formula_references_its_own_target() -> None:
    """A total that includes itself is circular, however plausible its value looks."""
    _, circular, _ = _double_counts()

    assert not circular, "formulas referencing their own target casilla:\n" + "\n".join(f"  {row}" for row in circular)


def _leaf(casilla_id: str) -> FormulaExpression:
    return FormulaExpression(casilla_id=casilla_id)


def test_the_gate_detects_a_repeated_addend() -> None:
    """Anti-tautology: the same box added twice must be reported."""
    expression = FormulaExpression(op="add", args=(_leaf("a"), _leaf("b"), _leaf("a")))

    assert Counter(_signed_additive_leaves(expression))[("a", 1)] == 2


def test_a_value_added_then_subtracted_is_not_a_double_count() -> None:
    """Opposite signs are a normalisation, not a repeat; flagging them would be noise."""
    expression = FormulaExpression(op="subtract", args=(_leaf("a"), _leaf("a")))

    counts = Counter(_signed_additive_leaves(expression))

    assert counts[("a", 1)] == 1
    assert counts[("a", -1)] == 1


def test_a_casilla_reused_across_a_selection_is_not_a_double_count() -> None:
    """Only one branch of a selection reaches the total, so descent must stop there."""
    branches = FormulaExpression(op="if_then_else", args=(_leaf("cond"), _leaf("a"), _leaf("a")))

    assert _signed_additive_leaves(branches) == []
