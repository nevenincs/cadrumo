"""Discover dynamic translation namespaces from literal prefixes."""

from __future__ import annotations

import ast

from ._ast_key_calls import _translation_call_names
from ._ast_key_policy import _KEY_PATTERN_PREFIX_MIN_PARTS, _KEY_PREFIX_RE
from ._ast_key_syntax import _callee_name, _is_dotted_literal, _is_dynamic_translation_prefix, _walk_nodes


def _dotted_prefix_tables(tree: ast.AST) -> dict[str, frozenset[str]]:
    """Return ``name -> dotted prefixes`` for tables that hold ONLY prefix literals.

    A surface that renders many enums through one helper does not write the
    prefix at the call site; it declares a table of them and selects one. The
    literals are still written down, which is what makes this readable without
    guessing.
    """
    tables: dict[str, frozenset[str]] = {}
    for node in _walk_nodes(tree):
        collect_dotted_prefix_table(node, tables)
    return tables


def _names_selected_from_a_prefix_table(tree: ast.AST, tables: dict[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """Return the local names bound by reading one prefix out of such a table."""
    bound: dict[str, frozenset[str]] = {}
    for node in _walk_nodes(tree):
        bind_selected_prefix_table(node, tables, bound)
    return bound


def _extract_fstring_prefixes(tree: ast.AST) -> set[str]:
    """Walk f-string literals and emit ``<prefix>.*`` namespace markers.

    Walks every f-string literal whose leading segment matches the
    dotted-key shape and emits ``<prefix>.*`` namespace markers.

    Covers both inline call sites (``tr(f"cli.registry.metrics.{x}")``)
    and the assignment form (``key = f"wizard.errors.{reason}"``)
    that the runtime then passes to a downstream call.

    The head literal must end in a dot — that's the explicit
    key-segment marker. ``f"topic.{slug}.title"`` qualifies because
    the head ``topic.`` ends in a dot; ``f"plain text {value}"``
    does not.
    """
    findings: set[str] = set()
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        if not node.values:
            continue
        head = node.values[0]
        if not isinstance(head, ast.Constant) or not isinstance(head.value, str):
            continue
        if not _KEY_PREFIX_RE.match(head.value):
            continue
        prefix = head.value.rstrip(".")
        if not _is_dynamic_translation_prefix(prefix):
            continue
        findings.add(f"{prefix}.*")
    findings |= _interpolated_head_prefixes(tree)
    return findings


def _interpolated_head_prefixes(tree: ast.AST) -> set[str]:
    """Emit markers for ``f"{prefix}.{value}"`` where ``prefix`` is a declared literal.

    The literal-head rule cannot see this shape at all: the head is an
    interpolation, so a helper that renders every enum on a screen through one
    selected prefix declares no namespace, and every key it builds reads as an
    orphan.

    The next segment must begin with the dot. That is what proves the
    interpolated name is being used AS a dotted prefix rather than as ordinary
    text, and it keeps the rule from firing on any f-string that happens to
    start with a variable.
    """
    tables = _dotted_prefix_tables(tree)
    if not tables:
        return set()
    bound = _names_selected_from_a_prefix_table(tree, tables)
    if not bound:
        return set()
    findings: set[str] = set()
    for node in _walk_nodes(tree):
        collect_interpolated_prefixes(node, bound, findings)
    return findings


def _extract_concat_prefixes(tree: ast.AST) -> set[str]:
    """Walk string-concatenation call sites and emit literal-prefix ``.*`` markers.

    Walks ``tr(<literal> + <expr>)`` and ``t(<literal> + <expr>)``
    concatenations and emits the literal-prefix ``.*`` marker.

    Matches the dynamic-key pattern ``tr("cli.registry.metrics." + key)``
    where the literal carries the registered key prefix.
    """
    findings: set[str] = set()
    tr_names = _translation_call_names(tree)
    for node in _walk_nodes(tree):
        if not isinstance(node, ast.Call):
            continue
        if _callee_name(node.func) not in tr_names:
            continue
        for argument in node.args:
            prefix = _concat_prefix_marker(argument)
            if prefix is not None:
                findings.add(prefix)
    return findings


def _concat_prefix_marker(argument: ast.expr) -> str | None:
    """Return the ``<prefix>.*`` marker for a ``"<literal>" + <expr>`` arg, or None."""
    if not isinstance(argument, ast.BinOp) or not isinstance(argument.op, ast.Add):
        return None
    left = argument.left
    if not isinstance(left, ast.Constant) or not isinstance(left.value, str):
        return None
    literal = left.value.rstrip(".")
    if not _is_dotted_literal(literal):
        return None
    if len(literal.split(".")) < _KEY_PATTERN_PREFIX_MIN_PARTS:
        return None
    if not _is_dynamic_translation_prefix(literal):
        return None
    return f"{literal}.*"


def collect_dotted_prefix_table(node: ast.AST, tables: dict[str, frozenset[str]]) -> None:
    """Collect dotted prefix table."""
    target: ast.expr | None = None
    value: ast.expr | None = None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    if not isinstance(target, ast.Name) or not isinstance(value, ast.Dict) or not value.values:
        return
    register_literal_prefix_table(target, value, tables)


def register_literal_prefix_table(target: ast.Name, value: ast.Dict, tables: dict[str, frozenset[str]]) -> None:
    """Register literal prefix table."""
    literals = [item.value for item in value.values if isinstance(item, ast.Constant) and isinstance(item.value, str)]
    if len(literals) == len(value.values) and all(_is_dotted_literal(literal) for literal in literals):
        tables[target.id] = frozenset(literals)


def bind_selected_prefix_table(
    node: ast.AST, tables: dict[str, frozenset[str]], bound: dict[str, frozenset[str]]
) -> None:
    """Bind selected prefix table."""
    target: ast.expr | None = None
    value: ast.expr | None = None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target, value = node.targets[0], node.value
    elif isinstance(node, ast.AnnAssign):
        target, value = node.target, node.value
    if not isinstance(target, ast.Name) or value is None:
        return
    base = prefix_table_access_base(value)
    if base is not None and base in tables:
        bound[target.id] = tables[base]


def prefix_table_access_base(value: ast.expr) -> str | None:
    """Prefix table access base."""
    base: str | None = None
    if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
        base = value.value.id
    elif (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "get"
        and isinstance(value.func.value, ast.Name)
    ):
        base = value.func.value.id
    return base


def collect_interpolated_prefixes(node: ast.AST, bound: dict[str, frozenset[str]], findings: set[str]) -> None:
    """Collect interpolated prefixes."""
    if (name := interpolated_prefix_name(node)) is None:
        return
    for prefix in bound.get(name, ()):
        if _is_dynamic_translation_prefix(prefix):
            findings.add(f"{prefix}.*")


def interpolated_prefix_name(node: ast.AST) -> str | None:
    """Interpolated prefix name."""
    if not isinstance(node, ast.JoinedStr) or len(node.values) < 2:
        return
    head, following = node.values[0], node.values[1]
    if not (isinstance(head, ast.FormattedValue) and isinstance(head.value, ast.Name)):
        return
    if not (isinstance(following, ast.Constant) and isinstance(following.value, str)):
        return
    if not following.value.startswith("."):
        return
    return head.value.id
