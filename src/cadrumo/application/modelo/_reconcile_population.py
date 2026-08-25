"""Population scoping for casilla reconciliation against a filed declaration.

:func:`detect_casilla_divergences` is a pure comparison and takes no view on
whether the two sides are *worth* comparing. Reconciling a freshly onboarded
profile against a pulled AEAT filing is the case where that matters: the local
calculation computes zero nearly everywhere, so every reconciled casilla
diverges and the operator learns nothing except that the bucket is empty. This
module supplies the missing predicate — which casillas of a persisted
:class:`~domain.modelos.CalculationRevision` carry enough locally-sourced input
that a divergence means genuine disagreement rather than emptiness — as a scope
the existing comparison already accepts, so no second differ is created.

The predicate is evaluated per casilla, not per revision. A revision that
supplied one figure out of forty has one thing to say and thirty-nine it does
not, and a whole-revision gate would either silence the one or surface the
thirty-nine.

WHAT COUNTS AS POPULATION, and why the list is shorter than it looks. A leaf of
a casilla's input closure is independent evidence when the operator supplied the
casilla directly, when the operator overrode the binding, when the binding reads
declared census facts, or when the binding is bucket-local and the revision
actually consumed ledger transactions. Carry bindings
(:attr:`~core.BindingSourceKind.PREVIOUS_FILING`,
:attr:`~core.BindingSourceKind.RELATION_PREFILL`) and relation references never
count, because their values originate in the same filed-observation store the
comparison's filed side is read from: counting them would let the scope be
satisfied by the very figures under comparison.

WHAT THIS DELIBERATELY DOES NOT CATCH. A taxpayer whose true figure is non-zero
and who supplied nothing leaves the casilla unpopulated, so no divergence is
raised and a real under-declaration goes unreported on this channel. That is a
false-negative bias, chosen because the alternative fires on every casilla of
every empty bucket, which is the alert fatigue that trains an operator to ignore
the channel. It must not be read as coverage of the absent-input case, which
needs a different signal. Separately, clause four approximates "the bucket holds
evidence" with "this revision consumed ledger transactions", so a bucket
populated only with invoices and no ledger transactions scores as empty — again
a false negative, and again the safe direction.

See Also:
    :func:`~application.modelo.detect_casilla_divergences`
        The pure comparison this scope is passed to.
    :class:`~domain.modelos.CalculationRevision`
        Persisted revision whose supplied inputs are read.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision supplying the formula graph walked here.
    :class:`~core.BindingSourceKind`
        Canonical source taxonomy separating carry bindings from evidence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BindingSourceKind, CasillaId
from ...core.aggregation import OBSERVATION_BACKED_BINDING_SOURCE_KINDS
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.runtime_graph import (
    expression_binding_refs,
    expression_casilla_refs,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import (
        DataBindingDefinition,
        FormulaExpression,
        ModeloRevision,
    )
    from ...domain.modelos import CalculationRevision

#: Binding sources whose value is read back from the filed-observation store.
#: Never population evidence: a scope satisfied by these would be satisfied by
#: the same figures the comparison places on its filed side. The canonical set
#: lives in ``core``; this module names it locally only for that reason.
_CARRY_SOURCE_KINDS = OBSERVATION_BACKED_BINDING_SOURCE_KINDS


class CasillaPopulationScope(BaseModel):
    """Which casillas of one persisted revision are worth reconciling.

    ``comparable_casilla_ids`` is the scope to pass to
    :func:`~application.modelo.detect_casilla_divergences`;
    ``unpopulated_casilla_ids`` is its complement over the same candidate set and
    is carried so a caller can report what was withheld rather than silently
    narrowing. The three ``supplied_*`` fields record the evidence the verdict
    rested on, so a scope that surprises an operator can be explained without
    re-deriving it.
    """

    model_config = _STRICT_FROZEN

    comparable_casilla_ids: tuple[CasillaId, ...] = ()
    unpopulated_casilla_ids: tuple[CasillaId, ...] = ()
    supplied_input_casilla_ids: tuple[CasillaId, ...] = ()
    supplied_binding_ids: tuple[BindingId, ...] = ()
    ledger_contributed: bool = False

    @property
    def divergence_scope(self) -> dict[CasillaId, None]:
        """Return ``comparable_casilla_ids`` in the mapping shape the comparison takes."""
        scope: dict[CasillaId, None] = {}
        for casilla_id in self.comparable_casilla_ids:
            scope[casilla_id] = None
        return scope

    @property
    def is_empty(self) -> bool:
        """Whether no casilla is comparable, i.e. the local calculation says nothing."""
        return not self.comparable_casilla_ids


def _closure_leaves(
    casilla_id: CasillaId,
    *,
    formula_expressions: dict[CasillaId, FormulaExpression],
    casilla_bindings: dict[CasillaId, BindingId],
) -> tuple[frozenset[CasillaId], frozenset[BindingId]]:
    """Walk one casilla's input closure to its non-computed leaves.

    Terminates at any casilla that is not a formula target: that casilla is
    itself a leaf, and its binding (when it has one) is a binding leaf. The
    registry validates the formula graph as a DAG, but ``seen`` guards the walk
    anyway so a malformed revision cannot hang a reconcile.
    """
    casilla_leaves: set[CasillaId] = set()
    binding_leaves: set[BindingId] = set()
    seen: set[CasillaId] = set()
    pending = [casilla_id]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        expression = formula_expressions.get(current)
        if expression is None:
            casilla_leaves.add(current)
            binding = casilla_bindings.get(current)
            if binding is not None:
                binding_leaves.add(binding)
            continue
        pending.extend(expression_casilla_refs(expression))
        binding_leaves.update(expression_binding_refs(expression))
    return frozenset(casilla_leaves), frozenset(binding_leaves)


def _binding_is_evidence(
    binding: DataBindingDefinition | None,
    *,
    overridden: bool,
    ledger_contributed: bool,
) -> bool:
    """Whether one binding leaf is independent population evidence."""
    if binding is None:
        return False
    if binding.source in _CARRY_SOURCE_KINDS:
        return False
    if overridden:
        return True
    if binding.source is BindingSourceKind.PROFILE:
        return True
    return ledger_contributed


def resolve_casilla_population_scope(
    *,
    registry_revision: ModeloRevision,
    calculation: CalculationRevision,
) -> CasillaPopulationScope:
    """Resolve which of ``registry_revision``'s casillas ``calculation`` can speak to.

    Args:
        registry_revision: The law-resolved :class:`ModeloRevision` supplying the
            formula graph, the casilla input kinds and the binding definitions.
            Resolve it from ``(modelo, filing_year, period)`` through the
            registry authority; never from a stored revision id.
        calculation: The persisted :class:`CalculationRevision` whose supplied
            inputs, binding overrides and ledger contribution decide population.

    Returns:
        The :class:`CasillaPopulationScope`. ``comparable_casilla_ids`` is empty
        exactly when the revision supplied no independent evidence anywhere, so
        an untouched bucket reconciles to no divergences at all.
    """
    formula_expressions: dict[CasillaId, FormulaExpression] = {
        formula.target_casilla_id: formula.expression for formula in registry_revision.formulas
    }
    bindings_by_id: dict[BindingId, DataBindingDefinition] = {
        binding.id: binding for binding in registry_revision.bindings
    }
    casilla_bindings: dict[CasillaId, BindingId] = {
        casilla.id: casilla.binding for casilla in registry_revision.casillas if casilla.binding is not None
    }
    supplied_inputs = frozenset(calculation.input_values_by_casilla_id)
    overridden_bindings = frozenset(calculation.binding_overrides)
    ledger_contributed = bool(calculation.source_transaction_ids)
    comparable, unpopulated = _partition_population_scope(
        registry_revision,
        formula_expressions=formula_expressions,
        bindings_by_id=bindings_by_id,
        casilla_bindings=casilla_bindings,
        supplied_inputs=supplied_inputs,
        overridden_bindings=overridden_bindings,
        ledger_contributed=ledger_contributed,
    )

    return CasillaPopulationScope(
        comparable_casilla_ids=tuple(sorted(comparable)),
        unpopulated_casilla_ids=tuple(sorted(unpopulated)),
        supplied_input_casilla_ids=tuple(sorted(supplied_inputs)),
        supplied_binding_ids=tuple(sorted(overridden_bindings)),
        ledger_contributed=ledger_contributed,
    )


def _partition_population_scope(
    registry_revision: ModeloRevision,
    *,
    formula_expressions: dict[CasillaId, FormulaExpression],
    bindings_by_id: dict[BindingId, DataBindingDefinition],
    casilla_bindings: dict[CasillaId, BindingId],
    supplied_inputs: frozenset[CasillaId],
    overridden_bindings: frozenset[BindingId],
    ledger_contributed: bool,
) -> tuple[list[CasillaId], list[CasillaId]]:
    candidates = tuple(
        casilla.id for casilla in registry_revision.casillas if casilla.input_kind is not InputKind.INFORMATIONAL
    )
    comparable: list[CasillaId] = []
    unpopulated: list[CasillaId] = []
    for casilla_id in candidates:
        if _casilla_is_populated(
            casilla_id,
            formula_expressions=formula_expressions,
            bindings_by_id=bindings_by_id,
            casilla_bindings=casilla_bindings,
            supplied_inputs=supplied_inputs,
            overridden_bindings=overridden_bindings,
            ledger_contributed=ledger_contributed,
        ):
            comparable.append(casilla_id)
        else:
            unpopulated.append(casilla_id)
    return comparable, unpopulated


def _casilla_is_populated(
    casilla_id: CasillaId,
    *,
    formula_expressions: dict[CasillaId, FormulaExpression],
    bindings_by_id: dict[BindingId, DataBindingDefinition],
    casilla_bindings: dict[CasillaId, BindingId],
    supplied_inputs: frozenset[CasillaId],
    overridden_bindings: frozenset[BindingId],
    ledger_contributed: bool,
) -> bool:
    casilla_leaves, binding_leaves = _closure_leaves(
        casilla_id,
        formula_expressions=formula_expressions,
        casilla_bindings=casilla_bindings,
    )
    return bool(casilla_leaves & supplied_inputs) or any(
        _binding_is_evidence(
            bindings_by_id.get(binding_id),
            overridden=binding_id in overridden_bindings,
            ledger_contributed=ledger_contributed,
        )
        for binding_id in binding_leaves
    )


__all__ = [
    "CasillaPopulationScope",
    "resolve_casilla_population_scope",
]
