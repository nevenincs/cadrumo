"""Registry-backed formula runtime using typed operation graphs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ._errors import CasillaConstraintViolationError, RegistrySnapshotError, RegistryValidationError
from ._runtime_graph import formula_evaluation_order
from ._schema import DatedValue, FormulaExpression, ModeloRevision, ParameterDefinition, RegistrySnapshot

_ZERO = Decimal("0")
_ONE = Decimal("1")


class RegistryCalculationEntry(BaseModel):
    """One trace row emitted by the registry formula runtime.

    Carries the per-formula provenance (``formula_id``, ``op``,
    ``operand_refs``, ``operand_values``, ``legal_refs``,
    ``source_refs``) for a single formula-computed casilla. Entries
    cover ONLY the casillas that were computed by a registry formula
    — input casillas and bound casillas are absent from the entries
    tuple. Callers that need provenance for non-computed casillas
    must look them up against
    :attr:`RegistrySnapshot.revision.casillas` directly.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    formula_id: str
    target: str
    op: str
    operand_refs: tuple[str, ...]
    operand_values: tuple[Decimal, ...]
    value: Decimal
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class RegistryCalculationResult(BaseModel):
    """Calculated outputs and trace entries for one registry snapshot.

    Coverage asymmetry between ``values`` and ``entries``:

    * :attr:`values` covers every casilla on the revision — inputs,
      bound, and formula-computed — with the final Decimal value the
      engine resolved for each. Iterate this when assembling a
      complete casilla map (e.g. for filing draft construction).
    * :attr:`entries` covers ONLY the formula-computed casillas. Each
      entry carries the formula's legal_refs / source_refs / operand
      lineage. ``len(entries) <= len(values)`` always; equality holds
      only when every casilla on the revision is formula-computed
      (rare in practice).

    Consumers that assume ``len(entries) == len(values)`` will silently
    drop provenance on input and bound casillas — see
    :func:`aeat.application.modelo._actions.calculate_modelo_revision`
    for the canonical pattern that pulls input / bound provenance from
    the registry casilla definitions instead.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str
    revision: str
    values: Mapping[str, Decimal]
    entries: tuple[RegistryCalculationEntry, ...]


def calculate_registry_snapshot(
    snapshot: RegistrySnapshot,
    *,
    inputs: Mapping[str, Decimal],
    date_context: Mapping[str, date],
    binding_values: Mapping[str, Decimal] | None = None,
    enum_binding_values: Mapping[str, str] | None = None,
    relation_values: Mapping[str, Decimal] | None = None,
) -> RegistryCalculationResult:
    """Evaluate all computed formulas in a validated registry snapshot.

    ``enum_binding_values`` carries string-valued bindings (typically
    profile-sourced enums like ``CCAA``) that the
    :func:`lookup_bracket_by_ccaa` op routes against. They are kept in
    a separate mapping from ``binding_values`` so the Decimal-only
    contract on numeric bindings stays intact.
    """

    _reject_non_decimal(inputs, "input")
    resolved_date_context = dict(date_context)
    resolved_date_context.setdefault("filing_period", date(snapshot.filing_year, 12, 31))
    resolved_bindings = binding_values or {}
    _reject_non_decimal(resolved_bindings, "binding")
    resolved_enum_bindings = enum_binding_values or {}
    _reject_non_string(resolved_enum_bindings, "enum_binding")
    resolved_relations = relation_values or {}
    _reject_non_decimal(resolved_relations, "relation")

    revision = snapshot.revision
    _reject_unknown_external_values(resolved_bindings, {binding.id for binding in revision.bindings}, "binding")
    _reject_unknown_external_values(
        resolved_relations,
        {
            relation.id
            for relation in revision.relations
            if not relation.target_periods or snapshot.period in relation.target_periods
        },
        "relation",
    )
    values = _initial_values(revision, inputs)
    formulas = {formula.target: formula for formula in revision.formulas}
    parameters = {parameter.id: parameter for parameter in revision.parameters}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    entries: list[RegistryCalculationEntry] = []

    with localcontext() as ctx:
        ctx.prec = 28
        for target in formula_evaluation_order(revision):
            formula = formulas[target]
            operand_refs: list[str] = []
            operand_values: list[Decimal] = []
            value = _evaluate_expression(
                formula.expression,
                values=values,
                binding_values=resolved_bindings,
                parameters=parameters,
                date_context=resolved_date_context,
                relation_values=resolved_relations,
                operand_refs=operand_refs,
                operand_values=operand_values,
                enum_binding_values=resolved_enum_bindings,
            )
            value = _apply_rounding(value, formula.rounding)
            target_casilla = casillas_by_id.get(target)
            if target_casilla is not None and target_casilla.constraints is not None:
                violation = target_casilla.constraints.violates(value)
                if violation is not None:
                    raise CasillaConstraintViolationError(
                        f"casilla {target_casilla.number!r} ({target_casilla.label}) "
                        f"violates declared constraint: {violation}",
                        translated_message="errors.calc.casilla_constraint_violation",
                        context={
                            "casilla_id": target,
                            "casilla_number": target_casilla.number,
                            "value": str(value),
                            "formula_id": formula.id,
                            "legal_refs": ",".join(target_casilla.constraints.legal_refs),
                            "source_refs": ",".join(target_casilla.constraints.source_refs),
                        },
                    )
            values[target] = value
            entries.append(
                RegistryCalculationEntry(
                    formula_id=formula.id,
                    target=target,
                    op=formula.expression.op or "value",
                    operand_refs=tuple(operand_refs),
                    operand_values=tuple(operand_values),
                    value=value,
                    legal_refs=tuple(formula.legal_refs),
                    source_refs=tuple(formula.source_refs),
                )
            )

    return RegistryCalculationResult(
        modelo=snapshot.modelo.id,
        revision=revision.id,
        values=values,
        entries=tuple(entries),
    )


def _initial_values(revision: ModeloRevision, inputs: Mapping[str, Decimal]) -> dict[str, Decimal]:
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    unknown = sorted(set(inputs).difference(casillas))
    if unknown:
        raise RegistryValidationError(
            f"unknown registry input casilla ids: {unknown!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(unknown)},
        )
    formula_targets = {formula.target for formula in revision.formulas}
    computed = sorted(
        casilla_id
        for casilla_id in inputs
        if casillas[casilla_id].input_kind == "computed" or casilla_id in formula_targets
    )
    if computed:
        raise RegistryValidationError(
            f"computed registry casillas cannot be supplied as inputs: {computed!r}",
            translated_message="errors.calc.computed_supplied_as_input",
            context={"casilla_ids": ",".join(computed)},
        )
    values: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind == "computed":
            continue
        values[casilla.id] = inputs.get(casilla.id, _ZERO)
    return values


def _evaluate_expression(
    expression: FormulaExpression,
    *,
    values: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[str, Decimal],
    operand_refs: list[str],
    operand_values: list[Decimal],
    enum_binding_values: Mapping[str, str] | None = None,
) -> Decimal:
    resolved_enum_bindings: Mapping[str, str] = enum_binding_values or {}
    if expression.op is None:
        return _evaluate_leaf(
            expression,
            values=values,
            binding_values=binding_values,
            parameters=parameters,
            date_context=date_context,
            relation_values=relation_values,
            operand_refs=operand_refs,
            operand_values=operand_values,
        )
    ctx = _EvalContext(
        values=values,
        binding_values=binding_values,
        parameters=parameters,
        date_context=date_context,
        relation_values=relation_values,
        operand_refs=operand_refs,
        operand_values=operand_values,
        enum_binding_values=resolved_enum_bindings,
    )
    op = expression.op
    if op == "lookup_bracket":
        return _evaluate_lookup_bracket(expression, ctx)
    if op == "lookup_bracket_by_ccaa":
        return _evaluate_lookup_bracket_by_ccaa(expression, ctx)
    if op == "lookup_parameter_by_entity_type":
        return _evaluate_lookup_parameter_by_entity_type(expression, ctx)
    if op == "if_then_else":
        return _evaluate_if_then_else(expression, ctx)
    args = [_evaluate_with_ctx(arg, ctx) for arg in expression.args]
    return _evaluate_args_op(op, args)


@dataclass(frozen=True)
class _EvalContext:
    """Bundles the runtime sinks + maps threaded through every recursive call.

    Kept frozen and slot-equivalent so the dispatcher can hand the same
    context to every per-op evaluator without copying. The two list
    sinks (operand_refs, operand_values) ARE mutated in place — they
    accumulate evaluation provenance for the explainability surface.
    """

    values: Mapping[str, Decimal]
    binding_values: Mapping[str, Decimal]
    parameters: Mapping[str, ParameterDefinition]
    date_context: Mapping[str, date]
    relation_values: Mapping[str, Decimal]
    operand_refs: list[str]
    operand_values: list[Decimal]
    enum_binding_values: Mapping[str, str]


def _evaluate_with_ctx(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Convenience: re-enter the dispatcher carrying every context field forward."""
    return _evaluate_expression(
        expression,
        values=ctx.values,
        binding_values=ctx.binding_values,
        parameters=ctx.parameters,
        date_context=ctx.date_context,
        relation_values=ctx.relation_values,
        operand_refs=ctx.operand_refs,
        operand_values=ctx.operand_values,
        enum_binding_values=ctx.enum_binding_values,
    )


def _evaluate_lookup_bracket(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
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
            f"parameter {bracket_arg.parameter!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket"
        )
    base = _evaluate_with_ctx(expression.args[0], ctx)
    ctx.operand_refs.append(bracket_arg.parameter)
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_lookup_bracket_by_ccaa(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    if len(expression.args) != 3:
        raise RegistryValidationError("formula op 'lookup_bracket_by_ccaa' expects 3 args")
    binding_arg = expression.args[1]
    dispatch_arg = expression.args[2]
    if binding_arg.binding is None:
        raise RegistryValidationError("formula op 'lookup_bracket_by_ccaa' requires args[1] to be a binding leaf")
    if dispatch_arg.dispatch_table is None:
        raise RegistryValidationError(
            "formula op 'lookup_bracket_by_ccaa' requires args[2] to be a dispatch_table leaf"
        )
    if binding_arg.binding not in ctx.enum_binding_values:
        raise RegistryValidationError(
            f"enum binding {binding_arg.binding!r} has no supplied value; required by lookup_bracket_by_ccaa"
        )
    dispatch_key = ctx.enum_binding_values[binding_arg.binding]
    dispatch_table = dispatch_arg.dispatch_table
    if dispatch_key not in dispatch_table:
        raise RegistryValidationError(
            f"lookup_bracket_by_ccaa dispatch_table is missing CCAA {dispatch_key!r} "
            f"(declared keys: {sorted(dispatch_table)})"
        )
    bracket_param_id = dispatch_table[dispatch_key]
    bracket_param = ctx.parameters.get(bracket_param_id)
    if bracket_param is None:
        raise RegistryValidationError(f"parameter {bracket_param_id!r} not registered")
    if bracket_param.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {bracket_param_id!r} must declare data_type='bracket_table' "
            f"to be used by lookup_bracket_by_ccaa"
        )
    base = _evaluate_with_ctx(expression.args[0], ctx)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(bracket_param_id)
    result = _resolve_bracket(bracket_param, base, ctx.date_context)
    ctx.operand_values.append(result)
    return result


def _evaluate_lookup_parameter_by_entity_type(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
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
            f"enum binding {binding_arg.binding!r} has no supplied value;"
            " required by lookup_parameter_by_entity_type",
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
    scalar_param = ctx.parameters.get(scalar_param_id)
    if scalar_param is None:
        raise RegistryValidationError(
            f"parameter {scalar_param_id!r} not registered",
            translated_message="errors.calc.parameter_unknown",
            context={"parameter_id": scalar_param_id},
        )
    if scalar_param.data_type == "bracket_table":
        raise RegistryValidationError(
            f"parameter {scalar_param_id!r} declares data_type='bracket_table'; "
            f"lookup_parameter_by_entity_type requires a scalar parameter (decimal / money / integer / ratio)",
            translated_message="errors.calc.dispatch_parameter_kind",
            context={"parameter_id": scalar_param_id, "op": op},
        )
    result = _resolve_parameter(scalar_param, ctx.date_context)
    ctx.operand_refs.append(binding_arg.binding)
    ctx.operand_refs.append(scalar_param_id)
    ctx.operand_values.append(result)
    return result


def _evaluate_if_then_else(expression: FormulaExpression, ctx: _EvalContext) -> Decimal:
    """Short-circuit: evaluate the predicate first, then only the selected branch.

    Eager evaluation of both branches would surface false-branch
    errors (e.g. divide-by-zero) even when the predicate routes around
    them — defeating the conditional.
    """
    if len(expression.args) != 3:
        raise RegistryValidationError("formula op 'if_then_else' expects 3 args")
    predicate_value = _evaluate_with_ctx(expression.args[0], ctx)
    selected_branch = expression.args[1] if predicate_value != _ZERO else expression.args[2]
    return _evaluate_with_ctx(selected_branch, ctx)


_COMPARISON_OPS = frozenset({"less_than", "less_equal", "greater_than", "greater_equal", "equal"})
_UNARY_PASSTHROUGH_OPS = frozenset({"copy", "lookup_parameter", "previous_period_value", "cross_model_sum"})


def _evaluate_args_op(op: str, args: list[Decimal]) -> Decimal:
    """Dispatch an N-arg arithmetic / comparison op once every arg has been evaluated."""
    if op in {"add", "sum", "previous_period_sum"}:
        if op == "previous_period_sum":
            _require_non_empty(op, args)
        return sum(args, _ZERO)
    if op in _COMPARISON_OPS:
        _require_arg_count(op, args, 2)
        return _ONE if _compare(op, args[0], args[1]) else _ZERO
    if op in _UNARY_PASSTHROUGH_OPS:
        _require_arg_count(op, args, 1)
        return args[0]
    return _dispatch_named_arithmetic_op(op, args)


def _dispatch_named_arithmetic_op(op: str, args: list[Decimal]) -> Decimal:
    """Dispatch the per-name arithmetic ops (subtract / multiply / divide / percent / min / max / clamp / negate)."""
    match op:
        case "subtract":
            _require_arg_count(op, args, 2)
            return args[0] - args[1]
        case "multiply":
            result = _ONE
            for arg in args:
                result *= arg
            return result
        case "divide":
            _require_arg_count(op, args, 2)
            if args[1] == _ZERO:
                raise RegistryValidationError(
                    "formula expression divides by zero",
                    translated_message="errors.calc.divide_by_zero",
                )
            return args[0] / args[1]
        case "percent":
            _require_arg_count(op, args, 2)
            return args[0] * args[1] / Decimal("100")
        case "min":
            _require_non_empty(op, args)
            return min(args)
        case "max":
            _require_non_empty(op, args)
            return max(args)
        case "clamp":
            _require_arg_count(op, args, 3)
            return max(args[1], min(args[0], args[2]))
        case "negate":
            _require_arg_count(op, args, 1)
            return -args[0]
        case _:
            raise RegistryValidationError(f"formula expression uses unsupported op {op!r}")


def _evaluate_leaf(
    expression: FormulaExpression,
    *,
    values: Mapping[str, Decimal],
    binding_values: Mapping[str, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[str, Decimal],
    operand_refs: list[str],
    operand_values: list[Decimal],
) -> Decimal:
    if expression.literal is not None:
        return expression.literal
    if expression.casilla is not None:
        if expression.casilla not in values:
            raise RegistryValidationError(
                f"casilla {expression.casilla!r} referenced before evaluation",
                translated_message="errors.calc.casilla_referenced_before_evaluation",
                context={"casilla_id": expression.casilla},
            )
        value = values[expression.casilla]
        operand_refs.append(expression.casilla)
        operand_values.append(value)
        return value
    if expression.binding is not None:
        if expression.binding not in binding_values:
            raise RegistryValidationError(
                f"binding {expression.binding!r} has no supplied value",
                translated_message="errors.calc.binding_value_missing",
                context={"binding_id": expression.binding},
            )
        value = binding_values[expression.binding]
        operand_refs.append(expression.binding)
        operand_values.append(value)
        return value
    if expression.parameter is not None:
        parameter = parameters[expression.parameter]
        value = _resolve_parameter(parameter, date_context)
        operand_refs.append(expression.parameter)
        operand_values.append(value)
        return value
    if expression.relation is not None:
        if expression.relation not in relation_values:
            raise RegistryValidationError(
                f"relation {expression.relation!r} has no supplied value",
                translated_message="errors.calc.relation_value_missing",
                context={"relation_id": expression.relation},
            )
        value = relation_values[expression.relation]
        operand_refs.append(expression.relation)
        operand_values.append(value)
        return value
    raise RegistryValidationError(
        "empty formula expression",
        translated_message="errors.calc.empty_expression",
    )


def _compare(op: str, left: Decimal, right: Decimal) -> bool:
    if op == "less_than":
        return left < right
    if op == "less_equal":
        return left <= right
    if op == "greater_than":
        return left > right
    if op == "greater_equal":
        return left >= right
    if op == "equal":
        return left == right
    raise RegistryValidationError(f"formula expression uses unsupported comparison op {op!r}")


def _resolve_bracket(
    parameter: ParameterDefinition,
    base: Decimal,
    date_context: Mapping[str, date],
) -> Decimal:
    """Compute the cuota for ``base`` using parameter's piecewise-linear bracket schedule."""
    if parameter.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {parameter.id!r} must declare data_type='bracket_table' to use lookup_bracket"
        )
    if parameter.bracket_axis is None:
        raise RegistryValidationError(f"parameter {parameter.id!r} bracket_table requires bracket_axis")
    if parameter.bracket_axis not in date_context:
        raise RegistryValidationError(f"parameter {parameter.id!r} requires date axis {parameter.bracket_axis!r}")
    selected = date_context[parameter.bracket_axis]
    candidates = [
        b for b in parameter.brackets if b.valid_from <= selected and (b.valid_to is None or selected <= b.valid_to)
    ]
    if not candidates:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} has no bracket valid for {selected.isoformat()}",
            translated_message="errors.calc.bracket_no_window",
            context={"parameter_id": parameter.id, "filing_date": selected.isoformat()},
        )
    base = Decimal(base)
    if base < Decimal("0"):
        raise RegistryValidationError(
            f"parameter {parameter.id!r} lookup_bracket received negative base {base}",
            translated_message="errors.calc.bracket_negative_base",
            context={"parameter_id": parameter.id, "base": str(base)},
        )
    sorted_brackets = sorted(candidates, key=lambda b: b.lower_bound)
    selected_entry = None
    for entry in sorted_brackets:
        if entry.lower_bound <= base and (entry.upper_bound is None or base <= entry.upper_bound):
            selected_entry = entry
            break
    if selected_entry is None:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} has no bracket covering base {base}",
            translated_message="errors.calc.bracket_no_coverage",
            context={"parameter_id": parameter.id, "base": str(base)},
        )
    return selected_entry.fixed_addition + selected_entry.marginal_rate * (base - selected_entry.lower_bound)


def _resolve_parameter(parameter: ParameterDefinition, date_context: Mapping[str, date]) -> Decimal:
    if not parameter.values:
        raise RegistryValidationError(f"parameter {parameter.id!r} has no dated values")
    matches: list[DatedValue] = []
    for value in parameter.values:
        if value.date_axis not in date_context:
            raise RegistryValidationError(f"parameter {parameter.id!r} requires date axis {value.date_axis!r}")
        selected = date_context[value.date_axis]
        if value.valid_from <= selected and (value.valid_to is None or selected <= value.valid_to):
            matches.append(value)
    if len(matches) != 1:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} expected exactly one dated value, found {len(matches)}"
        )
    return matches[0].value


def _apply_rounding(value: Decimal, rounding: str | None) -> Decimal:
    if rounding is None:
        return value
    if rounding == "money-2":
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounding == "integer":
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    raise RegistryValidationError(f"unsupported rounding rule {rounding!r}")


def _reject_non_decimal(values: Mapping[str, Decimal], label: str) -> None:
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"{label} {key!r} must be a Decimal")


def _reject_non_string(values: Mapping[str, str], label: str) -> None:
    for key, value in values.items():
        if not isinstance(value, str) or not value:
            raise RegistryValidationError(f"{label} {key!r} must be a non-empty string")


def _reject_unknown_external_values(values: Mapping[str, Decimal], known_ids: set[str], label: str) -> None:
    unknown = sorted(set(values).difference(known_ids))
    if unknown:
        raise RegistryValidationError(f"unknown registry {label} ids: {unknown!r}")


def _require_arg_count(op: str, args: list[Decimal], count: int) -> None:
    if len(args) != count:
        raise RegistryValidationError(f"formula op {op!r} expects {count} args, got {len(args)}")


def _require_non_empty(op: str, args: list[Decimal]) -> None:
    if not args:
        raise RegistryValidationError(f"formula op {op!r} expects at least one arg")


def read_parameter(
    modelo_id: str,
    revision_id: str,
    parameter_id: str,
    *,
    date_context: Mapping[str, date],
    registry_root: Path | None = None,
) -> Decimal:
    """Resolve a registered registry parameter value for the given date context.

    Public delegate over the same ``_resolve_parameter`` logic the formula runtime
    uses. Non-formula consumers (the rental tier resolver, IVA category resolver,
    etc.) call this surface to read parameter values without going through a
    formula expression. Registry access goes through ``ValidatedRegistryAuthority``
    whether ``registry_root`` is provided or the bundled registry is used.

    Raises :class:`RegistryValidationError` if the modelo / revision / parameter
    is not registered, or if the date context selects 0 or >1 dated values.
    """
    from aeat.core.resources import bundled_path

    from ._authority import ValidatedRegistryAuthority

    root = registry_root if registry_root is not None else bundled_path("registry", "aeat")
    authority = ValidatedRegistryAuthority.load(root, source_root=bundled_path())
    try:
        modelo_match = authority.modelo(modelo_id)
    except RegistrySnapshotError as exc:
        raise RegistryValidationError(f"modelo {modelo_id!r} not registered in {root}") from exc
    revision = modelo_match.revisions.get(revision_id)
    if revision is None:
        raise RegistryValidationError(f"modelo {modelo_id!r} has no revision {revision_id!r}")
    parameter = next((p for p in revision.parameters if p.id == parameter_id), None)
    if parameter is None:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} not registered under modelo {modelo_id!r} revision {revision_id!r}"
        )
    return _resolve_parameter(parameter, date_context)
