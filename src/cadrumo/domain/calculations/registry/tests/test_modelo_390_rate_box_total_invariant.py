"""No rate-asserting Modelo 390 casilla may be an operand of a total formula.

This is the structural invariant the two-layer rate-box shape rests on, gated
once for the whole modelo rather than once per block.

THE SHAPE. A tier's roles are split: rate-specific casillas serve the official
per-rate boxes, and a rate-blind sibling serves the total and catches rows whose
rate the ledger never recorded. The two are complements. If a rate-specific
casilla ALSO reaches the total, every rate-recorded row is counted twice --
once through its box and once through the blind sibling that still carries it --
and the return OVER-declares. That is the opposite error from the mis-allocation
the split exists to fix, and it is the only way the repair can damage a figure
that was previously correct.

WHY THIS GATE EXISTS SEPARATELY FROM ITS TWO SIBLINGS. The Reg. ordinario and
recargo suites each assert this for their own block, by matching a casilla-id
prefix. Both are correct and both are blind by construction: they encode which
blocks exist today, so a block added later is invisible to them and could wire a
box into a total with nothing objecting. Everything here is derived from the
loaded revision instead -- no prefix, no fixture list, no count.

THE DISCRIMINATOR IS THE BINDING, NOT THE BOX NUMBER. A casilla asserts a rate
when its binding pins ``applied_rates``; that is what makes it a claim about one
rate rather than a quantity. Keying on "carries an official box number" instead
is WRONG and would fail on correct data: at the time of writing, four numbered
casillas are legitimately operands -- ``regularizacion-bienes-inversion`` (box
63), ``regularizacion-prorrata-definitiva`` (box 522), and the two totals, which
carry numbers and feed ``resultado-regimen-general``. A box number marks a slot
in the record; it says nothing about whether the casilla asserts a rate.

MODELO 303 LEGITIMATELY VIOLATES THIS INVARIANT, AND IS NOT DEFECTIVE FOR IT.
Its total cuota devengada enumerates the tier cuota boxes directly, including
the RD-ley 4/2024 transitional rungs. It has no rate-blind total, so there is no
sibling to double against, and a rate-specific operand there is simply how the
form is built. The governing decision records the precondition: the two-layer
shape requires a total that is NOT the sum of the tier boxes.

SO DO NOT WIDEN THIS GATE TO ANOTHER MODELO WITHOUT MEASURING THAT MODELO FIRST.
Extending it is not a matter of dropping the ``390`` filter: it requires
establishing that the modelo's totals are drawn independently of its tiers. On a
modelo where they are not, this assertion would red correct data and the obvious
"fix" would be to break the form.

Real-behaviour: the committed registry through the real authority, walked with
the canonical ``expression_casilla_refs``. No mocks, stubs, skips or xfail.

Non-tautology: both derived sets are asserted populated before the disjointness
is asserted over them. "No rate-asserting casilla among the operands" is trivially
true of an empty operand set, and a walker that silently returned nothing would
otherwise make this module pass while measuring nothing at all.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from .....core.resources import resources
from .. import ModeloRevision, expression_casilla_refs, selector_as_dict

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revisions() -> Iterator[tuple[str, ModeloRevision]]:
    """Yield every revision the modelo declares, not a fixed list of them.

    Modelo 390's single long revision is being partitioned into per-design
    epochs. Iterating whatever the definition declares means this gate covers
    epochs that do not exist yet, and keeps covering them if the partition is
    revised again.
    """
    modelo = resources().modelos.authority.modelo("390")
    yield from modelo.revisions.items()


def _rate_asserting_casilla_ids(revision: ModeloRevision) -> set[str]:
    """Casillas whose binding admits a specific rate, and therefore assert one."""
    bindings = {binding.id: binding for binding in revision.bindings}
    asserting: set[str] = set()
    for casilla in revision.casillas:
        if casilla.binding is None:
            continue
        binding = bindings.get(str(casilla.binding))
        if binding is None:
            continue
        if selector_as_dict(binding).get("applied_rates"):
            asserting.add(casilla.id)
    return asserting


def _formula_operand_ids(revision: ModeloRevision) -> set[str]:
    """Every casilla referenced by any formula, via the canonical walker.

    ``expression_casilla_refs`` walks the validated expression tree. A regex over
    a formula's repr looks equivalent and is not: it matches the raw mapping the
    TOML parses to and silently extracts nothing from the loaded schema object,
    which is a failure with no symptom.
    """
    operands: set[str] = set()
    for formula in revision.formulas:
        operands |= {str(ref) for ref in expression_casilla_refs(formula.expression)}
    return operands


def test_the_derived_sets_are_populated() -> None:
    """The anti-vacuity precondition for every assertion below.

    Disjointness is trivially satisfied when either side is empty, so a revision
    that yielded no operands or no rate-asserting casillas would pass the real
    assertion while measuring nothing. This fails loudly instead.

    SCOPED TO REVISIONS THAT DECLARE A FORMULA, because the failure this guards
    is a WALKER that silently returns nothing -- and a walker can only fail on a
    revision that has something to walk. Modelo 390's 2021 revision declares no
    formulas at all: it is `authority_grade = "applicability"`, carrying ten
    casillas and an extraction profile so a filed prior-year return can be
    PARSED, and its own review note says "filing layout authority is not
    claimed". It has no bindings, no export layout and no formulas, so an empty
    operand set there is the correct reading of the data rather than a walker
    that broke.

    The exemption is keyed on the revision declaring zero formulas, never on its
    id, so a calculation-bearing revision whose operands come back empty still
    fails. The converse is asserted too: a formula-less revision must also yield
    no operands, since operands appearing from nowhere would be its own defect.
    """
    measured = 0
    for revision_id, revision in _revisions():
        operands = _formula_operand_ids(revision)
        if not revision.formulas:
            assert not operands, f"{revision_id}: declares no formulas yet {len(operands)} operand(s) were extracted"
            continue
        asserting = _rate_asserting_casilla_ids(revision)
        assert operands, f"{revision_id}: no formula operands were extracted at all"
        assert asserting, (
            f"{revision_id}: no rate-asserting casilla was found, so the invariant below would hold vacuously"
        )
        measured += 1
    assert measured, "no modelo 390 revision declares a formula, so this module measured nothing at all"


def test_no_rate_asserting_casilla_is_a_total_operand() -> None:
    """The invariant: a casilla may assert a rate OR feed a total, never both.

    Derived wholly from the revision, so a régimen block added later is covered
    the moment it declares a rate-pinned binding. Nothing here enumerates the
    blocks that happen to exist.
    """
    for revision_id, revision in _revisions():
        operands = _formula_operand_ids(revision)
        asserting = _rate_asserting_casilla_ids(revision)
        leaked = sorted(asserting & operands)
        assert not leaked, (
            f"{revision_id}: {leaked} assert a specific rate via applied_rates AND are "
            f"summed by a formula. Their rate-blind sibling already carries those rows "
            f"for the total, so each rate-recorded row is counted twice and the return "
            f"over-declares. Feed the total from the rate-blind layer only."
        )
