"""Compile missing-input checks with the registry's lazy conditional semantics."""

import re
from collections.abc import Mapping

from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ._translator import translate_formula
from .errors import CalcSheetsEngineError
from .layout import SheetLayout


def conditional_missing_input_guard(
    expression: FormulaExpression, *, formulas: Mapping[CasillaId, FormulaExpression], layout: SheetLayout
) -> str | None:
    """Return a dynamic condition only when a transitive dependency branches.

    Nonconditional plans retain their existing conservative input guards.
    A missing predicate is checked before evaluating it; only the chosen
    branch's dependencies can make a populated predicate's result unknown.
    """
    compiler = _ConditionalGuardCompiler(formulas, layout)
    return compiler.compile(expression)


class _ConditionalGuardCompiler:
    def __init__(self, formulas: Mapping[CasillaId, FormulaExpression], layout: SheetLayout) -> None:
        self._formulas = formulas
        self._layout = layout
        self._computed = {address.qualified(): key for key, address in layout.calculos_cells.items()}
        self._checked: set[str] = set()

    def compile(self, expression: FormulaExpression) -> str | None:
        self._validate_dependencies(expression, frozenset())
        if not self._branches(expression, frozenset()):
            return None
        condition, has_conditional = self._visit(expression, frozenset())
        return condition if has_conditional else None

    def _validate_dependencies(self, node: FormulaExpression, visiting: frozenset[str]) -> None:
        key = node.casilla_id
        if key is not None and key in self._formulas:
            if key in visiting:
                raise CalcSheetsEngineError("conditional formula dependency cycle")
            if key not in self._checked:
                self._validate_dependencies(self._formulas[key], visiting | {key})
                self._checked.add(key)
        for arg in node.args:
            self._validate_dependencies(arg, visiting)

    def _branches(self, node: FormulaExpression, visited: frozenset[str]) -> bool:
        if node.op in ("if_then_else", "require_condition", "record_row_unused", "text_equal"):
            return True
        if node.casilla_id is not None and node.casilla_id in self._formulas:
            if node.casilla_id in visited:
                raise CalcSheetsEngineError("conditional formula dependency cycle")
            return self._branches(self._formulas[node.casilla_id], visited | {node.casilla_id})
        return any(self._branches(arg, visited) for arg in node.args)

    def _combine(self, parts: list[tuple[str, bool]]) -> tuple[str, bool]:
        conditions = tuple(dict.fromkeys(value for value, _ in parts if value != "FALSE"))
        condition = (
            "FALSE" if not conditions else conditions[0] if len(conditions) == 1 else f"OR({','.join(conditions)})"
        )
        return condition, any(branches for _, branches in parts)

    def _references(self, body: str, visited: frozenset[str]) -> tuple[str, bool]:
        parts: list[tuple[str, bool]] = []
        for reference in re.findall(r"'[^']+'!\$?[A-Z]+\$?[0-9]+", body):
            key = self._computed.get(reference.replace("$", ""))
            if key is not None and key in self._formulas:
                if key in visited:
                    raise CalcSheetsEngineError("conditional formula dependency cycle")
                # Form projection guards every calculated support cell before
                # consumers read it. Test that result, rather than duplicating
                # its complete dependency tree in every downstream formula.
                # ISNUMBER is false for both errors and the unknown-value text.
                parts.append((f"NOT(ISNUMBER({reference}))", self._branches(self._formulas[key], visited | {key})))
            else:
                parts.append((f"ISBLANK({reference})", False))
        return self._combine(parts)

    def _visit(self, node: FormulaExpression, visited: frozenset[str]) -> tuple[str, bool]:
        if node.op in ("record_row_unused", "text_equal"):
            return f"ISERROR({translate_formula(node, layout=self._layout)})", True
        if node.op == "require_condition":
            predicate, value = node.args
            missing, _ = self._visit(predicate, visited)
            value_missing, _ = self._visit(value, visited)
            translated = translate_formula(predicate, layout=self._layout)
            condition = (
                f"IF(ISERROR({translated}),TRUE,"
                f"IF(OR(ISNUMBER({translated}),ISLOGICAL({translated})),"
                f"IF(({translated})<>0,{value_missing},TRUE),TRUE))"
            )
            return (condition if missing == "FALSE" else f"IF({missing},TRUE,{condition})"), True
        if node.op == "if_then_else":
            predicate, yes, no = node.args
            missing, _ = self._visit(predicate, visited)
            yes_missing, _ = self._visit(yes, visited)
            no_missing, _ = self._visit(no, visited)
            condition = f"IF(({translate_formula(predicate, layout=self._layout)})<>0,{yes_missing},{no_missing})"
            return (condition if missing == "FALSE" else f"IF({missing},TRUE,{condition})"), True
        if node.op in (
            "lookup_bracket",
            "lookup_bracket_by_ccaa",
            "lookup_bracket_by_entity_type",
            "lookup_parameter_by_entity_type",
            "age_at_year_end",
        ):
            return self._references(translate_formula(node, layout=self._layout), visited)
        if node.op is not None:
            return self._combine([self._visit(arg, visited) for arg in node.args])
        if node.date_binding is not None:
            return self._references(self._layout.address_for_date_binding(node.date_binding).qualified(), visited)
        return self._references(translate_formula(node, layout=self._layout), visited)
