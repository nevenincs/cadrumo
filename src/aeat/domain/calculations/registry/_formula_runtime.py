"""Registry-backed formula runtime using typed operation graphs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from pydantic import BaseModel, ConfigDict

from ._errors import RegistryValidationError
from ._runtime_graph import formula_evaluation_order
from ._schema import DatedValue, FormulaArg, FormulaDefinition, ModeloRevision, ParameterDefinition, RegistrySnapshot

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
    relation_values: Mapping[str, Decimal] | None = None,
) -> RegistryCalculationResult:
    """Evaluate all computed formulas in a validated registry snapshot."""

    _reject_non_decimal(inputs, "input")
    resolved_relations = relation_values or {}
    _reject_non_decimal(resolved_relations, "relation")

    revision = snapshot.revision
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
            value = _evaluate_formula(
                formula,
                values=values,
                parameters=parameters,
                date_context=date_context,
                relation_values=resolved_relations,
                operand_refs=operand_refs,
                operand_values=operand_values,
            )
            value = _apply_rounding(value, formula.rounding)
            values[target] = value
            entries.append(
                RegistryCalculationEntry(
                    formula_id=formula.id,
                    target=target,
                    op=formula.op,
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
    values: dict[str, Decimal] = {}
    for casilla in revision.casillas:
        if casilla.input_kind == "computed":
            continue
        values[casilla.id] = inputs.get(casilla.id, _ZERO)
    return values


def _evaluate_formula(
    formula: FormulaDefinition,
    *,
    values: Mapping[str, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[str, Decimal],
    operand_refs: list[str],
    operand_values: list[Decimal],
) -> Decimal:
    args = [
        _evaluate_arg(
            arg,
            values=values,
            parameters=parameters,
            date_context=date_context,
            relation_values=relation_values,
            operand_refs=operand_refs,
            operand_values=operand_values,
        )
        for arg in formula.args
    ]
    op = formula.op
    if op in {"add", "sum"}:
        return sum(args, _ZERO)
    if op == "subtract":
        _require_arg_count(formula, args, 2)
        return args[0] - args[1]
    if op == "multiply":
        result = _ONE
        for arg in args:
            result *= arg
        return result
    if op == "divide":
        _require_arg_count(formula, args, 2)
        if args[1] == _ZERO:
            raise RegistryValidationError(f"formula {formula.id!r} divides by zero")
        return args[0] / args[1]
    if op == "percent":
        _require_arg_count(formula, args, 2)
        return args[0] * args[1] / Decimal("100")
    if op == "min":
        _require_non_empty(formula, args)
        return min(args)
    if op == "max":
        _require_non_empty(formula, args)
        return max(args)
    if op == "clamp":
        _require_arg_count(formula, args, 3)
        return max(args[1], min(args[0], args[2]))
    if op == "negate":
        _require_arg_count(formula, args, 1)
        return -args[0]
    if op in {"copy", "lookup_parameter", "previous_period_value", "cross_model_sum"}:
        _require_arg_count(formula, args, 1)
        return args[0]
    if op == "previous_period_sum":
        _require_non_empty(formula, args)
        return sum(args, _ZERO)
    if op == "if_then_else":
        _require_arg_count(formula, args, 3)
        return args[1] if args[0] != _ZERO else args[2]
    raise RegistryValidationError(f"formula {formula.id!r} uses unsupported op {op!r}")


def _evaluate_arg(
    arg: FormulaArg,
    *,
    values: Mapping[str, Decimal],
    parameters: Mapping[str, ParameterDefinition],
    date_context: Mapping[str, date],
    relation_values: Mapping[str, Decimal],
    operand_refs: list[str],
    operand_values: list[Decimal],
) -> Decimal:
    if arg.literal is not None:
        return arg.literal
    if arg.casilla is not None:
        if arg.casilla not in values:
            raise RegistryValidationError(f"casilla {arg.casilla!r} referenced before evaluation")
        value = values[arg.casilla]
        operand_refs.append(arg.casilla)
        operand_values.append(value)
        return value
    if arg.parameter is not None:
        parameter = parameters[arg.parameter]
        value = _resolve_parameter(parameter, date_context)
        operand_refs.append(arg.parameter)
        operand_values.append(value)
        return value
    if arg.relation is not None:
        if arg.relation not in relation_values:
            raise RegistryValidationError(f"relation {arg.relation!r} has no supplied value")
        value = relation_values[arg.relation]
        operand_refs.append(arg.relation)
        operand_values.append(value)
        return value
    raise RegistryValidationError("empty formula arg")


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


def _require_arg_count(formula: FormulaDefinition, args: list[Decimal], count: int) -> None:
    if len(args) != count:
        raise RegistryValidationError(f"formula {formula.id!r} expects {count} args, got {len(args)}")


def _require_non_empty(formula: FormulaDefinition, args: list[Decimal]) -> None:
    if not args:
        raise RegistryValidationError(f"formula {formula.id!r} expects at least one arg")
