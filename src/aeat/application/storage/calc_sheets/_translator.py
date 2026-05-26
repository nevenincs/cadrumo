"""Closed-form translator from registry `FormulaExpression` ASTs to
Google Sheets A1 formula strings.

The translator is the parity contract: a registry op evaluates to the
same per-casilla rounded Decimal locally and in Sheets if and only if
the formula this translator emits is a closed-form equivalent of the
local Decimal arithmetic.

Per-casilla rounding is applied by the engine driver, not by this
translator — `translate_formula` returns the unrounded expression and
the caller wraps it in `ROUND(expr, scale)` according to the
casilla's rounding rule. That separation keeps the translator a pure
expression compiler and concentrates rounding policy in one place.

Unsupported leaves and ops raise `TranslationError`. Today bindings
and relations are unsupported in the closed-form path (the caller
must pre-resolve binding values into Tarifas/Entradas cells before
invoking the engine); `TranslationError` carries enough context for
the caller to surface a typed CLI error.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Final

from ....core.errors import AeatError
from ....domain.calculations.registry._ids import BindingId, CasillaId, ParameterId, RelationId
from ....domain.calculations.registry._schema import FormulaExpression
from ._layout import SheetLayout


class TranslationError(AeatError):
    """A registry expression has no closed-form Sheets equivalent."""

    def __init__(self, message: str, *, op: str | None = None, hint: str | None = None) -> None:
        super().__init__(message)
        self.op = op
        self.hint = hint


_SUPPORTED_OPS: Final[frozenset[str]] = frozenset(
    {
        "add",
        "sum",
        "subtract",
        "multiply",
        "divide",
        "percent",
        "min",
        "max",
        "clamp",
        "negate",
        "copy",
        "lookup_parameter",
        "lookup_bracket",
        "lookup_bracket_by_ccaa",
        "lookup_parameter_by_entity_type",
        "previous_period_value",
        "previous_period_sum",
        "cross_model_sum",
        "if_then_else",
        "less_than",
        "less_equal",
        "greater_than",
        "greater_equal",
        "equal",
    }
)


def translate_formula(
    expression: FormulaExpression,
    *,
    layout: SheetLayout,
) -> str:
    """Compile a registry formula expression to a Sheets A1 expression.

    The returned string does NOT have a leading "=" sign and is NOT
    yet wrapped in ROUND(). It is the raw arithmetic body the engine
    will rounded-wrap based on the target casilla's rounding rule.
    """

    return _translate(expression, layout=layout)


def _translate(expression: FormulaExpression, *, layout: SheetLayout) -> str:
    if expression.op is None:
        return _translate_leaf(expression, layout=layout)
    op = expression.op
    if op not in _SUPPORTED_OPS:
        raise TranslationError(
            f"registry op {op!r} has no closed-form Sheets translation yet",
            op=op,
            hint="cross-revision relations are the only outstanding leaf gap",
        )
    # ``lookup_bracket`` / ``lookup_bracket_by_ccaa`` /
    # ``lookup_parameter_by_entity_type`` inspect their operand leaves
    # directly (parameter / binding / dispatch_table leaves are NOT
    # translated to A1 references — they resolve into bracket-range
    # expansions instead).
    if op == "lookup_bracket":
        return _translate_lookup_bracket(expression, layout=layout)
    if op == "lookup_bracket_by_ccaa":
        return _translate_lookup_bracket_by_ccaa(expression, layout=layout)
    if op == "lookup_parameter_by_entity_type":
        return _translate_lookup_parameter_by_entity_type(expression, layout=layout)
    args = [_translate(arg, layout=layout) for arg in expression.args]
    builder = _ARG_OP_BUILDERS.get(op)
    if builder is None:
        raise TranslationError(f"internal: op {op!r} fell through dispatch", op=op)
    return builder(op, args)


def _build_variadic_join(joiner: str, identity: str) -> Callable[[str, list[str]], str]:
    """Build ``({a}{joiner}{b}{joiner}…)`` with an identity for the empty case."""

    def builder(_op: str, args: list[str]) -> str:
        if not args:
            return identity
        return f"({joiner.join(args)})"

    return builder


def _build_required_variadic_join(joiner: str) -> Callable[[str, list[str]], str]:
    """Like :func:`_build_variadic_join` but requires at least one arg."""

    def builder(op: str, args: list[str]) -> str:
        if not args:
            raise TranslationError(f"{op} requires at least one arg", op=op)
        return f"({joiner.join(args)})"

    return builder


def _build_call(name: str) -> Callable[[str, list[str]], str]:
    """``MIN(a,b,…)`` / ``MAX(a,b,…)`` style call with one-or-more args."""

    def builder(op: str, args: list[str]) -> str:
        if not args:
            raise TranslationError(f"{op} requires at least one arg", op=op)
        return f"{name}({','.join(args)})"

    return builder


def _build_fixed_arity(arity: int, template: str) -> Callable[[str, list[str]], str]:
    """Format ``template`` with exactly ``arity`` positional args."""

    def builder(op: str, args: list[str]) -> str:
        _expect_arg_count(op, args, arity)
        return template.format(*args)

    return builder


_ARG_OP_BUILDERS: Mapping[str, Callable[[str, list[str]], str]] = {
    "add": _build_variadic_join("+", "0"),
    "sum": _build_variadic_join("+", "0"),
    "subtract": _build_fixed_arity(2, "({0}-{1})"),
    "multiply": _build_variadic_join("*", "1"),
    "divide": _build_fixed_arity(2, "IFERROR(({0})/({1}),0)"),
    "percent": _build_fixed_arity(2, "(({0})*({1})/100)"),
    "min": _build_call("MIN"),
    "max": _build_call("MAX"),
    "clamp": _build_fixed_arity(3, "MAX({1},MIN({0},{2}))"),
    "negate": _build_fixed_arity(1, "(-({0}))"),
    "copy": _build_fixed_arity(1, "({0})"),
    "lookup_parameter": _build_fixed_arity(1, "({0})"),
    "previous_period_value": _build_fixed_arity(1, "({0})"),
    "cross_model_sum": _build_fixed_arity(1, "({0})"),
    "previous_period_sum": _build_required_variadic_join("+"),
    # Local runtime: args[1] if args[0] != 0 else args[2].
    # Sheets equivalent: IF(<>0, then, else).
    "if_then_else": _build_fixed_arity(3, "IF(({0})<>0,{1},{2})"),
    "less_than": _build_fixed_arity(2, "IF({0}<{1},1,0)"),
    "less_equal": _build_fixed_arity(2, "IF({0}<={1},1,0)"),
    "greater_than": _build_fixed_arity(2, "IF({0}>{1},1,0)"),
    "greater_equal": _build_fixed_arity(2, "IF({0}>={1},1,0)"),
    "equal": _build_fixed_arity(2, "IF({0}={1},1,0)"),
}


def _translate_leaf(expression: FormulaExpression, *, layout: SheetLayout) -> str:
    if expression.literal is not None:
        return _format_decimal(expression.literal)
    if expression.casilla is not None:
        return _casilla_reference(expression.casilla, layout=layout)
    if expression.parameter is not None:
        return _parameter_reference(expression.parameter, layout=layout)
    if expression.binding is not None:
        return _binding_reference(expression.binding, layout=layout)
    if expression.relation is not None:
        return _relation_reference(expression.relation, layout=layout)
    if expression.dispatch_table is not None:
        raise TranslationError(
            "dispatch_table leaves are only valid inside lookup_bracket_by_ccaa "
            "(they cannot be translated to an A1 reference on their own)",
        )
    raise TranslationError("empty formula leaf encountered")


def _bracket_lookup_formula(*, base_a1: str, parameter: ParameterId, layout: SheetLayout) -> str:
    """Emit the closed-form INDEX/MATCH bracket expression.

    The expression mirrors the runtime's `_resolve_bracket`:

        fixed_addition[i] + marginal_rate[i] * (base - lower_bound[i])

    where `i = MATCH(base, lower_bound_range, 1)` selects the largest
    `lower_bound` ≤ `base` in the sort-1 lower-bound range. The
    layout planner pre-sorts the emitted bracket rows and filters them
    by snapshot date so the MATCH contract holds.
    """

    ranges = layout.bracket_ranges.get(parameter)
    if ranges is None:
        raise TranslationError(
            f"parameter {parameter!r} is referenced by a lookup_bracket op but has no bracket ranges in the layout",
            op="lookup_bracket",
            hint="the layout planner must emit Tarifas bracket rows for every "
            "bracket_table parameter the formulas reach",
        )
    # MATCH with sort=1 returns the position of the largest entry ≤ base.
    match_expr = f"MATCH({base_a1},{ranges.lower_bound},1)"
    fa = f"INDEX({ranges.fixed_addition},{match_expr})"
    mr = f"INDEX({ranges.marginal_rate},{match_expr})"
    lo = f"INDEX({ranges.lower_bound},{match_expr})"
    return f"({fa}+{mr}*({base_a1}-{lo}))"


def _translate_lookup_bracket(expression: FormulaExpression, *, layout: SheetLayout) -> str:
    if len(expression.args) != 2:
        raise TranslationError(
            "lookup_bracket expects 2 args (base, bracket_parameter)",
            op="lookup_bracket",
        )
    base_expr, bracket_arg = expression.args
    if bracket_arg.parameter is None:
        raise TranslationError(
            "lookup_bracket args[1] must be a parameter leaf",
            op="lookup_bracket",
        )
    base_a1 = _translate(base_expr, layout=layout)
    return _bracket_lookup_formula(base_a1=base_a1, parameter=bracket_arg.parameter, layout=layout)


def _translate_lookup_bracket_by_ccaa(
    expression: FormulaExpression,
    *,
    layout: SheetLayout,
) -> str:
    """Emit a SWITCH that dispatches a bracket lookup by CCAA binding.

    Runtime semantics: the CCAA binding's value selects one of the
    bracket-table parameters from the dispatch_table mapping; the
    selected bracket parameter then runs through the same
    `_resolve_bracket` path as `lookup_bracket`. The closed Sheets
    form is a `SWITCH` over the binding cell whose branches are one
    full INDEX/MATCH bracket expansion each. Without a default branch
    `SWITCH` returns `#N/A` for an unmapped CCAA — that mirrors the
    runtime's `RegistryValidationError` for missing dispatch keys.
    """

    if len(expression.args) != 3:
        raise TranslationError(
            "lookup_bracket_by_ccaa expects 3 args (base, ccaa_binding, dispatch_table)",
            op="lookup_bracket_by_ccaa",
        )
    base_expr, binding_arg, dispatch_arg = expression.args
    if binding_arg.binding is None:
        raise TranslationError(
            "lookup_bracket_by_ccaa args[1] must be a binding leaf",
            op="lookup_bracket_by_ccaa",
        )
    if dispatch_arg.dispatch_table is None:
        raise TranslationError(
            "lookup_bracket_by_ccaa args[2] must be a dispatch_table leaf",
            op="lookup_bracket_by_ccaa",
        )
    base_a1 = _translate(base_expr, layout=layout)
    binding_a1 = _binding_reference(binding_arg.binding, layout=layout)
    branches: list[str] = []
    for ccaa_code, parameter_id in sorted(dispatch_arg.dispatch_table.items()):
        bracket_expr = _bracket_lookup_formula(base_a1=base_a1, parameter=parameter_id, layout=layout)
        # Sheets string literals must be double-quoted; embedded quotes
        # are escaped by doubling. CCAA codes never contain quotes
        # today, but the escape is applied unconditionally so a future
        # value with a quote cannot break the formula.
        safe_code = ccaa_code.replace('"', '""')
        branches.append(f'"{safe_code}",{bracket_expr}')
    return f"SWITCH({binding_a1},{','.join(branches)})"


def _translate_lookup_parameter_by_entity_type(
    expression: FormulaExpression,
    *,
    layout: SheetLayout,
) -> str:
    """Emit a SWITCH that dispatches a scalar parameter lookup by an enum binding.

    Runtime semantics: an enum binding (e.g. `entity_type`) selects
    one of several scalar parameters from the dispatch_table mapping;
    the selected parameter resolves to its temporally-active dated
    value. Closed Sheets form is a `SWITCH` over the binding cell
    whose branches each reference the dispatched parameter's
    `Tarifas` anchor cell directly. Without a default branch SWITCH
    returns `#N/A` for an unmapped enum key — matching the runtime's
    `RegistryValidationError` semantics.
    """

    if len(expression.args) != 3:
        raise TranslationError(
            "lookup_parameter_by_entity_type expects 3 args (placeholder, binding, dispatch_table)",
            op="lookup_parameter_by_entity_type",
        )
    _placeholder_expr, binding_arg, dispatch_arg = expression.args
    if binding_arg.binding is None:
        raise TranslationError(
            "lookup_parameter_by_entity_type args[1] must be a binding leaf",
            op="lookup_parameter_by_entity_type",
        )
    if dispatch_arg.dispatch_table is None:
        raise TranslationError(
            "lookup_parameter_by_entity_type args[2] must be a dispatch_table leaf",
            op="lookup_parameter_by_entity_type",
        )
    binding_a1 = _binding_reference(binding_arg.binding, layout=layout)
    branches: list[str] = []
    for enum_key, parameter_id in sorted(dispatch_arg.dispatch_table.items()):
        param_cell = layout.parameter_cells.get(parameter_id)
        if param_cell is None:
            raise TranslationError(
                f"parameter {parameter_id!r} is referenced by lookup_parameter_by_entity_type "
                f"but has no anchor cell in the layout",
                op="lookup_parameter_by_entity_type",
                hint="the layout planner must mirror every dispatched parameter into Tarifas",
            )
        safe_key = enum_key.replace('"', '""')
        branches.append(f'"{safe_key}",{param_cell.anchor.qualified()}')
    return f"SWITCH({binding_a1},{','.join(branches)})"


def _casilla_reference(casilla: CasillaId, *, layout: SheetLayout) -> str:
    address = layout.address_for(casilla)
    return address.qualified()


def _binding_reference(binding: BindingId, *, layout: SheetLayout) -> str:
    try:
        address = layout.address_for_binding(binding)
    except KeyError as exc:
        raise TranslationError(
            f"binding {binding!r} has no anchor cell in the layout",
            hint="the layout planner must reserve a cell for every referenced binding",
        ) from exc
    return address.qualified()


def _relation_reference(relation: RelationId, *, layout: SheetLayout) -> str:
    try:
        address = layout.address_for_relation(relation)
    except KeyError as exc:
        raise TranslationError(
            f"relation {relation!r} has no anchor cell in the layout",
            hint="the layout planner must mirror every referenced relation into Tarifas",
        ) from exc
    return address.qualified()


def _parameter_reference(parameter: ParameterId, *, layout: SheetLayout) -> str:
    cell = layout.parameter_cells.get(parameter)
    if cell is None:
        raise TranslationError(
            f"parameter {parameter!r} has no anchor cell in the layout",
            hint="the layout planner must mirror every referenced parameter into Tarifas",
        )
    return cell.anchor.qualified()


def _format_decimal(value: Decimal) -> str:
    # Sheets accepts Decimal literals as plain numbers. We render in
    # fixed-point form (no scientific notation) so very large or very
    # small values still parse as numbers.
    text = format(value, "f")
    return text if text else "0"


def _expect_arg_count(op: str, args: list[str], expected: int) -> None:
    if len(args) != expected:
        raise TranslationError(
            f"op {op!r} expects {expected} args; got {len(args)}",
            op=op,
        )


__all__ = ["TranslationError", "translate_formula"]
