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

from ....core import CasillaId
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs
from .ids import BindingId, RelationId
from .runtime_graph import formula_evaluation_order
from .schema import FormulaDefinition, ModeloRevision
from .schema_formula import FormulaExpression
from .schema_input_kind import InputKind
from .schema_references import LegalReference, SourceReference
from .schema_surfaces import CasillaDefinition
from .validate_revision_identity import duplicates


def validate_formula_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    bindings: set[BindingId],
    parameters: set[str],
    relations: set[RelationId],
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
                relations=relations,
            ),
        )

    for target in sorted(duplicates([formula.target_casilla_id for formula in revision.formulas])):
        failures.append(f"{prefix}: duplicate formula target {target!r}")
    return failures


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
    relations: set[RelationId],
) -> list[str]:
    failures: list[str] = []
    if expression.casilla_id is not None and expression.casilla_id not in casillas:
        failures.append(f"{scope}: formula {formula_id!r} references unknown casilla {expression.casilla_id!r}")
    if expression.binding is not None and expression.binding not in bindings:
        failures.append(f"{scope}: formula {formula_id!r} references unknown binding {expression.binding!r}")
    if expression.parameter is not None and expression.parameter not in parameters:
        failures.append(f"{scope}: formula {formula_id!r} references unknown parameter {expression.parameter!r}")
    if expression.relation is not None and expression.relation not in relations:
        failures.append(f"{scope}: formula {formula_id!r} references unknown relation {expression.relation!r}")
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
    relations: set[RelationId],
) -> list[str]:
    failures = _formula_scalar_reference_failures(
        scope,
        formula_id,
        expression,
        casillas=casillas,
        bindings=bindings,
        parameters=parameters,
        relations=relations,
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
    relations: set[RelationId],
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
        relations=relations,
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
                relations=relations,
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
