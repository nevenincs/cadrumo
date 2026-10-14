"""Neutral AST detection of paths constructed from the configured storage root."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from typing import Final, NamedTuple

from ..core.storage_taxonomy import STORAGE_ROOT_SETTINGS_FIELD

_MODULE_SCOPE: Final[str] = "<module>"

JOIN_METHODS: Final[frozenset[str]] = frozenset({"joinpath", "glob", "rglob", "iterdir"})


class JoinSite(NamedTuple):
    """One place the storage root is joined onto, and who owns it."""

    module: str
    function: str
    lineno: int

    @property
    def key(self) -> tuple[str, str]:
        """The declaration key: module and enclosing function."""
        return (self.module, self.function)


def _unwrap_path_call(node: ast.expr) -> ast.expr:
    """Strip ``Path(...)`` wrappers so ``Path(root) / x`` reads like ``root / x``."""
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path" and node.args:
        node = node.args[0]
    return node


def _is_root_access(node: ast.expr) -> bool:
    """Whether ``node`` loads the storage-root attribute off anything."""
    unwrapped = _unwrap_path_call(node)
    return isinstance(unwrapped, ast.Attribute) and unwrapped.attr == STORAGE_ROOT_SETTINGS_FIELD


def _join_linenos(tree: ast.AST) -> set[int]:
    """Return the lines on which the storage root has something joined onto it."""
    found: set[int] = set()
    for node in ast.walk(tree):
        target: ast.expr | None = None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            target = node.left
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in JOIN_METHODS:
            target = node.func.value
        if target is not None and _is_root_access(target):
            found.add(_unwrap_path_call(target).lineno)
    return found


def _function_spans(tree: ast.AST) -> list[tuple[int, int, str]]:
    """Return ``(start, end, dotted name)`` for every function, nested ones included."""
    spans: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                name = f"{prefix}{child.name}"
                if not isinstance(child, ast.ClassDef):
                    spans.append((child.lineno, child.end_lineno or child.lineno, name))
                walk(child, f"{name}.")
            else:
                walk(child, prefix)

    walk(tree, "")
    return spans


def _enclosing_scope(lineno: int, spans: list[tuple[int, int, str]]) -> str:
    """Return the innermost function containing ``lineno``, or the module scope."""
    enclosing = [(start, name) for start, end, name in spans if start <= lineno <= end]
    return max(enclosing)[1] if enclosing else _MODULE_SCOPE


def _root_bound_names(tree: ast.AST, spans: list[tuple[int, int, str]]) -> dict[str, list[tuple[str, int]]]:
    """Return, per scope, the local names assigned the storage root and where.

    A one-line rebind is the obvious way around a receiver-only walk::

        root = settings.cadrumo_local_storage_root   # a plain read
        target = root / "buckets" / bucket_id        # a join the walk cannot see

    Both statements are individually unremarkable and together they produce a
    location, so the binding has to be followed or the gate passes a join it
    never saw.

    Scope is deliberately the whole of a function (plus the scopes enclosing
    it, since a closure genuinely sees its host's names) and no further.
    Chasing the root through parameters and return values is where a heuristic
    starts flagging healthy code, and a gate that flags healthy code gets
    weakened or deleted.
    """
    bound: dict[str, list[tuple[str, int]]] = {}
    for node in ast.walk(tree):
        targets: Sequence[ast.expr]
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = (node.target,)
        else:
            continue
        if node.value is None or not _is_root_access(node.value):
            continue
        scope = _enclosing_scope(node.lineno, spans)
        for target in targets:
            if isinstance(target, ast.Name):
                bound.setdefault(scope, []).append((target.id, node.lineno))
    return bound


def _binds_root(
    name: str,
    scope: str,
    lineno: int,
    bound: dict[str, list[tuple[str, int]]],
) -> bool:
    """Whether ``name`` holds the storage root at ``lineno`` within ``scope``.

    Visible scopes are the scope itself and every scope enclosing it, so a
    closure joining a name its host bound is caught. Only bindings *above* the
    use count, which keeps an unrelated same-named local in an earlier sibling
    function from reaching across.
    """
    parts = scope.split(".")
    visible = [".".join(parts[:depth]) for depth in range(1, len(parts) + 1)] + [_MODULE_SCOPE]
    return any(
        bound_name == name and bound_lineno < lineno
        for candidate in visible
        for bound_name, bound_lineno in bound.get(candidate, ())
    )


def root_join_sites(module: str, tree: ast.AST) -> tuple[JoinSite, ...]:
    """Return every place ``module`` joins onto the storage root.

    A pure function over a display name and a parsed tree, so the
    discrimination tests can hand it synthetic source and prove each shape
    fires or does not. The innermost enclosing function wins, so a join inside
    a closure is attributed to the closure rather than to its host.
    """
    spans = _function_spans(tree)
    bound = _root_bound_names(tree, spans)
    linenos: set[int] = set(_join_linenos(tree))

    for node in ast.walk(tree):
        target: ast.expr | None = None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            target = node.left
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in JOIN_METHODS:
            target = node.func.value
        if target is None:
            continue
        receiver = _unwrap_path_call(target)
        if isinstance(receiver, ast.Name) and _binds_root(
            receiver.id, _enclosing_scope(receiver.lineno, spans), receiver.lineno, bound
        ):
            linenos.add(receiver.lineno)

    return tuple(
        JoinSite(module=module, function=_enclosing_scope(lineno, spans), lineno=lineno) for lineno in sorted(linenos)
    )
