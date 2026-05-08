"""Registry-backed formula runtime using typed operation graphs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ._errors import RegistryValidationError
from ._loader import load_registry_tree
from ._runtime_graph import formula_evaluation_order
from ._schema import DatedValue, FormulaExpression, ModeloRevision, ParameterDefinition, RegistrySnapshot

_ZERO = Decimal("0")
_ONE = Decimal("1")


class RegistryCalculationEntry(BaseModel):
    """One trace row emitted by the registry formula runtime."""

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
    """Calculated outputs and trace entries for one registry snapshot."""

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
        raise RegistryValidationError(f"unknown registry input casilla ids: {unknown!r}")
    formula_targets = {formula.target for formula in revision.formulas}
    computed = sorted(
        casilla_id
        for casilla_id in inputs
        if casillas[casilla_id].input_kind == "computed" or casilla_id in formula_targets
    )
    if computed:
        raise RegistryValidationError(f"computed registry casillas cannot be supplied as inputs: {computed!r}")
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
    op = expression.op
    if op == "lookup_bracket":
        if len(expression.args) != 2:
            raise RegistryValidationError("formula op 'lookup_bracket' expects 2 args")
        bracket_arg = expression.args[1]
        if bracket_arg.parameter is None:
            raise RegistryValidationError(
                "formula op 'lookup_bracket' requires args[1] to be a parameter leaf"
            )
        bracket_param = parameters.get(bracket_arg.parameter)
        if bracket_param is None:
            raise RegistryValidationError(f"parameter {bracket_arg.parameter!r} not registered")
        if bracket_param.data_type != "bracket_table":
            raise RegistryValidationError(
                f"parameter {bracket_arg.parameter!r} must declare data_type='bracket_table' "
                f"to be used by lookup_bracket"
            )
        base = _evaluate_expression(
            expression.args[0],
            values=values,
            binding_values=binding_values,
            parameters=parameters,
            date_context=date_context,
            relation_values=relation_values,
            operand_refs=operand_refs,
            operand_values=operand_values,
            enum_binding_values=resolved_enum_bindings,
        )
        operand_refs.append(bracket_arg.parameter)
        result = _resolve_bracket(bracket_param, base, date_context)
        operand_values.append(result)
        return result
    if op == "lookup_bracket_by_ccaa":
        if len(expression.args) != 3:
            raise RegistryValidationError("formula op 'lookup_bracket_by_ccaa' expects 3 args")
        binding_arg = expression.args[1]
        dispatch_arg = expression.args[2]
        if binding_arg.binding is None:
            raise RegistryValidationError(
                "formula op 'lookup_bracket_by_ccaa' requires args[1] to be a binding leaf"
            )
        if dispatch_arg.dispatch_table is None:
            raise RegistryValidationError(
                "formula op 'lookup_bracket_by_ccaa' requires args[2] to be a dispatch_table leaf"
            )
        if binding_arg.binding not in resolved_enum_bindings:
            raise RegistryValidationError(
                f"enum binding {binding_arg.binding!r} has no supplied value; "
                f"required by lookup_bracket_by_ccaa"
            )
        dispatch_key = resolved_enum_bindings[binding_arg.binding]
        dispatch_table = dispatch_arg.dispatch_table
        if dispatch_key not in dispatch_table:
            raise RegistryValidationError(
                f"lookup_bracket_by_ccaa dispatch_table is missing CCAA {dispatch_key!r} "
                f"(declared keys: {sorted(dispatch_table)})"
            )
        bracket_param_id = dispatch_table[dispatch_key]
        bracket_param = parameters.get(bracket_param_id)
        if bracket_param is None:
            raise RegistryValidationError(f"parameter {bracket_param_id!r} not registered")
        if bracket_param.data_type != "bracket_table":
            raise RegistryValidationError(
                f"parameter {bracket_param_id!r} must declare data_type='bracket_table' "
                f"to be used by lookup_bracket_by_ccaa"
            )
        base = _evaluate_expression(
            expression.args[0],
            values=values,
            binding_values=binding_values,
            parameters=parameters,
            date_context=date_context,
            relation_values=relation_values,
            operand_refs=operand_refs,
            operand_values=operand_values,
            enum_binding_values=resolved_enum_bindings,
        )
        operand_refs.append(binding_arg.binding)
        operand_refs.append(bracket_param_id)
        result = _resolve_bracket(bracket_param, base, date_context)
        operand_values.append(result)
        return result
    args = [
        _evaluate_expression(
            arg,
            values=values,
            binding_values=binding_values,
            parameters=parameters,
            date_context=date_context,
            relation_values=relation_values,
            operand_refs=operand_refs,
            operand_values=operand_values,
            enum_binding_values=resolved_enum_bindings,
        )
        for arg in expression.args
    ]
    if op in {"add", "sum"}:
        return sum(args, _ZERO)
    if op == "subtract":
        _require_arg_count(op, args, 2)
        return args[0] - args[1]
    if op == "multiply":
        result = _ONE
        for arg in args:
            result *= arg
        return result
    if op == "divide":
        _require_arg_count(op, args, 2)
        if args[1] == _ZERO:
            raise RegistryValidationError("formula expression divides by zero")
        return args[0] / args[1]
    if op == "percent":
        _require_arg_count(op, args, 2)
        return args[0] * args[1] / Decimal("100")
    if op in {"less_than", "less_equal", "greater_than", "greater_equal", "equal"}:
        _require_arg_count(op, args, 2)
        return _ONE if _compare(op, args[0], args[1]) else _ZERO
    if op == "min":
        _require_non_empty(op, args)
        return min(args)
    if op == "max":
        _require_non_empty(op, args)
        return max(args)
    if op == "clamp":
        _require_arg_count(op, args, 3)
        return max(args[1], min(args[0], args[2]))
    if op == "negate":
        _require_arg_count(op, args, 1)
        return -args[0]
    if op in {"copy", "lookup_parameter", "previous_period_value", "cross_model_sum"}:
        _require_arg_count(op, args, 1)
        return args[0]
    if op == "previous_period_sum":
        _require_non_empty(op, args)
        return sum(args, _ZERO)
    if op == "if_then_else":
        _require_arg_count(op, args, 3)
        return args[1] if args[0] != _ZERO else args[2]
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
            raise RegistryValidationError(f"casilla {expression.casilla!r} referenced before evaluation")
        value = values[expression.casilla]
        operand_refs.append(expression.casilla)
        operand_values.append(value)
        return value
    if expression.binding is not None:
        if expression.binding not in binding_values:
            raise RegistryValidationError(f"binding {expression.binding!r} has no supplied value")
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
            raise RegistryValidationError(f"relation {expression.relation!r} has no supplied value")
        value = relation_values[expression.relation]
        operand_refs.append(expression.relation)
        operand_values.append(value)
        return value
    raise RegistryValidationError("empty formula expression")


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
        raise RegistryValidationError(
            f"parameter {parameter.id!r} requires date axis {parameter.bracket_axis!r}"
        )
    selected = date_context[parameter.bracket_axis]
    candidates = [
        b
        for b in parameter.brackets
        if b.valid_from <= selected and (b.valid_to is None or selected <= b.valid_to)
    ]
    if not candidates:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} has no bracket valid for {selected.isoformat()}"
        )
    base = Decimal(base)
    if base < Decimal("0"):
        raise RegistryValidationError(
            f"parameter {parameter.id!r} lookup_bracket received negative base {base}"
        )
    sorted_brackets = sorted(candidates, key=lambda b: b.lower_bound)
    selected_entry = None
    for entry in sorted_brackets:
        if entry.lower_bound <= base and (entry.upper_bound is None or base <= entry.upper_bound):
            selected_entry = entry
            break
    if selected_entry is None:
        raise RegistryValidationError(
            f"parameter {parameter.id!r} has no bracket covering base {base}"
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
    formula expression. The registry tree loads via ``load_registry_tree`` when
    ``registry_root`` is provided; otherwise the default
    ``<PROJECT_ROOT>/registry/aeat`` is used.

    Raises :class:`RegistryValidationError` if the modelo / revision / parameter
    is not registered, or if the date context selects 0 or >1 dated values.
    """
    from aeat.core.paths import PROJECT_ROOT

    root = registry_root if registry_root is not None else PROJECT_ROOT / "registry" / "aeat"
    modelos, _catalogues = load_registry_tree(root)
    modelo_match = next((m for m in modelos if m.id == modelo_id), None)
    if modelo_match is None:
        raise RegistryValidationError(f"modelo {modelo_id!r} not registered in {root}")
    revision = modelo_match.revisions.get(revision_id)
    if revision is None:
        raise RegistryValidationError(f"modelo {modelo_id!r} has no revision {revision_id!r}")
    parameter = next((p for p in revision.parameters if p.id == parameter_id), None)
    if parameter is None:
        raise RegistryValidationError(
            f"parameter {parameter_id!r} not registered under modelo {modelo_id!r} revision {revision_id!r}"
        )
    return _resolve_parameter(parameter, date_context)
