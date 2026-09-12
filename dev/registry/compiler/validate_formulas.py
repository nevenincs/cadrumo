"""Formula expression and dependency graph validation helpers.

Validates formula expressions and the DAG formed by formula targets
declared on a :class:`~cadrumo.domain.calculations.registry.ModeloRevision`,
checking casilla, binding, parameter, and relation reference closure and
detecting cycles.

See Also:
    :func:`cadrumo.domain.calculations.registry.runtime_graph.expression_casilla_refs`
        Formula-expression walker used to derive target dependencies.
    :func:`cadrumo.domain.calculations.registry.runtime_graph.formula_evaluation_order`
        Runtime topological order builder that assumes this validator has
        rejected cycles.
"""

from __future__ import annotations

from collections.abc import Mapping
from graphlib import CycleError
from typing import Final

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.runtime_graph import formula_evaluation_order
from cadrumo.domain.calculations.registry.schema import FormulaDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.validate_revision_identity import duplicates

from ._validate_helpers import missing_refs
from .validate_evidence import EvidenceValidator


def validate_formula_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    bindings: set[BindingId],
    parameters: set[str],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return formula reference, evidence, citation, and duplicate-target failures.

    Every formula the :class:`ModeloRevision` ``revision`` declares is checked in
    turn, and each failure is collected into the returned list.
    """
    failures: list[str] = []
    for formula in revision.formulas:
        owner = f"formula {formula.id}"
        failures.extend(missing_refs(prefix, owner, formula.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, formula.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, formula.source_refs, "official_source_guidance"))
        failures.extend(
            evidence.validate_source_citations(
                prefix,
                owner,
                formula.source_refs,
                formula.source_citations,
                "official_source_guidance",
            ),
        )
        failures.extend(
            validate_formula_target_casilla(
                prefix,
                formula,
                casillas=casillas,
                casilla_by_id=casilla_by_id,
            ),
        )
        failures.extend(
            validate_formula_expression(
                prefix,
                formula.id,
                formula.expression,
                casillas=casillas,
                bindings=bindings,
                parameters=parameters,
            ),
        )

        failures.extend(validate_boolean_channel_operands(prefix, formula, revision=revision))

    for target in sorted(duplicates([formula.target_casilla_id for formula in revision.formulas])):
        failures.append(f"{prefix}: duplicate formula target {target!r}")
    return failures


#: Operator positions at which a truth-valued binding is a legitimate operand.
#: ``equal`` asks the yes/no question of it directly; ``if_then_else`` reads its
#: first argument as the branch condition. Every other position consumes its
#: operand as a quantity, where a truth value has no defensible magnitude.
_BOOLEAN_OPERAND_POSITIONS: Final[frozenset[tuple[str, int]]] = frozenset(
    {("equal", 0), ("equal", 1), ("if_then_else", 0)},
)


def validate_boolean_channel_operands(
    scope: str,
    formula: FormulaDefinition,
    *,
    revision: ModeloRevision,
) -> list[str]:
    """Refuse a boolean-channel binding consumed as an arithmetic operand.

    A binding whose value contract declares the boolean channel carries a truth
    value, not a magnitude. The evaluator projects it to ``1``/``0`` at the leaf
    so a predicate can read it, and that projection is only meaningful where the
    formula is asking a yes/no question: an ``equal`` comparison operand, or the
    condition of an ``if_then_else``. Summed, multiplied, or subtracted, the same
    projection silently fabricates a filing-grade quantity out of a fact that has
    none -- a declared ``true`` becoming one euro of base.

    A bare binding leaf standing as the WHOLE expression is the third legitimate
    shape and is not refused: no operator consumes it, and the published corpus
    uses it to project a declared truth onto a yes/no casilla (Modelo 100 casilla
    0245, "si el matrimonio ha estado vigente durante todo el ano"), where 1/0 is
    the record design's own encoding rather than an invented quantity.

    The check is positional rather than value-based because the defect is in the
    declaration, not in any particular filing's data: it must fail at compile
    time, before a revision carrying it can be published.
    """
    boolean_bindings = {
        binding.id for binding in revision.bindings if binding.value.channel is BindingValueChannel.BOOLEAN
    }
    if not boolean_bindings:
        return []
    failures: list[str] = []
    _collect_boolean_operand_failures(
        scope,
        formula.id,
        formula.expression,
        boolean_bindings=boolean_bindings,
        position=None,
        failures=failures,
    )
    return failures


def _collect_boolean_operand_failures(
    scope: str,
    formula_id: str,
    expression: FormulaExpression,
    *,
    boolean_bindings: set[BindingId],
    position: tuple[str, int] | None,
    failures: list[str],
) -> None:
    """Walk one expression tree, recording every misplaced boolean-binding leaf."""
    if (
        position is not None
        and position not in _BOOLEAN_OPERAND_POSITIONS
        and expression.binding is not None
        and expression.binding in boolean_bindings
    ):
        failures.append(
            f"{scope}: formula {formula_id!r} consumes boolean-channel binding "
            f"{expression.binding!r} as {position[0]!r} argument {position[1]}; a boolean "
            f"binding may only be an 'equal' operand, an 'if_then_else' condition, or the "
            f"whole expression of a formula targeting a yes/no casilla",
        )
    operator = expression.op
    for index, arg in enumerate(expression.args):
        _collect_boolean_operand_failures(
            scope,
            formula_id,
            arg,
            boolean_bindings=boolean_bindings,
            position=None if operator is None else (str(operator), index),
            failures=failures,
        )


def validate_formula_dag(scope: str, revision: ModeloRevision) -> list[str]:
    """Return dependency-cycle failures for a revision's computed formulas.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    formula targets and expressions. Only dependencies that point at another
    computed target participate in the DAG; registry membership and reference
    existence are handled by :func:`validate_formula_expression`.
    """
    try:
        formula_evaluation_order(revision)
    except CycleError as exc:
        return [f"{scope}: formula graph cycle: {exc}"]
    return []


def _formula_scalar_reference_failures(
    scope: str,
    formula_id: str,
    expression: FormulaExpression,
    *,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    parameters: set[str],
) -> list[str]:
    failures: list[str] = []
    if expression.casilla_id is not None and expression.casilla_id not in casillas:
        failures.append(f"{scope}: formula {formula_id!r} references unknown casilla {expression.casilla_id!r}")
    if expression.binding is not None and expression.binding not in bindings:
        failures.append(f"{scope}: formula {formula_id!r} references unknown binding {expression.binding!r}")
    if expression.parameter is not None and expression.parameter not in parameters:
        failures.append(f"{scope}: formula {formula_id!r} references unknown parameter {expression.parameter!r}")
    return failures


def _formula_dispatch_reference_failures(
    scope: str,
    formula_id: str,
    expression: FormulaExpression,
    parameters: set[str],
) -> list[str]:
    if expression.dispatch_table is None:
        return []
    return [
        f"{scope}: formula {formula_id!r} dispatch_table[{key!r}] references unknown parameter {dispatched!r}"
        for key, dispatched in expression.dispatch_table.items()
        if dispatched not in parameters
    ]


def _formula_direct_reference_failures(
    scope: str,
    formula_id: str,
    expression: FormulaExpression,
    *,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    parameters: set[str],
) -> list[str]:
    failures = _formula_scalar_reference_failures(
        scope,
        formula_id,
        expression,
        casillas=casillas,
        bindings=bindings,
        parameters=parameters,
    )
    failures.extend(_formula_dispatch_reference_failures(scope, formula_id, expression, parameters))
    return failures


def validate_formula_expression(
    scope: str,
    formula_id: str,
    expression: FormulaExpression,
    *,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    parameters: set[str],
) -> list[str]:
    """Return reference-closure failures for one formula expression tree.

    The :class:`~cadrumo.domain.calculations.registry.FormulaExpression` may refer
    to :class:`~cadrumo.core.CasillaId`,
    :class:`~cadrumo.domain.calculations.registry.BindingId`, parameter, and
    :class:`~cadrumo.domain.calculations.registry.RelationId` values. This recursive
    validator keeps every nested expression node inside the selected revision's
    declared id sets.
    """
    failures = _formula_direct_reference_failures(
        scope,
        formula_id,
        expression,
        casillas=casillas,
        bindings=bindings,
        parameters=parameters,
    )
    for arg in expression.args:
        failures.extend(
            validate_formula_expression(
                scope,
                formula_id,
                arg,
                casillas=casillas,
                bindings=bindings,
                parameters=parameters,
            ),
        )
    return failures


def validate_formula_target_casilla(
    scope: str,
    formula: FormulaDefinition,
    *,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
) -> list[str]:
    """Return the bidirectional schema failures for one formula target."""
    if formula.target_casilla_id not in casillas:
        return [f"{scope}: formula {formula.id!r} targets unknown casilla {formula.target_casilla_id!r}"]

    target_casilla = casilla_by_id[formula.target_casilla_id]
    failures: list[str] = []
    if target_casilla.input_kind != InputKind.COMPUTED:
        failures.append(
            f"{scope}: formula {formula.id!r} targets casilla {formula.target_casilla_id!r} "
            f"declared as {target_casilla.input_kind.value!r}; formula targets must be computed",
        )
    if target_casilla.formula != formula.id:
        failures.append(
            f"{scope}: formula {formula.id!r} targets casilla {formula.target_casilla_id!r} "
            f"whose declared formula is {target_casilla.formula!r}",
        )
    return failures
