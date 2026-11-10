"""The year gate's Python reader: every year a module's syntax tree writes as a bound or a coordinate.

The rules it applies, and what they admit, are stated by the gate in
``dev.quality.year_literals``. The reader walks the tree once; before it reads
a node's children it records which strings there are prose, amounts, compared
or parsed text, or casilla ids, so that a string is judged where it stands.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from typing import override

from .year_literal_casilla_ids import (
    casilla_named,
    casilla_operand,
    keyword_casilla_texts,
    parsed_casilla_texts,
    shaped_texts,
    typed_casilla_texts,
)
from .year_literal_python_rules import (
    AMOUNT_CALLS,
    DATE_CALLS,
    any_year,
    bound_detail,
    dated_from_year,
    keyword_bounds,
    node_name,
    opaque_texts,
    parsed_year_texts,
    template_rule,
    text_finding,
    written_bound,
    year_argument,
    year_compared,
    year_named,
    year_value,
)
from .year_literal_shapes import EDITION_IN_TEXT, Finding


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.found: list[tuple[int, str, str]] = []
        self._lines = source.splitlines()
        self._prose: set[int] = set()
        self._amounts: set[int] = set()
        self._compared: set[int] = set()
        self._parsed: set[int] = set()
        self._casilla_ids: set[int] = set()

    def _report(self, node: ast.AST, rule: str, detail: object) -> None:
        self.found.append((getattr(node, "lineno", 0), rule, str(detail)))

    def _mark_docstring(self, body: list[ast.stmt]) -> None:
        first = body[0] if body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            self._prose.add(id(first.value))

    @override
    def visit_Module(self, node: ast.Module) -> None:
        self._mark_docstring(node.body)
        self.generic_visit(node)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._mark_docstring(node.body)
        self.generic_visit(node)

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._mark_docstring(node.body)
        arguments = node.args
        positional = [*arguments.posonlyargs, *arguments.args]
        defaulted: list[tuple[ast.arg, ast.expr | None]] = [
            *zip(positional[len(positional) - len(arguments.defaults) :], arguments.defaults, strict=True),
            *zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True),
        ]
        for argument, default in defaulted:
            if casilla_named(argument.arg):
                self._casilla_ids.update(shaped_texts(default))
            self._casilla_ids.update(typed_casilla_texts(argument.annotation, default))
            year = written_bound(default, argument.arg, self._lines)
            if year is not None and default is not None:
                self._report(default, "year bound", f"{argument.arg}={year}")
        self.generic_visit(node)

    @override
    def visit_Compare(self, node: ast.Compare) -> None:
        sides = (node.left, *node.comparators)
        if year_compared(sides, self._lines):
            self._report(node, "year compared", ast.unparse(node)[:80])
        for side in sides:
            self._compared.update(opaque_texts(side))
            if casilla_operand(side):
                self._casilla_ids.update(text for other in sides if other is not side for text in shaped_texts(other))
        self.generic_visit(node)

    @override
    def visit_MatchValue(self, node: ast.MatchValue) -> None:
        self._compared.update(opaque_texts(node.value))
        self.generic_visit(node)

    def _bound(
        self, targets: Iterable[ast.AST], value: ast.AST | None, node: ast.AST, annotation: ast.AST | None = None
    ) -> None:
        self._casilla_ids.update(typed_casilla_texts(annotation, value))
        for target in targets:
            name = node_name(target)
            if casilla_named(name) and not isinstance(target, ast.Subscript):
                self._casilla_ids.update(shaped_texts(value))
            detail = bound_detail(name, value, annotation, self._lines)
            if detail is not None:
                self._report(node, "year bound", detail)
                return

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        self._bound(node.targets, node.value, node)
        self.generic_visit(node)

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._bound((node.target,), node.value, node, node.annotation)
        self.generic_visit(node)

    @override
    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._bound((node.target,), node.value, node)
        self.generic_visit(node)

    @override
    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                continue
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and casilla_named(key.value):
                self._casilla_ids.update(shaped_texts(value))
            year = written_bound(value, node_name(key), self._lines)
            if year is not None:
                self._report(value, "year bound", f"{node_name(key)}={year}")
        if sum(1 for key in node.keys if year_value(key, self._lines) is not None) >= 2:
            self._report(node, "year list", "dictionary keyed by years")
        self.generic_visit(node)

    @override
    def visit_Subscript(self, node: ast.Subscript) -> None:
        if casilla_named(node_name(node.value)) and isinstance(node.slice, ast.Constant):
            self._casilla_ids.update(shaped_texts(node.slice))
        self.generic_visit(node)

    @override
    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, (ast.Add, ast.Sub)):
            for year, other in ((node.left, node.right), (node.right, node.left)):
                if year_value(year, self._lines) is not None and year_named(other):
                    self._report(node, "year arithmetic", ast.unparse(node)[:80])
                    break
        self.generic_visit(node)

    def _sequence(self, node: ast.Tuple | ast.List | ast.Set) -> None:
        if sum(1 for element in node.elts if year_value(element, self._lines) is not None) >= 2:
            self._report(node, "year list", ast.unparse(node)[:80])
        self.generic_visit(node)

    @override
    def visit_Tuple(self, node: ast.Tuple) -> None:
        self._sequence(node)

    @override
    def visit_List(self, node: ast.List) -> None:
        self._sequence(node)

    @override
    def visit_Set(self, node: ast.Set) -> None:
        self._sequence(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        called = node_name(node.func)
        self._casilla_ids.update(parsed_casilla_texts(called, node))
        self._casilla_ids.update(keyword_casilla_texts(node))
        if called in AMOUNT_CALLS:
            # An amount written as text, such as a Decimal of two thousand, is money, not a year.
            self._amounts.update(id(argument) for argument in node.args)
        if called == "range" and any_year(node.args, self._lines):
            self._report(node, "year list", ast.unparse(node)[:80])
        elif self._builds_dated(called, node):
            self._report(node, "year date", ast.unparse(node)[:80])
        else:
            for value, detail in keyword_bounds(node, self._lines):
                self._report(value, "year bound", detail)
            if year_argument(called, node, self._lines):
                self._report(node, "year argument", ast.unparse(node)[:80])
        self.generic_visit(node)

    def _builds_dated(self, called: str, node: ast.Call) -> bool:
        """Whether a call builds a date or datetime from a written year, marking text it parses."""
        if called in DATE_CALLS:
            return dated_from_year(node, self._lines)
        written = parsed_year_texts(called, node)
        self._parsed.update(id(argument) for argument in written)
        return bool(written)

    @override
    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self._prose or id(node) in self._amounts or not isinstance(node.value, str):
            return
        if id(node) in self._parsed:
            return
        finding = text_finding(
            node.value, compared=id(node) in self._compared, casilla_id=id(node) in self._casilla_ids
        )
        if finding is not None:
            self._report(node, *finding)

    @override
    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        literal = "".join(str(part.value) for part in node.values if isinstance(part, ast.Constant))
        judged = id(node) in self._compared or id(node) in self._parsed
        rule = None if judged else template_rule(node)
        if rule is not None:
            self._report(node, rule, repr(literal[:80]))
        elif EDITION_IN_TEXT.search(literal):
            self._report(node, "edition id", repr(literal[:80]))
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                self.visit(part)


def python_findings(source: str, path: str) -> list[Finding]:
    """Every year written into one Python source text."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [Finding(path=path, line=error.lineno or 0, rule="unreadable", text=str(error.msg))]
    visitor = _PythonVisitor(source)
    visitor.visit(tree)
    unique = dict.fromkeys(visitor.found)
    return sorted(Finding(path=path, line=line, rule=rule, text=text) for line, rule, text in unique)
