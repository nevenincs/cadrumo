"""Closed-form translator from registry ``FormulaExpression`` ASTs to Google Sheets A1 formula strings.

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
from typing import Final

from ....core.casilla_id import CasillaId
from ....core.decimal.formatting import format_decimal
from ....core.errors.hierarchy import CadrumoError
from ....domain.calculations.registry.ids import (
    BindingId,
    ParameterId,
    RelationId,
)
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ._layout import SheetLayout
from .errors import CalcSheetsEngineError

type SheetA1Reference = str


class TranslationError(CadrumoError):
    """A registry expression has no closed-form Sheets equivalent."""

    def __init__(self, *, op: str | None = None, hint: str | None = None) -> None:
        context: dict[str, object] = {"reason": "formula_translation_failed"}
        if op is not None and op in _SUPPORTED_OPS:
            context["op"] = op
        elif op is not None:
            context["unsupported_op"] = True
        super().__init__(
            "formula expression cannot be translated to a spreadsheet formula",
            context=context,
            translated_message="application.storage.calc_sheets.translator.errors.translation_failed",
        )
        self.op = op if op is not None and op in _SUPPORTED_OPS else None
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
        "lookup_bracket_by_entity_type",
        "lookup_parameter_by_entity_type",
        "age_at_year_end",
        "previous_period_value",
        "previous_period_sum",
        "cross_model_sum",
        "if_then_else",
        "less_than",
        "less_equal",
        "greater_than",
        "greater_equal",
        "equal",
    },
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


def is_translatable(
    expression: FormulaExpression,
    *,
    layout: SheetLayout,
) -> bool:
    """Return whether `expression` has a closed-form Sheets translation.

    This is the honest ``translate_formula`` would-succeed probe: it
    attempts the full closed-form compilation against the same layout and
    reports failure iff a :class:`TranslationError` is raised (for an
    unsupported op or a leaf the layout has not materialised). It never
    re-implements the supported-op set, so it cannot drift from the real
    translator.
    """
    try:
        _translate(expression, layout=layout)
    except TranslationError:
        return False
    return True


def _translate(expression: FormulaExpression, *, layout: SheetLayout) -> str:
    if expression.op is None:
        return _translate_leaf(expression, layout=layout)
    op = expression.op
    if op not in _SUPPORTED_OPS:
        raise TranslationError(
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
    if op in ("lookup_bracket_by_ccaa", "lookup_bracket_by_entity_type"):
        return _translate_lookup_bracket_by_binding(expression, layout=layout, op=op)
    if op == "lookup_parameter_by_entity_type":
        return _translate_lookup_parameter_by_entity_type(expression, layout=layout)
    if op == "age_at_year_end":
        return _translate_age_at_year_end(expression, layout=layout)
    args = [_translate(arg, layout=layout) for arg in expression.args]
    builder = _ARG_OP_BUILDERS.get(op)
    if builder is None:
        raise TranslationError(op=op)
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
            raise TranslationError(op=op)
        return f"({joiner.join(args)})"

    return builder


def _build_call(name: str) -> Callable[[str, list[str]], str]:
    """``MIN(a,b,…)`` / ``MAX(a,b,…)`` style call with one-or-more args."""

    def builder(op: str, args: list[str]) -> str:
        if not args:
            raise TranslationError(op=op)
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
        return format_decimal(expression.literal)
    if expression.casilla_id is not None:
        return _casilla_cell_reference(expression.casilla_id, layout=layout)
    if expression.parameter is not None:
        return _parameter_reference(expression.parameter, layout=layout)
    if expression.binding is not None:
        return _binding_reference(expression.binding, layout=layout)
    if expression.relation is not None:
        return _relation_reference(expression.relation, layout=layout)
    if expression.dispatch_table is not None:
        raise TranslationError()
    raise TranslationError()


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
            op="lookup_bracket",
        )
    base_expr, bracket_arg = expression.args
    if bracket_arg.parameter is None:
        raise TranslationError(
            op="lookup_bracket",
        )
    base_a1 = _translate(base_expr, layout=layout)
    return _bracket_lookup_formula(base_a1=base_a1, parameter=bracket_arg.parameter, layout=layout)


def _translate_lookup_bracket_by_binding(
    expression: FormulaExpression,
    *,
    layout: SheetLayout,
    op: str,
) -> str:
    """Emit a SWITCH that dispatches a bracket lookup by an enum/CCAA binding.

    Shared by ``lookup_bracket_by_ccaa`` (dispatch by the CCAA binding) and
    ``lookup_bracket_by_entity_type`` (dispatch by an entity-type / legal-form
    enum binding, e.g. the LIS Art. 29.1 micro-empresa two-tranche scale on
    Modelo 200). Both carry args (base, binding, dispatch_table): the binding's
    value selects one of the bracket-table parameters from the dispatch_table,
    and the selected bracket runs the same ``_resolve_bracket`` path as
    ``lookup_bracket``. The closed Sheets form is a ``SWITCH`` over the binding
    cell whose branches are one full INDEX/MATCH bracket expansion each. Without
    a default branch ``SWITCH`` returns ``#N/A`` for an unmapped key — mirroring
    the runtime's ``RegistryValidationError`` for missing dispatch keys.
    """
    if len(expression.args) != 3:
        raise TranslationError(
            op=op,
        )
    base_expr, binding_arg, dispatch_arg = expression.args
    if binding_arg.binding is None:
        raise TranslationError(
            op=op,
        )
    if dispatch_arg.dispatch_table is None:
        raise TranslationError(
            op=op,
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
            op="lookup_parameter_by_entity_type",
        )
    _placeholder_expr, binding_arg, dispatch_arg = expression.args
    if binding_arg.binding is None:
        raise TranslationError(
            op="lookup_parameter_by_entity_type",
        )
    if dispatch_arg.dispatch_table is None:
        raise TranslationError(
            op="lookup_parameter_by_entity_type",
        )
    binding_a1 = _binding_reference(binding_arg.binding, layout=layout)
    branches: list[str] = []
    for enum_key, parameter_id in sorted(dispatch_arg.dispatch_table.items()):
        param_cell = layout.parameter_cells.get(parameter_id)
        if param_cell is None:
            raise TranslationError(
                op="lookup_parameter_by_entity_type",
                hint="the layout planner must mirror every dispatched parameter into Tarifas",
            )
        safe_key = enum_key.replace('"', '""')
        branches.append(f'"{safe_key}",{param_cell.anchor.qualified()}')
    return f"SWITCH({binding_a1},{','.join(branches)})"


def _translate_age_at_year_end(expression: FormulaExpression, *, layout: SheetLayout) -> str:
    """Emit ``(filing_year - YEAR(date_binding_cell))``.

    Mirrors the runtime ``age_at_year_end`` (Art. 57.1.b LIRPF ages the taxpayer
    at 31 December of the tax year, so ``filing_year - birth_year`` is exact): the
    single arg is a ``date_binding`` leaf (a date-valued profile fact such as
    birth_date) whose Entradas cell holds the operator-entered date. The filing
    year is the constant carried on the layout from the snapshot.
    """
    if len(expression.args) != 1:
        raise TranslationError(op="age_at_year_end")
    arg = expression.args[0]
    if arg.date_binding is None:
        raise TranslationError(op="age_at_year_end")
    if layout.filing_year <= 0:
        raise TranslationError(
            op="age_at_year_end",
            hint="plan_layout must be called with a bracket_filter_date so the filing year is known",
        )
    try:
        cell = layout.address_for_date_binding(arg.date_binding)
    except CalcSheetsEngineError as exc:
        raise TranslationError(
            op="age_at_year_end",
            hint="the layout planner must reserve an Entradas cell for every referenced date_binding",
        ) from exc
    return f"({layout.filing_year}-YEAR({cell.qualified()}))"


def _casilla_cell_reference(casilla_id: CasillaId, *, layout: SheetLayout) -> SheetA1Reference:
    """Return the Sheets A1 cell reference for a canonical ``casilla.id``."""
    try:
        address = layout.address_for(casilla_id)
    except CalcSheetsEngineError as exc:
        raise TranslationError(
            hint="the layout planner must reserve a cell for every referenced casilla",
        ) from exc
    return address.qualified()


def _binding_reference(binding: BindingId, *, layout: SheetLayout) -> str:
    try:
        address = layout.address_for_binding(binding)
    except CalcSheetsEngineError as exc:
        raise TranslationError(
            hint="the layout planner must reserve a cell for every referenced binding",
        ) from exc
    return address.qualified()


def _relation_reference(relation: RelationId, *, layout: SheetLayout) -> str:
    try:
        address = layout.address_for_relation(relation)
    except CalcSheetsEngineError as exc:
        raise TranslationError(
            hint="the layout planner must mirror every referenced relation into Tarifas",
        ) from exc
    return address.qualified()


def _parameter_reference(parameter: ParameterId, *, layout: SheetLayout) -> str:
    cell = layout.parameter_cells.get(parameter)
    if cell is None:
        raise TranslationError(
            hint="the layout planner must mirror every referenced parameter into Tarifas",
        )
    return cell.anchor.qualified()


def _expect_arg_count(op: str, args: list[str], expected: int) -> None:
    if len(args) != expected:
        raise TranslationError(
            op=op,
        )


__all__ = ["TranslationError", "translate_formula"]
