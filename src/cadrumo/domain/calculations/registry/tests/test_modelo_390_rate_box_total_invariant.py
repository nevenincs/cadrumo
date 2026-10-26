"""Rate-specific subtotals never add the matching blind control a second time.

Official printed sums can consume rate boxes. Their independent blind controls
retain unrated observations for coverage diagnostics and export refusal.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ..binding_selector_utils import selector_as_dict
from ..rate_box_partition import derive_rate_box_partitions
from ..runtime_graph import expression_casilla_refs
from ..schema import ModeloRevision
from .m390_formula_support import assert_partition_is_not_double_counted
from .registry_tree import bundled_modelo_components

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _revisions() -> Iterator[tuple[str, ModeloRevision]]:
    """Yield every revision the modelo declares, not a fixed list of them.

    Modelo 390's single long revision is being partitioned into per-design
    epochs. Iterating whatever the definition declares means this gate covers
    epochs that do not exist yet, and keeps covering them if the partition is
    revised again.
    """
    modelo = bundled_modelo_components("390")[0]
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


def test_no_formula_consumes_both_layers_of_a_rate_partition() -> None:
    """No formula consumes a blind control together with its rate breakdown."""
    measured = 0
    for _revision_id, revision in _revisions():
        for partition in derive_rate_box_partitions(revision):
            assert_partition_is_not_double_counted(revision, partition)
            measured += 1
    assert measured, "no rate-box partition was checked"


def test_a_blind_control_added_beside_its_printed_boxes_is_rejected() -> None:
    """Prove that the graph guard detects an indirect second copy of a tier."""
    revision = next(revision for revision_id, revision in _revisions() if revision_id == "2024")
    partition = next(
        partition
        for partition in derive_rate_box_partitions(revision)
        if partition.total_casilla_id == "iva.anual.repercutido.reducido"
    )
    total = next(
        formula for formula in revision.formulas if formula.target_casilla_id == "iva.anual.cuota-devengada-total"
    )
    blind = total.expression.args[0].model_copy(update={"casilla_id": partition.total_casilla_id})
    changed = total.model_copy(
        update={"expression": total.expression.model_copy(update={"args": (*total.expression.args, blind)})}
    )
    mutated = revision.model_copy(
        update={"formulas": tuple(changed if formula.id == total.id else formula for formula in revision.formulas)}
    )
    with pytest.raises(AssertionError, match="consumes both"):
        assert_partition_is_not_double_counted(mutated, partition)
