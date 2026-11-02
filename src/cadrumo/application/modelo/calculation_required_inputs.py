"""Which answers a Modelo calculation refuses to run without, read from the registry the engine runs on.

The engine raises a missing-input refusal in two places, and this module names
the inputs that reach each one, so a form can ask the filer for them before a
calculation is attempted instead of presenting them as optional:

* a bound casilla fed by an earlier filing the engine cannot treat as absent by
  design (:func:`~cadrumo.domain.calculations.registry.formula_initial_values.binding_is_absent_by_design`)
  has no value to start from. Only a carry that reaches back whole filing years
  is named here: it comes from a declaration that predates this campaign's
  work, so nothing the application prepares now fills it. A carry between
  periods of one year waits for the declaration that produces it instead.
* a formula leaf reads a binding the filer types (``manual_input``) and no
  value was supplied. A leaf behind an ``if_then_else`` is read only when its
  branch is taken, so it is named only when the branch is known from facts the
  caller supplies, or when both branches read it. A guard the facts cannot
  decide names nothing: the form does not claim a refusal it cannot prove.

The result is the set of boxes (and of bindings no box carries) that need the
filer. It never reads a value, so it cannot tell a missing answer from a given
one; the form pairs it with the box's own state.

See Also:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, bindings and formulas.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.decimal.constants import ONE, ZERO
from ...domain.calculations.registry.binding_selector_utils import provider_member
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids, revision_bindings_by_id
from ...domain.calculations.registry.binding_temporal import FilingYearOffset
from ...domain.calculations.registry.bindings_previous_filing import PreviousFilingProvider
from ...domain.calculations.registry.formula_expression import SPECIALIZED_EXPRESSION_EVALUATORS
from ...domain.calculations.registry.formula_initial_values import binding_is_absent_by_design
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.manual_input_selector import ManualInputProvider
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.calculations.registry.schema_formula import FormulaExpression
from ...domain.calculations.registry.schema_input_kind import InputKind


@dataclass(frozen=True, slots=True)
class CalculationRequiredInputs:
    """The boxes and the box-less bindings a calculation refuses to run without."""

    casilla_ids: frozenset[CasillaId] = frozenset()
    binding_ids: frozenset[BindingId] = frozenset()


def calculation_required_inputs(
    revision: ModeloRevision,
    *,
    registry_period: str,
    known_truths: Mapping[BindingId, bool] | None = None,
) -> CalculationRequiredInputs:
    """Name the inputs the engine refuses without for ``revision`` in the period ``registry_period``.

    ``known_truths`` are the yes-or-no facts already known for the filer, by
    boolean binding, which decide the guards formulas branch on; without them
    only reads that no guard can skip are named.
    """
    bindings = revision_bindings_by_id(revision)
    casilla_ids = set(_earlier_year_carries(revision, bindings, registry_period))
    binding_ids: set[BindingId] = set()
    truths = known_truths or {}
    declared = {item.id for item in revision.casillas}
    for formula in revision.formulas:
        for binding_id in _reads(formula.expression, truths):
            binding = bindings.get(binding_id)
            if binding is None or binding.source is not BindingSourceKind.MANUAL_INPUT:
                continue
            provider = binding.provider
            carrier = provider.casilla_id if isinstance(provider, ManualInputProvider) else None
            if carrier is not None and carrier in declared:
                casilla_ids.add(carrier)
            else:
                binding_ids.add(binding_id)
    return CalculationRequiredInputs(casilla_ids=frozenset(casilla_ids), binding_ids=frozenset(binding_ids))


def _earlier_year_carries(
    revision: ModeloRevision, bindings: Mapping[BindingId, BindingDefinition], registry_period: str
) -> set[CasillaId]:
    named: set[CasillaId] = set()
    for casilla in revision.casillas:
        if casilla.input_kind != InputKind.BOUND:
            continue
        carries = [
            binding
            for binding_id in bound_casilla_binding_ids(casilla)
            if (binding := bindings.get(binding_id)) is not None
            and binding.source is BindingSourceKind.PREVIOUS_FILING
            and isinstance(provider_member(binding, PreviousFilingProvider).temporal, FilingYearOffset)
        ]
        # The engine starts from the first value any of the casilla's equivalent bindings resolves, so the
        # box is refused only when every one of them is an unresolvable earlier-year carry.
        if (
            carries
            and len(carries) == len(bound_casilla_binding_ids(casilla))
            and not any(binding_is_absent_by_design(binding, target_period=registry_period) for binding in carries)
        ):
            named.add(casilla.id)
    return named


def _reads(expression: FormulaExpression, truths: Mapping[BindingId, bool]) -> frozenset[BindingId]:
    """The bindings evaluating ``expression`` is certain to read, given the facts in ``truths``."""
    none = frozenset[BindingId]()
    if expression.op is None:
        return none if expression.binding is None else frozenset({expression.binding})
    if expression.op == "if_then_else":
        guard, taken, skipped = expression.args
        decided = _decided(guard, truths)
        if decided is None:
            return _reads(guard, truths) | (_reads(taken, truths) & _reads(skipped, truths))
        return _reads(guard, truths) | _reads(taken if decided else skipped, truths)
    if expression.op == "require_condition":
        return _reads(expression.args[0], truths) | _reads(expression.args[1], truths)
    if expression.op in SPECIALIZED_EXPRESSION_EVALUATORS:
        # A specialised evaluator reads its operands on its own terms; nothing is claimed from inside it.
        return none
    return none.union(*(_reads(arg, truths) for arg in expression.args))


def _decided(guard: FormulaExpression, truths: Mapping[BindingId, bool]) -> bool | None:
    """Whether a guard holds, when it compares a known yes-or-no fact to a literal; otherwise unknown."""
    if guard.op != "equal" or len(guard.args) != 2:
        return None
    left, right = guard.args
    for fact, literal in ((left, right), (right, left)):
        if fact.binding is not None and fact.binding in truths and literal.literal is not None:
            held: Decimal = ONE if truths[fact.binding] else ZERO
            return held == literal.literal
    return None


__all__ = ["CalculationRequiredInputs", "calculation_required_inputs"]
