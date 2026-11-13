"""Post-hydration checks of the autonomic deducción enrolments a revision carries.

An enrolment names its box by semantic role, the binding the axis count reaches
the formula through, and the parameters the formula and the axis read. Once a
revision is hydrated, each of those names must resolve in it: the role to the one
box the formula targets, inside the autonomic deducción section; the bindings to
profile bindings, each reading one profile path, that the formula reads; the
parameters to parameters the revision declares, the amount and income thresholds
among those the formula reads, and every dated value of an axis threshold a whole
number; the base
roles to boxes the formula sums; and every legal reference to the catalogue. Two
enrolments of one box are refused, since the shared dispatch could not tell which
to apply.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from ....core.aggregation import BindingSourceKind
from ...user_profile.registry_contract import profile_binding_selectors
from .autonomic_deduccion_enrolment import (
    AUTONOMIC_DEDUCCION_SECTION,
    AscendantMinimumEntitlementAxis,
    AutonomicDeduccionEnrolment,
    AutonomicIncomeLimit,
    DescendantEntryWindowAxis,
)
from .runtime_graph import expression_binding_refs, expression_casilla_refs, expression_parameter_refs

if TYPE_CHECKING:
    from .ids import ParameterId
    from .reference_checker import IdReferenceChecker
    from .schema import FormulaDefinition, ModeloRevision
    from .schema_formula import ParameterDefinition

__all__ = ["autonomic_deduccion_enrolments", "check_autonomic_deduccion_enrolments"]


def autonomic_deduccion_enrolments(
    revision: ModeloRevision,
) -> Iterator[tuple[FormulaDefinition, AutonomicDeduccionEnrolment]]:
    """Each formula of ``revision`` that enrols a comunidad deducción, with its enrolment, in declared order."""
    for formula in revision.formulas:
        if formula.autonomic_deduccion is not None:
            yield formula, formula.autonomic_deduccion


def _axis_parameters(enrolment: AutonomicDeduccionEnrolment) -> tuple[str, ...]:
    eligibility = enrolment.eligibility
    if isinstance(eligibility, DescendantEntryWindowAxis):
        return ()
    if isinstance(eligibility, AscendantMinimumEntitlementAxis):
        return (eligibility.minimum_age, eligibility.minimum_discapacidad_grado)
    raise AssertionError(f"unhandled eligibility axis {eligibility!r}")


def _role_casillas(revision: ModeloRevision, role: str) -> list[str]:
    return [casilla.id for casilla in revision.casillas if casilla.semantic_role == role]


def _check_target(
    checker: IdReferenceChecker, revision: ModeloRevision, formula: FormulaDefinition, owner: str
) -> None:
    enrolment = formula.autonomic_deduccion
    if enrolment is None:
        return
    matches = _role_casillas(revision, enrolment.target_semantic_role)
    if matches != [formula.target_casilla_id]:
        checker.failures.append(
            f"{checker.prefix}: {owner} names role {enrolment.target_semantic_role!r}, carried by {matches!r}, "
            f"but the formula targets box {formula.target_casilla_id!r}"
        )
        return
    casilla = next(casilla for casilla in revision.casillas if casilla.id == formula.target_casilla_id)
    if AUTONOMIC_DEDUCCION_SECTION not in casilla.section:
        checker.failures.append(
            f"{checker.prefix}: {owner} targets box {casilla.id!r}, which is not an autonomic deducción box"
        )


def _check_bindings(
    checker: IdReferenceChecker, revision: ModeloRevision, formula: FormulaDefinition, owner: str
) -> None:
    enrolment = formula.autonomic_deduccion
    if enrolment is None:
        return
    read = set(expression_binding_refs(formula.expression))
    declared = {binding.id: binding for binding in revision.bindings}
    named = [("count_binding", enrolment.count_binding)]
    limit = enrolment.income_limit
    if isinstance(limit, AutonomicIncomeLimit) and limit.other_members_base_binding is not None:
        named.append(("other_members_base_binding", limit.other_members_base_binding))
    for field, binding_id in named:
        binding = declared.get(binding_id)
        if binding is None:
            checker.failures.append(f"{checker.prefix}: {owner}.{field} references unknown binding {binding_id!r}")
        elif binding.source != BindingSourceKind.PROFILE:
            checker.failures.append(f"{checker.prefix}: {owner}.{field} {binding_id!r} is not a profile binding")
        elif len(profile_binding_selectors(binding.provider)) != 1:
            checker.failures.append(f"{checker.prefix}: {owner}.{field} {binding_id!r} does not read one profile path")
        elif binding_id not in read:
            checker.failures.append(f"{checker.prefix}: {owner}.{field} {binding_id!r} is not read by the formula")


def _check_parameters(
    checker: IdReferenceChecker, revision: ModeloRevision, formula: FormulaDefinition, owner: str
) -> None:
    enrolment = formula.autonomic_deduccion
    if enrolment is None:
        return
    read = set(expression_parameter_refs(formula.expression))
    formula_terms = _formula_parameters(enrolment)
    for parameter_id in (*formula_terms, *_axis_parameters(enrolment)):
        checker.chk(f"{owner} parameter", parameter_id, checker.parameter_ids)
    for parameter_id in formula_terms:
        if parameter_id not in read:
            checker.failures.append(f"{checker.prefix}: {owner} parameter {parameter_id!r} is not read by the formula")
    declared = {parameter.id: parameter for parameter in revision.parameters}
    for parameter_id in _axis_parameters(enrolment):
        parameter = declared.get(parameter_id)
        if parameter is not None and not _is_dated_whole_number(parameter):
            checker.failures.append(
                f"{checker.prefix}: {owner} axis parameter {parameter_id!r} is not a dated whole number"
            )


def _formula_parameters(enrolment: AutonomicDeduccionEnrolment) -> list[ParameterId]:
    """The amount and income-limit parameters the enrolment's formula must read."""
    formula_terms = [enrolment.amount]
    limit = enrolment.income_limit
    if isinstance(limit, AutonomicIncomeLimit):
        formula_terms.extend((limit.individual_limit, limit.joint_limit))
        if limit.unidad_familiar_limit is not None:
            formula_terms.append(limit.unidad_familiar_limit)
    return formula_terms


def _is_dated_whole_number(parameter: ParameterDefinition) -> bool:
    return bool(parameter.values) and all(dated.value == dated.value.to_integral_value() for dated in parameter.values)


def _check_income_base(
    checker: IdReferenceChecker, revision: ModeloRevision, formula: FormulaDefinition, owner: str
) -> None:
    enrolment = formula.autonomic_deduccion
    if enrolment is None or not isinstance(enrolment.income_limit, AutonomicIncomeLimit):
        return
    limit = enrolment.income_limit
    summed = set(expression_casilla_refs(formula.expression))
    for role in limit.base_semantic_roles:
        matches = _role_casillas(revision, role)
        if len(matches) != 1:
            checker.failures.append(f"{checker.prefix}: {owner} base role {role!r} resolves to {matches!r}")
        elif matches[0] not in summed:
            checker.failures.append(
                f"{checker.prefix}: {owner} base role {role!r} is box {matches[0]!r}, which the formula does not read"
            )
    checker.chk_tuple(f"{owner}.income_limit.legal_refs", limit.legal_refs, checker.legal_ids)


def check_autonomic_deduccion_enrolments(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    """Record a failure on ``checker`` for each enrolment reference the hydrated ``revision`` does not resolve."""
    enrolled_roles: dict[str, str] = {}
    for formula, enrolment in autonomic_deduccion_enrolments(revision):
        owner = f"formula {formula.id} autonomic_deduccion"
        earlier = enrolled_roles.setdefault(enrolment.target_semantic_role, formula.id)
        if earlier != formula.id:
            checker.failures.append(
                f"{checker.prefix}: {owner} enrols role {enrolment.target_semantic_role!r}, "
                f"which formula {earlier!r} already enrols"
            )
        checker.chk_tuple(f"{owner}.legal_refs", enrolment.legal_refs, checker.legal_ids)
        missing_from_formula = sorted(set(enrolment.legal_refs) - set(formula.legal_refs))
        if missing_from_formula:
            checker.failures.append(
                f"{checker.prefix}: {owner} cites {missing_from_formula!r}, which the formula does not cite"
            )
        _check_target(checker, revision, formula, owner)
        _check_bindings(checker, revision, formula, owner)
        _check_parameters(checker, revision, formula, owner)
        _check_income_base(checker, revision, formula, owner)
