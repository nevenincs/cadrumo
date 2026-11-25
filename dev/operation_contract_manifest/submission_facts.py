"""Index and resolve source names, methods, and submission facts."""

from __future__ import annotations

import ast
from collections.abc import Iterator

from .submission_index import SubmissionIndexFlow
from .submission_source import (
    OPAQUE,
    Call,
    Facts,
    Resolution,
    Scope,
    Submission,
    Symbol,
    nodes_outside_annotations,
)


class SubmissionFactsFlow(SubmissionIndexFlow):
    """Collect submission facts from source scopes."""

    def _facts_of(self, symbol: Symbol) -> Facts:
        facts = self._facts.get(symbol)
        if facts is None:
            facts = self._read_facts(symbol)
            self._facts[symbol] = facts
        return facts

    def _facts_for_node(self, scope: Scope, node: ast.AST, called: dict[int, ast.Call]) -> Facts:
        if isinstance(node, ast.Call) and self._is_submission(scope, node.func):
            return Facts(roots=(self._root(scope, node),))
        if not isinstance(node, ast.Name | ast.Attribute):
            return Facts()
        resolution = self._resolve(scope, node)
        call = called.get(id(node))
        untyped = (
            ((node.attr, node.lineno),)
            if call is not None and not resolution.traced and isinstance(node, ast.Attribute)
            else ()
        )
        calls, references = self._resolved_facts(resolution, call)
        return Facts(calls=calls, references=references, untyped_calls=untyped)

    def _resolved_facts(
        self, resolution: Resolution, call: ast.Call | None
    ) -> tuple[tuple[Call, ...], frozenset[Symbol]]:
        calls: list[Call] = []
        references: set[Symbol] = set()
        for target in resolution.targets:
            if not self.defines(target):
                continue
            if call is not None and target[1] in self._index(target[0]).functions:
                calls.append(Call(callee=target, node=call, bound=resolution.bound))
            else:
                references.add(target)
        return tuple(calls), frozenset(references)

    def _read_facts(self, symbol: Symbol) -> Facts:
        path, name = symbol
        index = self._index(path)
        if name in index.classes:
            return Facts(references=self._class_references(symbol))
        scope = self._scope(symbol)
        body: ast.AST | None = scope.function if scope.function is not None else index.bindings.get(name)
        if body is None:
            return Facts()
        roots: list[Submission] = []
        calls: list[Call] = []
        references: set[Symbol] = set()
        untyped: list[tuple[str, int]] = []
        nodes = nodes_outside_annotations(body)
        called = {id(node.func): node for node in nodes if isinstance(node, ast.Call)}
        for node in nodes:
            part = self._facts_for_node(scope, node, called)
            roots.extend(part.roots)
            calls.extend(part.calls)
            references.update(part.references)
            untyped.extend(part.untyped_calls)
        return Facts(
            roots=tuple(roots), calls=tuple(calls), references=frozenset(references), untyped_calls=tuple(untyped)
        )

    def _class_references(self, symbol: Symbol) -> frozenset[Symbol]:
        """A class constructed or entered runs its special methods, and those of its bases."""
        path, name = symbol
        index = self._index(path)
        references: set[Symbol] = {
            (path, qualified)
            for qualified in index.functions
            if qualified.startswith(f"{name}.__") and qualified.endswith("__")
        }
        references.update(self._bases(symbol))
        return frozenset(references)

    def _bases(self, symbol: Symbol) -> Iterator[Symbol]:
        definition = self._index(symbol[0]).classes.get(symbol[1])
        if definition is None:
            return
        for base in definition.bases:
            if isinstance(base, ast.Name):
                origin = self._origin(symbol[0], base.id)
                if origin is not None:
                    yield origin

    def _is_submission(self, scope: Scope, callee: ast.expr) -> bool:
        return self._submission in self._resolve(scope, callee).targets

    def _root(self, scope: Scope, call: ast.Call) -> Submission:
        keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}
        identity = keywords.get(self._identity_argument)
        payload = keywords.get(self._payload_argument)
        return Submission(
            site=f"{scope.path}:{call.lineno}",
            identity=OPAQUE if identity is None else self._identity(scope, identity),
            payload=OPAQUE if payload is None else self._payload(scope, payload),
        )
