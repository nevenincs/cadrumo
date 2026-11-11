"""Follow the annual liquidation graph without treating disclosure totals as tax."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....iva.rates import IVA_RATE_FACT_ID
from ..authority import bundled_indexed_authority
from ..facts.payloads import MappingFactPayload
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


def spanish_temporary_rate_window(percent: str) -> tuple[date, date]:
    """Return the latest closed window in which the registry puts one Spanish IVA rate in force.

    The temporary rates (5 %, 7,5 %, 2 % and the zero rate of the same measure)
    are in force only inside the windows the rate fact dates, so a test that
    needs a day where one applies, or a day where it does not, reads the window
    from the fact instead of spelling its dates.
    """
    wanted = Decimal(percent)
    with bundled_indexed_authority().operation() as operation:
        variants = operation.governed_fact(IVA_RATE_FACT_ID).variants
    windows = [
        (variant.valid_from, variant.valid_to)
        for variant in variants
        if {selector.name: selector.value for selector in variant.selectors}.get("member_state") == "es"
        and variant.valid_from is not None
        and variant.valid_to is not None
        and isinstance(variant.payload, MappingFactPayload)
        and any(entry.key == "pct" and entry.value == wanted for entry in variant.payload.entries)
    ]
    assert windows, f"the rate fact dates no closed window for {percent} %"
    return max(windows)


def temporary_rate_year() -> int:
    """Return the year of the window in which the 5 % temporary rate applies."""
    return spanish_temporary_rate_window("5")[0].year
