"""Structural detection of unvalidated string-to-:class:`~decimal.Decimal` parses.

The sibling :mod:`~tests._inventory` surface answers "which files do structural
ratchets scan"; this module answers the narrower question "does this
``Decimal(...)`` call parse *text*". A bare ``Decimal(text)`` silently admits
scientific notation, a leading ``+``, an underscore digit separator, and the
non-finite ``NaN``/``Infinity`` — and a ``NaN`` monetary value compares ``False``
to every threshold, so an under-declaration advisory keyed on ``> 0`` never fires
for it. Every such call must route through the canonical grammar
(:func:`~core.decimal.try_parse_canonical_decimal`) or the tolerant coercion
helper (:func:`~core.decimal.coerce_decimal`) instead.

Why the argument's *type* is the discriminator
----------------------------------------------

``Decimal(len(rows))`` and ``Decimal(self.runs)`` widen an integer: no grammar is
involved, the result cannot be non-finite, and nothing can be misread. Only a
*string* argument carries a grammar, so only a string argument can misparse.
This module therefore reports a violation exactly when the single argument is
provably string-typed by structure, which is decidable from the AST alone in a
fully-annotated tree:

* a ``str(...)`` call, an f-string, or a string literal concatenation;
* a call to a string-only method (``.strip()``, ``.replace()``, …) — the receiver
  need not be resolvable, because no non-string type in this tree exposes them;
* a name bound to a ``str`` / ``str | None`` / ``Annotated[str, ...]`` parameter
  or annotated assignment of an enclosing scope;
* a name assigned from any of the above (folded to a fixed point, so
  ``text = raw.strip()`` then ``Decimal(text)`` is still seen);
* a loop target over a ``Mapping[..., str]`` / ``Sequence[str]`` iterable.

Integer widening is consequently never reported, so the gate needs no allowlist
entry for the many legitimate ``Decimal(<int>)`` sites.

See Also:
    :func:`~core.decimal.try_parse_canonical_decimal`
        Strict grammar for operator-typed text.
    :func:`~core.decimal.coerce_decimal`
        Tolerant coercion for machine-produced text.
    :mod:`~tests._inventory`
        Shared production AST inventory surface.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from ._inventory import leaf_name

STRING_ONLY_METHODS: frozenset[str] = frozenset(
    {
        "strip",
        "lstrip",
        "rstrip",
        "replace",
        "lower",
        "upper",
        "casefold",
        "removeprefix",
        "removesuffix",
        "zfill",
        "title",
        "swapcase",
        "expandtabs",
    },
)
"""Methods no non-string type in this tree exposes, so their result is a ``str``."""

_ALIAS_FOLD_PASSES = 4
"""Fixed-point bound for ``a = raw.strip(); b = a`` rebinding chains."""

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
"""Scopes that bind parameter names. A lambda cannot annotate its parameters, so
it contributes nothing to the ``str``-name set, but including it keeps the
parameter walk total over every callable form."""


def annotation_is_str(node: ast.expr | None) -> bool:
    """Return True when *node* annotates a plain ``str`` (optionally wrapped)."""
    if node is None:
        return False
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # A stringised annotation (``"str | None"``) under future annotations.
        return node.value.strip().split("|")[0].strip() == "str"
    if isinstance(node, ast.Name):
        return node.id == "str"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return annotation_is_str(node.left) or annotation_is_str(node.right)
    if isinstance(node, ast.Subscript):
        base = leaf_name(node.value)
        if base == "Annotated":
            target = node.slice
            if isinstance(target, ast.Tuple) and target.elts:
                return annotation_is_str(target.elts[0])
            return annotation_is_str(target)
        if base == "Optional":
            return annotation_is_str(node.slice)
    return False


def annotation_element_is_str(node: ast.expr | None) -> bool:
    """Return True when *node* annotates a container whose element type is ``str``.

    ``Mapping[CasillaId, str]`` and ``Sequence[str]`` both qualify: iterating the
    former's ``.items()`` or the latter directly binds a ``str``.
    """
    if node is None:
        return False
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return annotation_element_is_str(node.left) or annotation_element_is_str(node.right)
    if not isinstance(node, ast.Subscript):
        return False
    target = node.slice
    elements = target.elts if isinstance(target, ast.Tuple) else [target]
    return bool(elements) and annotation_is_str(elements[-1])


def _expression_is_str(node: ast.expr, str_names: frozenset[str]) -> bool:
    """Return True when *node* provably evaluates to a ``str``."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Name):
        return node.id in str_names
    if isinstance(node, ast.Call):
        if leaf_name(node.func) == "str":
            return True
        return isinstance(node.func, ast.Attribute) and node.func.attr in STRING_ONLY_METHODS
    if isinstance(node, ast.Subscript):
        return _expression_is_str(node.value, str_names)
    if isinstance(node, ast.BoolOp):
        return any(_expression_is_str(value, str_names) for value in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _expression_is_str(node.left, str_names) or _expression_is_str(node.right, str_names)
    if isinstance(node, ast.IfExp):
        return _expression_is_str(node.body, str_names) or _expression_is_str(node.orelse, str_names)
    return False


def _annotated_str_parameters(node: _FunctionNode) -> set[str]:
    args = node.args
    parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg is not None:
        parameters.append(args.vararg)
    if args.kwarg is not None:
        parameters.append(args.kwarg)
    return {parameter.arg for parameter in parameters if annotation_is_str(parameter.annotation)}


def _loop_target_str_names(node: ast.For | ast.AsyncFor, str_containers: Mapping[str, bool]) -> set[str]:
    iterated = node.iter
    if isinstance(iterated, ast.Call) and isinstance(iterated.func, ast.Attribute):
        if iterated.func.attr not in {"items", "values"}:
            return set()
        iterated = iterated.func.value
    while isinstance(iterated, ast.BoolOp) and iterated.values:
        iterated = iterated.values[0]
    if not isinstance(iterated, ast.Name) or not str_containers.get(iterated.id, False):
        return set()
    target = node.target
    bound = target.elts if isinstance(target, ast.Tuple) else [target]
    return {bound[-1].id} if bound and isinstance(bound[-1], ast.Name) else set()


def _str_container_names(node: ast.AST | None) -> dict[str, bool]:
    """Return parameter names annotated as a container of ``str``.

    Annotated *assignments* of the same shape are folded in by
    :func:`_scope_str_names`, which walks the whole scope body rather than only
    its top-level statements.
    """
    containers: dict[str, bool] = {}
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        args = node.args
        for parameter in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            if annotation_element_is_str(parameter.annotation):
                containers[parameter.arg] = True
    return containers


def _scope_str_names(
    body: Sequence[ast.stmt],
    inherited: frozenset[str],
    node: ast.AST | None,
) -> frozenset[str]:
    """Return every provably-``str`` name visible in one scope."""
    names = set(inherited)
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        names |= _annotated_str_parameters(node)
    containers = _str_container_names(node)

    statements = [child for statement in body for child in ast.walk(statement)]
    for statement in statements:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if annotation_is_str(statement.annotation):
                names.add(statement.target.id)
            if annotation_element_is_str(statement.annotation):
                containers[statement.target.id] = True
        elif isinstance(statement, ast.For | ast.AsyncFor):
            names |= _loop_target_str_names(statement, containers)

    for _ in range(_ALIAS_FOLD_PASSES):
        grew = False
        for statement in statements:
            if isinstance(statement, ast.Assign):
                targets: list[ast.expr] = list(statement.targets)
                value: ast.expr = statement.value
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                targets = [statement.target]
                value = statement.value
            else:
                continue
            if not _expression_is_str(value, frozenset(names)):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    grew = True
        if not grew:
            break
    return frozenset(names)


def _is_single_argument_decimal_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call) and leaf_name(node.func) == "Decimal" and len(node.args) == 1 and not node.keywords
    )


def _visit_scope(
    body: Sequence[ast.stmt],
    inherited: frozenset[str],
    node: ast.AST | None,
    found: list[tuple[int, str]],
) -> None:
    """Record string-parsing ``Decimal`` calls in one scope, then recurse into nested ones."""
    str_names = _scope_str_names(body, inherited, node)
    nested: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def walk(current: ast.AST) -> None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            nested.append(current)
            return
        if _is_single_argument_decimal_call(current):
            assert isinstance(current, ast.Call)
            argument = current.args[0]
            if not isinstance(argument, ast.Constant) and _expression_is_str(argument, str_names):
                found.append((current.lineno, _enclosing_name(node)))
        for child in ast.iter_child_nodes(current):
            walk(child)

    for statement in body:
        walk(statement)
    for function in nested:
        _visit_scope(function.body, str_names, function, found)


def _enclosing_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return node.name
    return "<module>"


def string_parse_decimal_sites(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    """Return ``(lineno, enclosing function name)`` for each string-parsing ``Decimal`` call."""
    if not isinstance(tree, ast.Module):
        return ()
    found: list[tuple[int, str]] = []
    _visit_scope(tree.body, frozenset(), None, found)
    return tuple(sorted(set(found)))


def string_parse_decimal_violations(
    items: Iterable[tuple[Path, ast.AST]],
    *,
    display_root: Path,
    exempt: Mapping[tuple[str, str], str] = {},
) -> list[str]:
    """Return ``path:lineno (function)`` strings for non-exempt string-parsing sites.

    Args:
        items: ``(path, AST)`` pairs to scan.
        display_root: Root the reported paths are made relative to. Injecting a
            temporary root is how the gate's own anti-tautology proof scans a
            synthetic module without monkeypatching the production surface.
        exempt: ``(relative path, enclosing function name) -> reason`` entries.
            Keyed by function rather than line number so an unrelated edit in the
            same file does not silently move a site out of its exemption.
    """
    violations: list[str] = []
    for path, tree in items:
        relative = path.relative_to(display_root).as_posix()
        for lineno, function in string_parse_decimal_sites(tree):
            if (relative, function) in exempt:
                continue
            violations.append(f"{relative}:{lineno} (in {function})")
    return violations


__all__ = [
    "STRING_ONLY_METHODS",
    "annotation_element_is_str",
    "annotation_is_str",
    "string_parse_decimal_sites",
    "string_parse_decimal_violations",
]
