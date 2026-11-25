"""Index and resolve source names, methods, and submission facts."""

from __future__ import annotations

import ast
from abc import abstractmethod
from collections.abc import Mapping
from typing import override

from cadrumo.entrypoints.tests.source_tree_support import SourceTree, module_level_bindings

from .submission_source import (
    Facts,
    FlowValue,
    Function,
    ModuleIndex,
    Scope,
    Symbol,
    function_scope,
)
from .submission_values import SubmissionValueFlow


class SubmissionIndexFlow(SubmissionValueFlow):
    """Index source declarations and scopes for a flow reading."""

    @abstractmethod
    def defines(self, symbol: Symbol) -> bool:
        """Check whether the source symbol can be read."""

    def __init__(
        self,
        tree: SourceTree,
        *,
        scanned: tuple[str, ...],
        submission: Symbol,
        identity_argument: str = "definition_id",
        payload_argument: str = "payload_json",
        callable_members: Mapping[tuple[Symbol, str], Symbol] | None = None,
    ) -> None:
        """Bind the reading to its source tree and to the record every submission constructs.

        Args:
            tree: The source tree to read.
            scanned: Path prefixes of the packages whose functions are walked.
                A function elsewhere is never entered; a constant or a class
                elsewhere is still read when a walked function names it.
            submission: The class whose construction is a submission.
            identity_argument: The keyword that names the operation.
            payload_argument: The keyword that carries the encoded payload.
            callable_members: Source-bound callable fields supplied by the owning host.
        """
        self._tree = tree
        self._callable_members = dict(callable_members or {})
        self._scanned = scanned
        self._submission = submission
        self._identity_argument = identity_argument
        self._payload_argument = payload_argument
        self._indexes: dict[str, ModuleIndex] = {}
        self._scopes: dict[Symbol, Scope] = {}
        self._facts: dict[Symbol, Facts] = {}
        self._receiver_classes: dict[tuple[Symbol, str], frozenset[Symbol]] = {}
        self._member_classes: dict[tuple[Symbol, str], frozenset[Symbol]] = {}
        self._required_classes: dict[Symbol, Mapping[str, Symbol]] = {}
        self._identities: dict[tuple[Symbol, int], FlowValue] = {}
        self._payloads: dict[tuple[Symbol, int], FlowValue] = {}

    def _is_scanned(self, path: str) -> bool:
        return path.startswith(self._scanned)

    @override
    def _index(self, path: str) -> ModuleIndex:
        index = self._indexes.get(path)
        if index is None:
            module = self._tree.parsed(path)
            functions: dict[str, Function] = {}
            classes: dict[str, ast.ClassDef] = {}
            for node in module.body:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    functions[node.name] = node
                elif isinstance(node, ast.ClassDef):
                    classes[node.name] = node
                    for member in node.body:
                        if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                            functions[f"{node.name}.{member.name}"] = member
            index = ModuleIndex(functions=functions, classes=classes, bindings=dict(module_level_bindings(module)))
            self._indexes[path] = index
        return index

    @override
    def _origin(self, path: str, name: str) -> Symbol | None:
        """Resolve a name used in a file to the module-level symbol that defines it.

        A scanned file is checked to define the name, and an import it merely
        passes along is followed. A file outside the scanned packages is taken
        at its word, so naming one of its symbols never costs a parse; whoever
        needs to know what kind of symbol it is reads the file then.
        """
        origin = self._tree.name_origins(path).get(name)
        seen: set[Symbol] = set()
        while origin is not None and origin not in seen:
            seen.add(origin)
            if not self._is_scanned(origin[0]) or self._index(origin[0]).defines(origin[1]):
                return origin
            origin = self._tree.name_origins(origin[0]).get(origin[1])
        return None

    @override
    def _class_named(self, scope: Scope, name: str) -> Symbol | None:
        """Resolve a name to a class of the tree, unless the scope binds the name itself."""
        if scope.binds(name):
            return None
        origin = self._origin(scope.path, name)
        if origin is None or origin[1] not in self._index(origin[0]).classes:
            return None
        return origin

    @override
    def _module_scope(self, path: str) -> Scope:
        return Scope(symbol=(path, ""), owner=None, function=None)

    def _scope(self, symbol: Symbol) -> Scope:
        scope = self._scopes.get(symbol)
        if scope is None:
            path, name = symbol
            function = self._index(path).functions.get(name)
            owner = (path, name.rpartition(".")[0]) if "." in name else None
            scope = (
                Scope(symbol=symbol, owner=owner, function=None)
                if function is None
                else function_scope(symbol, owner, function)
            )
            self._scopes[symbol] = scope
        return scope

    # -- what a symbol's own source says ----------------------------------
