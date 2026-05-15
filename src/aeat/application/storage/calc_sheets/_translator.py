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

from decimal import Decimal
from typing import Final

from ....domain.calculations.registry._ids import BindingId, CasillaId, ParameterId, RelationId
from ....domain.calculations.registry._schema import FormulaExpression
from ._layout import SheetLayout


class TranslationError(Exception):
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
    # `lookup_bracket` and `lookup_bracket_by_ccaa` must inspect their
    # operand leaves directly (parameter / binding / dispatch_table
    # leaves are NOT translated to A1 references — they resolve into
    # bracket-range expansions instead). Handle them before the
    # general recursive arg translation.
    if op == "lookup_bracket":
        return _translate_lookup_bracket(expression, layout=layout)
    if op == "lookup_bracket_by_ccaa":
        return _translate_lookup_bracket_by_ccaa(expression, layout=layout)
    if op == "lookup_parameter_by_entity_type":
        return _translate_lookup_parameter_by_entity_type(expression, layout=layout)
    args = [_translate(arg, layout=layout) for arg in expression.args]
    if op in {"add", "sum"}:
        if not args:
            return "0"
        return f"({'+'.join(args)})"
    if op == "subtract":
        _expect_arg_count(op, args, 2)
        return f"({args[0]}-{args[1]})"
    if op == "multiply":
        if not args:
            return "1"
        return f"({'*'.join(args)})"
    if op == "divide":
        _expect_arg_count(op, args, 2)
        return f"IFERROR(({args[0]})/({args[1]}),0)"
    if op == "percent":
        _expect_arg_count(op, args, 2)
        return f"(({args[0]})*({args[1]})/100)"
    if op == "min":
        if not args:
            raise TranslationError("min requires at least one arg", op=op)
        return f"MIN({','.join(args)})"
    if op == "max":
        if not args:
            raise TranslationError("max requires at least one arg", op=op)
        return f"MAX({','.join(args)})"
    if op == "clamp":
        _expect_arg_count(op, args, 3)
        return f"MAX({args[1]},MIN({args[0]},{args[2]}))"
    if op == "negate":
        _expect_arg_count(op, args, 1)
        return f"(-({args[0]}))"
    if op in {"copy", "lookup_parameter", "previous_period_value", "cross_model_sum"}:
        _expect_arg_count(op, args, 1)
        return f"({args[0]})"
    if op == "previous_period_sum":
        if not args:
            raise TranslationError("previous_period_sum requires at least one arg", op=op)
        return f"({'+'.join(args)})"
    if op == "if_then_else":
        _expect_arg_count(op, args, 3)
        # Local runtime: args[1] if args[0] != 0 else args[2].
        # Sheets equivalent: IF(<>0, then, else).
        return f"IF(({args[0]})<>0,{args[1]},{args[2]})"
    if op == "less_than":
        _expect_arg_count(op, args, 2)
        return f"IF({args[0]}<{args[1]},1,0)"
    if op == "less_equal":
        _expect_arg_count(op, args, 2)
        return f"IF({args[0]}<={args[1]},1,0)"
    if op == "greater_than":
        _expect_arg_count(op, args, 2)
        return f"IF({args[0]}>{args[1]},1,0)"
    if op == "greater_equal":
        _expect_arg_count(op, args, 2)
        return f"IF({args[0]}>={args[1]},1,0)"
    if op == "equal":
        _expect_arg_count(op, args, 2)
        return f"IF({args[0]}={args[1]},1,0)"
    raise TranslationError(f"internal: op {op!r} fell through dispatch", op=op)


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
