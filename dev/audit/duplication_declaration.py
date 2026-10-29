"""Prove clone spans contain only inert declarations."""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

from dev._paths import UTF_8

from .duplication_declaration_rules import (
    declaration_docstring,
    declaration_has_call,
    declaration_imported_names,
    inert_declaration,
)

_UTF_8 = UTF_8


def source_span(source: str, node: ast.stmt) -> tuple[tuple[int, int], tuple[int, int]]:
    """Translate AST UTF-8 byte columns into tokenizer character columns."""
    rows = source.splitlines()

    def position(line: int, column: int) -> tuple[int, int]:
        return line, len(rows[line - 1].encode(_UTF_8)[:column].decode(_UTF_8))

    if node.end_lineno is None or node.end_col_offset is None:
        raise ValueError("Parsed statement has no source extent")
    return position(node.lineno, node.col_offset), position(node.end_lineno, node.end_col_offset)


def site_span(site: tuple[str, int, int, int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Convert clone coordinates to source span coordinates."""
    _, start, start_column, end, end_column = site
    return (start, start_column - 1), (end, end_column)


def intersects(left: tuple[tuple[int, int], tuple[int, int]], right: tuple[tuple[int, int], tuple[int, int]]) -> bool:
    """Return whether two source intervals overlap."""
    return left[0] < right[1] and right[0] < left[1]


def span_is_declaration(repo_root: Path, site: tuple[str, int, int, int, int]) -> bool:
    """Prove every cloned token is inert, retaining unknown and executable spans."""
    path = site[0]
    try:
        source = (repo_root / path).read_text(encoding=_UTF_8)
        tree = ast.parse(source, filename=path)
    except (OSError, UnicodeError, SyntaxError):
        return False
    proof = _DeclarationIntervals(source, tree)
    proof.visit(tree.body)
    declared, executable = proof.declared, proof.executable
    span = site_span(site)
    relevant = _declaration_tokens(source, span)
    if relevant is None:
        return False
    return bool(relevant) and all(
        any(interval[0] <= token[0] and token[1] <= interval[1] for interval in declared)
        and not any(intersects(token, interval) for interval in executable)
        for token in relevant
    )


def _declaration_tokens(
    source: str, span: tuple[tuple[int, int], tuple[int, int]]
) -> list[tuple[tuple[int, int], tuple[int, int]]] | None:
    try:
        relevant = [
            (token.start, token.end)
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type
            not in {
                tokenize.ENCODING,
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENDMARKER,
            }
            and intersects((token.start, token.end), span)
        ]
    except (tokenize.TokenError, IndentationError):
        return None
    return relevant


class _DeclarationIntervals:
    def __init__(self, source: str, tree: ast.Module) -> None:
        self.source = source
        self.declared: list[tuple[tuple[int, int], tuple[int, int]]] = []
        self.executable: list[tuple[tuple[int, int], tuple[int, int]]] = []
        self.type_checking = declaration_imported_names(tree, "typing", "TYPE_CHECKING")
        self.fields = declaration_imported_names(tree, "pydantic", "Field")
        self.protocols = declaration_imported_names(tree, "typing", "Protocol") | declaration_imported_names(
            tree, "typing_extensions", "Protocol"
        )

    def visit(self, body: list[ast.stmt], *, in_class: bool = False, protocol: bool = False) -> None:
        for index, node in enumerate(body):
            span = source_span(self.source, node)
            if isinstance(node, ast.Import | ast.ImportFrom) or (index == 0 and declaration_docstring(node)):
                self.declared.append(span)
            elif isinstance(node, ast.If) and _type_checking_if(node, self.type_checking):
                self.declared.append((span[0], source_span(self.source, node.body[-1])[1]))
                self.visit(node.orelse, in_class=in_class, protocol=protocol)
            elif isinstance(node, ast.ClassDef):
                self._class(node, span)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                self._function(node, span, protocol)
            elif isinstance(node, ast.AnnAssign | ast.Assign):
                self._assignment(node, span, in_class)
            else:
                self.executable.append(span)

    def _class(self, node: ast.ClassDef, span: tuple[tuple[int, int], tuple[int, int]]) -> None:
        header = (span[0], source_span(self.source, node.body[0])[0])
        self.declared.append(header)
        if declaration_has_call(node.bases + node.decorator_list + [keyword.value for keyword in node.keywords]):
            self.executable.append(header)
        is_protocol = any(isinstance(base, ast.Name) and base.id in self.protocols for base in node.bases)
        self.visit(node.body, in_class=True, protocol=is_protocol)

    def _function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        span: tuple[tuple[int, int], tuple[int, int]],
        protocol: bool,
    ) -> None:
        header = (span[0], source_span(self.source, node.body[0])[0])
        self.declared.append(header)
        if _function_header_has_call(node):
            self.executable.append(header)
        arguments = _function_argument_names(node)
        for number, stmt in enumerate(node.body):
            stub = protocol and _protocol_stub(stmt, arguments)
            (self.declared if stub or (number == 0 and declaration_docstring(stmt)) else self.executable).append(
                source_span(self.source, stmt)
            )

    def _assignment(
        self, node: ast.AnnAssign | ast.Assign, span: tuple[tuple[int, int], tuple[int, int]], in_class: bool
    ) -> None:
        value = node.value
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        safe = all(isinstance(target, ast.Name) for target in targets) and inert_declaration(value)
        if in_class and isinstance(node, ast.AnnAssign) and isinstance(value, ast.Call):
            safe = _safe_field_call(value, self.fields)
        if isinstance(node, ast.AnnAssign) and declaration_has_call([node.annotation]):
            safe = False
        (self.declared if safe else self.executable).append(span)


def _safe_field_call(value: ast.Call, fields: set[str]) -> bool:
    return (
        isinstance(value.func, ast.Name)
        and value.func.id in fields
        and not value.args
        and all(item.arg not in {None, "default_factory"} and inert_declaration(item.value) for item in value.keywords)
    )


def _function_header_has_call(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    defaults = node.args.defaults + [value for value in node.args.kw_defaults if value is not None]
    annotations = [
        arg.annotation
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if arg.annotation is not None
    ]
    for variadic in (node.args.vararg, node.args.kwarg):
        if variadic is not None and variadic.annotation is not None:
            annotations.append(variadic.annotation)
    if node.returns is not None:
        annotations.append(node.returns)
    return declaration_has_call(defaults + node.decorator_list + annotations)


def _function_argument_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = {arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
    if node.args.vararg is not None:
        arguments.add(node.args.vararg.arg)
    if node.args.kwarg is not None:
        arguments.add(node.args.kwarg.arg)
    return arguments


def _protocol_stub(stmt: ast.stmt, arguments: set[str]) -> bool:
    return (
        isinstance(stmt, ast.Pass)
        or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis)
        or (
            isinstance(stmt, ast.Delete)
            and all(isinstance(target, ast.Name) and target.id in arguments for target in stmt.targets)
        )
    )


def _type_checking_if(node: ast.If, names: set[str]) -> bool:
    return isinstance(node.test, ast.Name) and node.test.id in names
