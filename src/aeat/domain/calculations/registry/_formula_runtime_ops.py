"""Formula-runtime operation helpers for :class:`ModeloRevision` calculations.

Input validation helpers inspect the registry revision before formula execution
accepts casilla inputs. The public :func:`read_parameter` helper loads a
:class:`ValidatedRegistryAuthority` so ad hoc parameter reads resolve through the
same registry authority used by snapshot-backed runtime callers.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ....core.money import round_to_cents as _round_to_cents
from ._casilla_membership import undeclared_casilla_ids
from ._errors import RegistrySnapshotError, RegistryValidationError
from ._ids import CasillaId, validated_casilla_id
from ._schema import DatedValue, ModeloRevision, ParameterDefinition

_ZERO = Decimal("0")
_ONE = Decimal("1")
_COMPARISON_OPS = frozenset({"less_than", "less_equal", "greater_than", "greater_equal", "equal"})
_UNARY_PASSTHROUGH_OPS = frozenset({"copy", "lookup_parameter", "previous_period_value", "cross_model_sum"})


def evaluate_args_op(op: str, args: list[Decimal]) -> Decimal:
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


def resolve_bracket(
    parameter: ParameterDefinition,
    base: Decimal,
    date_context: Mapping[str, date],
) -> Decimal:
    if parameter.data_type != "bracket_table":
        raise RegistryValidationError(
            f"parameter {parameter.id!r} must declare data_type='bracket_table' to use lookup_bracket",
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
            context={"parameter_id": parameter.id, "as_of": selected.isoformat()},
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


def resolve_parameter(parameter: ParameterDefinition, date_context: Mapping[str, date]) -> Decimal:
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
            f"parameter {parameter.id!r} expected exactly one dated value, found {len(matches)}",
        )
    return matches[0].value


def apply_rounding(value: Decimal, rounding: str | None) -> Decimal:
    if rounding is None:
        return value
    if rounding == "money-2":
        return _round_to_cents(value)
    if rounding == "integer":
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    raise RegistryValidationError(f"unsupported rounding rule {rounding!r}")


def reject_non_decimal[Key](items: Mapping[Key, Decimal], label: str) -> None:
    for key, value in items.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"{label} {key!r} must be a Decimal")


def validated_decimal_input_casilla_ids[InputKey, InputValue](
    inputs: Mapping[InputKey, InputValue],
    *,
    revision: ModeloRevision,
) -> dict[CasillaId, Decimal]:
    invalid = tuple(repr(key) for key in inputs if not isinstance(key, str))
    if invalid:
        raise RegistryValidationError(
            f"input keys must be canonical casilla.id strings: {sorted(invalid)!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(sorted(invalid))},
        )
    malformed: list[str] = []
    canonical_inputs: dict[CasillaId, InputValue] = {}
    for key in inputs:
        try:
            canonical_inputs[validated_casilla_id(key, surface="input casilla.id")] = inputs[key]
        except ValueError:
            malformed.append(str(key))
    if malformed:
        raise RegistryValidationError(
            f"input keys must be canonical casilla.id strings: {sorted(malformed)!r}",
            translated_message="errors.calc.unknown_input_casillas",
            context={"casilla_ids": ",".join(sorted(malformed))},
        )
    unknown = undeclared_casilla_ids(revision, canonical_inputs)
    if unknown:
        raise RegistryValidationError.for_unknown_input_casilla_ids(casilla_ids=unknown)
    resolved_inputs: dict[CasillaId, Decimal] = {}
    for key, value in canonical_inputs.items():
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"input {key!r} must be a Decimal")
        resolved_inputs[key] = value
    return resolved_inputs


def reject_non_string[Key](values: Mapping[Key, str], label: str) -> None:
    for key, value in values.items():
        if not isinstance(value, str) or not value:
            raise RegistryValidationError(f"{label} {key!r} must be a non-empty string")


def reject_unknown_external_values[Key](items: Mapping[Key, Decimal], known_ids: set[Key], label: str) -> None:
    unknown = sorted(set(items).difference(known_ids))
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
    from ....core.resources import bundled_path
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
            f"parameter {parameter_id!r} not registered under modelo {modelo_id!r} revision {revision_id!r}",
        )
    return resolve_parameter(parameter, date_context)
