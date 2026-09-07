"""Detect disjunction operands satisfied by tokens the test itself supplied.

The closed shape is an ``or`` assertion over captured output where one string
membership operand is either an exact CLI argument or a ``key=<argument>``
rendering. Such an operand can be satisfied by an error echo or pass-through
of the test's own input, so it cannot serve as the fallback proof of the
sibling claim.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import override

__all__ = [
    "SelfEchoingToken",
    "scan_self_echoing_tokens",
]

_CLI_CALL_NAMES = frozenset({"_invoke", "invoke_cached_cli"})


@dataclass(frozen=True, slots=True)
class SelfEchoingToken:
    """One disjunct that accepts a token supplied by the asserting test."""

    path: Path
    lineno: int
    echoed_needle: str
    argv_token: str
    haystack: str

    @override
    def __str__(self) -> str:
        """Render an openable locator and the self-echo relation."""
        return (
            f"{self.path}:{self.lineno} {self.echoed_needle!r} accepts supplied "
            f"token {self.argv_token!r} in {self.haystack}"
        )


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _argv_tokens(call: ast.Call) -> frozenset[str]:
    """Return literal CLI arguments supplied by one supported invocation."""
    tokens: set[str] = set()
    if _call_name(call) in _CLI_CALL_NAMES and call.args and isinstance(call.args[0], (ast.List, ast.Tuple)):
        tokens.update(
            element.value
            for element in call.args[0].elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        )
    return frozenset(tokens)


def _same_scope_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[ast.AST]:
    """Yield nodes in one function without crossing a nested lexical scope."""

    def descend(node: ast.AST) -> Iterator[ast.AST]:
        yield node
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Lambda,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        ):
            return
        for child in ast.iter_child_nodes(node):
            yield from descend(child)

    for statement in function.body:
        yield from descend(statement)


def _bound_names(target: ast.expr) -> tuple[str, ...]:
    """Return every simple name bound by one assignment target."""
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(name for element in target.elts for name in _bound_names(element))
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return ()


def _writes(node: ast.AST) -> tuple[tuple[str, ast.expr | None], ...]:
    """Return same-scope name bindings, with a value only for one direct assignment."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return ((node.targets[0].id, node.value),)
    if isinstance(node, ast.Assign):
        return tuple((name, None) for target in node.targets for name in _bound_names(target))
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return ((node.target.id, node.value),)
    if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
        return ((node.target.id, None),)
    if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
        return ((node.target.id, node.value),)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return tuple((name, None) for name in _bound_names(node.target))
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return tuple(
            (name, None)
            for item in node.items
            if item.optional_vars is not None
            for name in _bound_names(item.optional_vars)
        )
    if isinstance(node, ast.ExceptHandler) and node.name is not None:
        return ((node.name, None),)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return ((node.name, None),)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return tuple((alias.asname or alias.name.split(".")[0], None) for alias in node.names)
    return ()


def _string_membership(node: ast.expr) -> tuple[str, ast.expr] | None:
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.In)
        and len(node.comparators) == 1
        and isinstance(node.left, ast.Constant)
        and isinstance(node.left.value, str)
    ):
        return None
    return node.left.value, node.comparators[0]


def _assigned_invocations(
    scope_nodes: tuple[ast.AST, ...],
) -> dict[str, tuple[tuple[int, frozenset[str] | None], ...]]:
    """Index assignments, retaining unsupported writes as binding barriers."""
    indexed: dict[str, list[tuple[int, frozenset[str] | None]]] = {}
    for position, node in enumerate(scope_nodes):
        for name, value in _writes(node):
            tokens = _argv_tokens(value) if isinstance(value, ast.Call) else frozenset()
            indexed.setdefault(name, []).append((position, tokens or None))
    return {name: tuple(sorted(entries)) for name, entries in indexed.items()}


def _result_name(haystack: ast.expr) -> str | None:
    """Return the invocation-result name for one direct captured-output reference."""
    if isinstance(haystack, ast.Attribute) and haystack.attr == "output" and isinstance(haystack.value, ast.Name):
        return haystack.value.id
    return None


def _echoed_token(needle: str, argv_tokens: frozenset[str]) -> str | None:
    folded_needle = needle.casefold()
    for token in sorted(argv_tokens, key=len, reverse=True):
        if len(token) < 4:
            continue
        folded_token = token.casefold()
        if folded_needle == folded_token or folded_needle.endswith(f"={folded_token}"):
            return token
    return None


def scan_self_echoing_tokens(path: Path, source: str) -> tuple[SelfEchoingToken, ...]:
    """Return self-echoing membership disjuncts in one test module."""
    tree = ast.parse(source, filename=str(path))
    findings: list[SelfEchoingToken] = []
    for function in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        scope_nodes = tuple(_same_scope_nodes(function))
        invocations = _assigned_invocations(scope_nodes)
        if not invocations:
            continue
        for position, node in enumerate(scope_nodes):
            if not (
                isinstance(node, ast.Assert) and isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or)
            ):
                continue
            for operand in node.test.values:
                membership = _string_membership(operand)
                if membership is None:
                    continue
                needle, haystack_node = membership
                result_name = _result_name(haystack_node)
                if result_name is None:
                    continue
                preceding = tuple(
                    tokens
                    for assignment_position, tokens in invocations.get(result_name, ())
                    if assignment_position < position
                )
                if not preceding:
                    continue
                argv_tokens = preceding[-1]
                if argv_tokens is None:
                    continue
                token = _echoed_token(needle, argv_tokens)
                if token is not None:
                    findings.append(
                        SelfEchoingToken(
                            path=path,
                            lineno=node.lineno,
                            echoed_needle=needle,
                            argv_token=token,
                            haystack=ast.unparse(haystack_node),
                        ),
                    )
    return tuple(findings)
