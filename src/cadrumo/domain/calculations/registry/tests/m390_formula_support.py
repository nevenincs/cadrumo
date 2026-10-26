"""Follow the annual liquidation graph without treating disclosure totals as tax."""

from __future__ import annotations

from ..rate_box_partition import RateBoxPartition
from ..runtime_graph import expression_casilla_refs
from ..schema import ModeloRevision


def formula_operands(revision: ModeloRevision, target: str) -> set[str]:
    """Return direct and transitive inputs to one declared formula."""
    formulas = {str(formula.target_casilla_id): formula for formula in revision.formulas}
    assert target in formulas, f"formula for {target} is absent"
    pending = [target]
    seen: set[str] = set()
    while pending:
        target = pending.pop()
        formula = formulas.get(target)
        if formula is None:
            continue
        for reference in expression_casilla_refs(formula.expression):
            operand = str(reference)
            if operand not in seen:
                seen.add(operand)
                pending.append(operand)
    return seen


def liquidation_operands(revision: ModeloRevision) -> set[str]:
    """Return direct and transitive inputs to the annual liquidation result."""
    operands = formula_operands(revision, "iva.anual.resultado-liquidacion")
    assert operands, "annual liquidation formula has no casilla operands"
    return operands


def assert_partition_is_not_double_counted(revision: ModeloRevision, partition: RateBoxPartition) -> None:
    """A subtotal may use the blind quantity or its breakdown, never both."""
    for formula in revision.formulas:
        operands = formula_operands(revision, str(formula.target_casilla_id))
        assert not (partition.total_casilla_id in operands and operands.intersection(partition.box_casilla_ids)), (
            f"{formula.id} consumes both {partition.total_casilla_id} and its rate-specific breakdown"
        )
