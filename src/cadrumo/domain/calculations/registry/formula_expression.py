"""Evaluation of registry formula expression trees."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ....core.casilla_id import CasillaId
from ....core.decimal.constants import ONE, ZERO
from . import _formula_runtime_irnr as _irnr
from . import _formula_runtime_m131 as _m131
from . import formula_runtime_m100 as _m100
from ._formula_operator_contracts import require_formula_operator_arity
from .errors import RegistryValidationError
from .formula_runtime_ops import UnresolvedFormulaDependencyError as _UnresolvedFormulaDependencyError
from .formula_runtime_ops import evaluate_args_op as _evaluate_args_op
from .formula_runtime_ops import numeric_casilla_value as _numeric_casilla_value
from .formula_runtime_ops import resolve_bracket as _resolve_bracket
from .formula_runtime_ops import resolve_scalar_parameter as _resolve_scalar_parameter
from .ids import BindingId, RelationId
from .schema_formula import FormulaExpression, ParameterDefinition


def evaluate_expression(
    expression: FormulaExpression,
    *,
    values: Mapping[CasillaId, Decimal],
    binding_values: Mapping[BindingId, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[RelationId, Decimal],
    unresolved_relation_ids: frozenset[RelationId],
    unresolved_casilla_ids: set[CasillaId],
    operand_refs: list[str],
    operand_casilla_refs: list[CasillaId],
    operand_values: list[Decimal],
    unresolved_binding_ids: frozenset[BindingId] = frozenset(),
    enum_binding_values: Mapping[BindingId, str] | None = None,
    date_binding_values: Mapping[BindingId, date] | None = None,
    boolean_binding_values: Mapping[BindingId, bool] | None = None,
    filing_year: int = 0,
    text_values: Mapping[CasillaId, str] | None = None,
    text_casilla_ids: frozenset[CasillaId] = frozenset(),
    record_row_occupancy: Mapping[BindingId, bool] | None = None,
) -> Decimal:
    """Build the shared :class:`EvalContext` for one formula tree and evaluate it.

    The entry point from loose arguments: it normalises the optional channels
    and constructs the context once. Recursive re-entry goes through
    :func:`evaluate_with_context`, which carries that same context object forward
    instead of rebuilding it.

    Returns:
        The evaluated :class:`~decimal.Decimal` value of ``expression``.
    """
    resolved_enum_bindings: Mapping[BindingId, str] = enum_binding_values or dict[BindingId, str]()
    resolved_date_bindings: Mapping[BindingId, date] = date_binding_values or dict[BindingId, date]()
    resolved_boolean_bindings: Mapping[BindingId, bool] = boolean_binding_values or dict[BindingId, bool]()
    resolved_text_values: Mapping[CasillaId, str] = text_values or dict[CasillaId, str]()
    ctx = EvalContext(
        values=values,
        binding_values=binding_values,
        parameters=parameters,
        date_context=date_context,
        relation_values=relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        unresolved_casilla_ids=unresolved_casilla_ids,
        operand_refs=operand_refs,
        operand_casilla_refs=operand_casilla_refs,
        operand_values=operand_values,
        enum_binding_values=resolved_enum_bindings,
        date_binding_values=resolved_date_bindings,
        boolean_binding_values=resolved_boolean_bindings,
        filing_year=filing_year,
        text_values=resolved_text_values,
        text_casilla_ids=text_casilla_ids,
        record_row_occupancy=record_row_occupancy or {},
    )
    return evaluate_with_context(expression, ctx)


@dataclass(frozen=True, slots=True)
class EvalContext:
    """Bundles the runtime sinks + maps threaded through every recursive call.

    Frozen and slotted. Exactly one instance is built per formula tree, by
    :func:`evaluate_expression`, and handed by reference to every per-op
    evaluator and every recursive re-entry through
    :func:`evaluate_with_context`; the tree is walked without rebuilding it.
    The three list sinks (operand_refs, operand_casilla_refs, operand_values)
    ARE mutated in place — they accumulate evaluation provenance for the
    explainability surface, and passing the one context object by reference is
    what keeps every node of the tree appending to those same three lists.
    """

    values: Mapping[CasillaId, Decimal]
    binding_values: Mapping[BindingId, Decimal]
    parameters: Mapping[str, ParameterDefinition]
    date_context: Mapping[str, date]
    relation_values: Mapping[RelationId, Decimal]
    unresolved_relation_ids: frozenset[RelationId]
    unresolved_casilla_ids: set[CasillaId]
    operand_refs: list[str]
    operand_casilla_refs: list[CasillaId]
    operand_values: list[Decimal]
    enum_binding_values: Mapping[BindingId, str]
    date_binding_values: Mapping[BindingId, date]
    filing_year: int
    boolean_binding_values: Mapping[BindingId, bool] = field(default_factory=lambda: dict[BindingId, bool]())
    unresolved_binding_ids: frozenset[BindingId] = frozenset()
    text_values: Mapping[CasillaId, str] = field(default_factory=lambda: dict[CasillaId, str]())
    #: Every casilla the revision declares as text, populated or not. A text
    #: casilla absent from ``text_values`` is absent: it has no numeric value to
    #: fall back to, so an operand reader must consult this set rather than infer
    #: text-ness from the value it happens to find.
    text_casilla_ids: frozenset[CasillaId] = frozenset()
    record_row_occupancy: Mapping[BindingId, bool] = field(default_factory=dict[BindingId, bool], repr=False)


def evaluate_with_context(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Evaluate one expression node against ``ctx``, recursing into its args.

    The dispatcher proper: leaf, specialised per-op evaluator, or generic
    arg-folding op. ``ctx`` is passed through by reference rather than
    destructured and rebuilt, so the whole tree shares one context object and
    one set of provenance sinks.
    """
    if expression.op is None:
        return _evaluate_leaf(expression, ctx)
    op = expression.op
    require_formula_operator_arity(op, len(expression.args))
    evaluator = SPECIALIZED_EXPRESSION_EVALUATORS.get(op)
    if evaluator is not None:
        return evaluator(expression, ctx)
    args = [evaluate_with_context(arg, ctx) for arg in expression.args]
    return _evaluate_args_op(op, args)


def _evaluate_lookup_bracket(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    if len(expression.args) != 2:
        raise RegistryValidationError("formula op 'lookup_bracket' expects 2 args")
    bracket_arg = expression.args[1]
    if bracket_arg.parameter is None:
        raise RegistryValidationError("formula op 'lookup_bracket' requires args[1] to be a parameter leaf")
    bracket_param = ctx.parameters.get(bracket_arg.parameter)
    if bracket_param is None:
        raise RegistryValidationError(f"parameter {bracket_arg.parameter!r} not registered")
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_arg.parameter!r} must declare data_type='bracket_table' to be used by lookup_bracket",
        )
    base = evaluate_with_context(expression.args[0], ctx)
    ctx.operand_refs.append(bracket_arg.parameter)
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_lookup_bracket_by_ccaa(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    if len(expression.args) != 3:
        raise RegistryValidationError("formula op 'lookup_bracket_by_ccaa' expects 3 args")
    binding_arg = expression.args[1]
    dispatch_arg = expression.args[2]
    if binding_arg.binding is None:
        raise RegistryValidationError("formula op 'lookup_bracket_by_ccaa' requires args[1] to be a binding leaf")
    if dispatch_arg.dispatch_table is None:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_ccaa' requires args[2] to be a dispatch_table leaf",
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_bracket_by_ccaa",
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_bracket_by_ccaa dispatch_table is missing CCAA {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})",
        )
    bracket_param_id = dispatch_table[dispatch_key]
    bracket_param = ctx.parameters.get(bracket_param_id)
    if bracket_param is None:
        raise RegistryValidationError(f"parameter {bracket_param_id!r} not registered")
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket_by_ccaa",
        )
    base = evaluate_with_context(expression.args[0], ctx)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(bracket_param_id)
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_lookup_parameter_by_entity_type(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Dispatch a scalar parameter lookup by an enum binding (e.g. entity_type → tipo gravamen for IS modelo 200).

    Three args: args[0] is unused (placeholder for symmetry with the
    bracket variant); args[1] is the binding leaf carrying the enum
    value; args[2] is the dispatch_table mapping enum keys to
    parameter ids.
    """
    op = "lookup_parameter_by_entity_type"
    if len(expression.args) != 3:
        raise RegistryValidationError(
            "formula op 'lookup_parameter_by_entity_type' expects 3 args",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "3"},
        )
    binding_arg = expression.args[1]
    dispatch_arg = expression.args[2]
    if binding_arg.binding is None:
        raise RegistryValidationError(
            "formula op 'lookup_parameter_by_entity_type' requires args[1] to be a binding leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "binding"},
        )
    if dispatch_arg.dispatch_table is None:
        raise RegistryValidationError(
            "formula op 'lookup_parameter_by_entity_type' requires args[2] to be a dispatch_table leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[2]", "expected_kind": "dispatch_table"},
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_parameter_by_entity_type",
            translated_message="errors.calc.enum_binding_value_missing",
            context={"binding_id": binding_arg.binding, "op": op},
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_parameter_by_entity_type dispatch_table is missing key {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})",
            translated_message="errors.calc.dispatch_key_unknown",
            context={
                "op": op,
                "binding_id": binding_arg.binding,
                "dispatch_key": dispatch_key,
                "available_keys": ",".join(sorted(dispatch_table)),
            },
        )
    scalar_param_id = dispatch_table[dispatch_key]
    ctx.operand_refs.append(binding_arg.binding)
    return _resolve_scalar_parameter(scalar_param_id, ctx, op=op)


def _evaluate_lookup_bracket_by_entity_type(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Dispatch a bracket-table lookup by an entity-type enum binding.

    Mirrors :func:`_evaluate_lookup_parameter_by_entity_type` but routes
    against a ``bracket_table`` parameter (e.g. the LIS Art. 29.1
    micro-empresa two-tranche scale on Modelo 200): args[0] is the base
    value resolved against the bracket; args[1] is the binding leaf
    carrying the enum value (typically ``legal_entity_form``); args[2]
    is the dispatch_table mapping enum keys to bracket-table parameter
    ids. A scalar parameter resolved by the dispatch is rejected — the
    op exists precisely because the per-sub-form rate is a tranche
    scale, not a flat scalar.
    """
    op = "lookup_bracket_by_entity_type"
    if len(expression.args) != 3:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_entity_type' expects 3 args",
            translated_message="errors.calc.lookup_dispatch_arg_count",
            context={"op": op, "expected": "3"},
        )
    binding_arg = expression.args[1]
    dispatch_arg = expression.args[2]
    if binding_arg.binding is None:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_entity_type' requires args[1] to be a binding leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[1]", "expected_kind": "binding"},
        )
    if dispatch_arg.dispatch_table is None:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_entity_type' requires args[2] to be a dispatch_table leaf",
            translated_message="errors.calc.lookup_dispatch_arg_kind",
            context={"op": op, "position": "args[2]", "expected_kind": "dispatch_table"},
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_bracket_by_entity_type",
            translated_message="errors.calc.enum_binding_value_missing",
            context={"binding_id": binding_arg.binding, "op": op},
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_bracket_by_entity_type dispatch_table is missing key {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})",
            translated_message="errors.calc.dispatch_key_unknown",
            context={
                "op": op,
                "binding_id": binding_arg.binding,
                "dispatch_key": dispatch_key,
                "available_keys": ",".join(sorted(dispatch_table)),
            },
        )
    bracket_param_id = dispatch_table[dispatch_key]
    bracket_param = ctx.parameters.get(bracket_param_id)
    if bracket_param is None:
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": bracket_param_id},
        )
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket_by_entity_type",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": bracket_param_id, "op": op},
        )
    base = evaluate_with_context(expression.args[0], ctx)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(bracket_param_id)
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_record_row_unused(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Return true only for a positively unused fixed row, never for a blank.

    A supplied value proves occupation even without a complete source set.
    Without that value or membership evidence the predicate stays unresolved.
    Missing fields in an occupied row are still checked by its chosen branch.
    """
    binding_id = expression.args[0].binding
    if binding_id is None:
        raise RegistryValidationError("record_row_unused requires one binding leaf")
    supplied = (
        binding_id in ctx.binding_values
        or binding_id in ctx.date_binding_values
        or binding_id in ctx.boolean_binding_values
        or bool(ctx.enum_binding_values.get(binding_id))
    )
    occupied = ctx.record_row_occupancy.get(binding_id)
    if occupied is False:
        if supplied:
            raise RegistryValidationError("an unused record row contains a supplied value")
        result = ONE
    elif occupied is True or supplied:
        result = ZERO
    else:
        raise _UnresolvedFormulaDependencyError((binding_id,))
    ctx.operand_refs.append(binding_id)
    ctx.operand_values.append(result)
    return result


def _text_binding_operand(key: BindingId, ctx: EvalContext) -> str | None:
    if key in ctx.unresolved_binding_ids:
        raise _UnresolvedFormulaDependencyError((key,))
    if key in ctx.binding_values or key in ctx.boolean_binding_values or key in ctx.date_binding_values:
        raise RegistryValidationError("text_equal operand has a non-text or ambiguous channel")
    value = ctx.enum_binding_values.get(key)
    ctx.operand_refs.append(key)
    return value


def _text_casilla_operand(key: CasillaId, ctx: EvalContext) -> str | None:
    if key in ctx.unresolved_casilla_ids:
        raise _UnresolvedFormulaDependencyError((key,))
    if key not in ctx.text_casilla_ids or key in ctx.values:
        raise RegistryValidationError("text_equal operand is not a text casilla")
    value = ctx.text_values.get(key)
    ctx.operand_casilla_refs.append(key)
    return value


def _text_operand(arg: FormulaExpression, ctx: EvalContext) -> str:
    if arg.binding is not None:
        value = _text_binding_operand(arg.binding, ctx)
    elif arg.casilla_id is not None:
        value = _text_casilla_operand(arg.casilla_id, ctx)
    elif arg.text_literal is not None:
        value = arg.text_literal
    else:
        raise RegistryValidationError("text_equal requires binding, casilla, or text_literal leaves")
    if not isinstance(value, str) or not value:
        raise RegistryValidationError("text_equal requires populated text operands")
    return value


def _evaluate_text_equal(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Compare two explicit text channels without numeric or case coercion."""
    texts = [_text_operand(arg, ctx) for arg in expression.args]
    result = ONE if texts[0] == texts[1] else ZERO
    ctx.operand_values.append(result)
    return result


def _evaluate_if_then_else(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Short-circuit: evaluate the predicate first, then only the selected branch.

    Eager evaluation of both branches would surface false-branch
    errors (e.g. divide-by-zero) even when the predicate routes around
    them — defeating the conditional.
    """
    if len(expression.args) != 3:
        raise RegistryValidationError("formula op 'if_then_else' expects 3 args")
    predicate_value = evaluate_with_context(expression.args[0], ctx)
    selected_branch = expression.args[1] if predicate_value != ZERO else expression.args[2]
    return evaluate_with_context(selected_branch, ctx)


def _evaluate_require_condition(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Require a true predicate before reading the value's dependencies."""
    if len(expression.args) != 2:
        raise RegistryValidationError("formula op 'require_condition' expects 2 args")
    predicate = evaluate_with_context(expression.args[0], ctx)
    if not predicate.is_finite() or predicate == ZERO:
        raise RegistryValidationError("formula precondition was not satisfied")
    return evaluate_with_context(expression.args[1], ctx)


def _evaluate_age_at_year_end(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    """Compute age at the fiscal year-end from a date-channel binding.

    Expects exactly one arg which must be a ``date_binding`` leaf — the
    id of a date-valued profile fact (e.g. taxpayer birth_date).
    Returns ``Decimal(filing_year - birth_date.year)``.

    Art. 57.1.b LIRPF ages the taxpayer at 31 December of the tax year
    (fin del período impositivo).  Because birth month/day cannot be
    after 31 December of any year, the simplistic
    ``filing_year - birth_year`` formula is correct for all cases.
    """
    if len(expression.args) != 1:
        raise RegistryValidationError("formula op 'age_at_year_end' expects exactly 1 arg")
    arg = expression.args[0]
    if arg.date_binding is None:
        raise RegistryValidationError("formula op 'age_at_year_end' requires args[0] to be a date_binding leaf")
    binding_id = arg.date_binding
    if binding_id not in ctx.date_binding_values:
        raise RegistryValidationError(
            f"date_binding {binding_id!r} has no supplied value; required by age_at_year_end",
            translated_message="errors.calc.date_binding_value_missing",
            context={"binding_id": binding_id},
        )
    birth_date = ctx.date_binding_values[binding_id]
    if ctx.filing_year == 0:
        raise RegistryValidationError(
            "age_at_year_end requires a non-zero filing_year in evaluation context",
            translated_message="errors.calc.age_at_year_end_no_filing_year",
        )
    age = Decimal(ctx.filing_year - birth_date.year)
    ctx.operand_refs.append(binding_id)
    ctx.operand_values.append(age)
    return age


def _evaluate_binding_leaf(binding_id: BindingId, ctx: EvalContext) -> Decimal:
    """Resolve one binding leaf and append its provenance reference.

    A binding carried on the boolean channel is projected to ``ONE``/``ZERO``
    HERE, at the point a formula reads it as a predicate operand, and nowhere
    earlier. That placement is the whole point of the separate channel: the
    truth value travels as a truth value, and the only thing that turns it into
    a number is a formula asking a yes/no question of it.

    The compiler refuses a boolean-channel binding consumed under an arithmetic
    operator, so this projection reaches an operand position in only three
    shapes: an ``equal`` comparison operand, an ``if_then_else`` condition, or
    the whole expression of a formula whose target casilla records that same
    yes/no answer in the record design's own 1/0 encoding.
    """
    boolean_value = ctx.boolean_binding_values.get(binding_id)
    if boolean_value is not None:
        value = ONE if boolean_value else ZERO
        ctx.operand_refs.append(binding_id)
        ctx.operand_values.append(value)
        return value
    if binding_id not in ctx.binding_values:
        if binding_id in ctx.unresolved_binding_ids:
            raise _UnresolvedFormulaDependencyError((binding_id,))
        raise RegistryValidationError(
            f"binding {binding_id!r} has no supplied value",
            translated_message="errors.calc.binding_value_missing",
            context={"binding_id": binding_id},
        )
    value = ctx.binding_values[binding_id]
    ctx.operand_refs.append(binding_id)
    ctx.operand_values.append(value)
    return value


def _reject_date_binding_leaf(binding_id: BindingId) -> None:
    """Reject a date channel used without its age operation."""
    raise RegistryValidationError(
        f"date_binding {binding_id!r} leaf must be consumed inside an "
        "'age_at_year_end' op, not used as a standalone Decimal leaf",
        translated_message="errors.calc.date_binding_used_as_decimal_leaf",
        context={"binding_id": binding_id},
    )


def _evaluate_leaf(expression: FormulaExpression, ctx: EvalContext) -> Decimal:
    if expression.text_literal is not None:
        raise RegistryValidationError("text_literal may only be an operand of text_equal")
    if expression.literal is not None:
        return expression.literal
    if expression.casilla_id is not None:
        return _numeric_casilla_value(expression.casilla_id, ctx)
    if expression.binding is not None:
        return _evaluate_binding_leaf(expression.binding, ctx)
    if expression.date_binding is not None:
        _reject_date_binding_leaf(expression.date_binding)
    if expression.parameter is not None:
        return _resolve_scalar_parameter(expression.parameter, ctx, op="formula_parameter")
    raise RegistryValidationError(
        "empty formula expression",
        translated_message="errors.calc.empty_expression",
    )


_FormulaExpressionEvaluator = Callable[[FormulaExpression, EvalContext], Decimal]
SPECIALIZED_EXPRESSION_EVALUATORS: dict[str, _FormulaExpressionEvaluator] = {
    "lookup_bracket": _evaluate_lookup_bracket,
    "lookup_bracket_by_ccaa": _evaluate_lookup_bracket_by_ccaa,
    "m100_resolve_renta_inmobiliaria_imputada": _m100.evaluate_m100_resolve_renta_inmobiliaria_imputada,
    "irnr_resolve_tipo_gravamen": _irnr.evaluate_irnr_resolve_tipo_gravamen,
    "m210_resolve_base_imponible": _irnr.evaluate_m210_resolve_base_imponible,
    "lookup_parameter_by_entity_type": _evaluate_lookup_parameter_by_entity_type,
    "lookup_bracket_by_entity_type": _evaluate_lookup_bracket_by_entity_type,
    "if_then_else": _evaluate_if_then_else,
    "require_condition": _evaluate_require_condition,
    "text_equal": _evaluate_text_equal,
    "record_row_unused": _evaluate_record_row_unused,
    "age_at_year_end": _evaluate_age_at_year_end,
    "m131_resolve_modulos_previo": _m131.evaluate_m131_resolve_modulos_previo,
    "m131_resolve_modulos_minoracion_empleo": _m131.evaluate_m131_resolve_modulos_minoracion_empleo,
    "m131_resolve_modulos_indice_exceso": _m131.evaluate_m131_resolve_modulos_indice_exceso,
    "m131_resolve_modulos_indices_generales": _m131.evaluate_m131_resolve_modulos_indices_generales,
    "m131_resolve_modulos_pequena_dimension_ignorado_flag": (
        _m131.evaluate_m131_resolve_modulos_pequena_dimension_ignorado_flag
    ),
    "m131_resolve_modulos_temporada_inicio_conflicto_flag": (
        _m131.evaluate_m131_resolve_modulos_temporada_inicio_conflicto_flag
    ),
    "m100_resolve_eo_agraria_indices_correctores": _m100.evaluate_m100_resolve_eo_agraria_indices_correctores,
}
