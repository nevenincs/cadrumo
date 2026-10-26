"""Resolve shipped import, deferred-string and child-process module edges."""

from __future__ import annotations

import ast
from collections import deque
from collections.abc import Iterable, Iterator, Mapping

from dev.quality.source_import_analysis import (
    resolve_relative_import,
    type_checking_guarded_nodes,
)

from .unreachable_members import resolved_member_uses
from .unreachable_memo import _walked
from .unreachable_models import ShippedModule
from .unreachable_policy import _DOTTED_SPEC, _MODULE_EXEC_FLAG
from .unreachable_receiver_types import ReceiverTypes

# ---------------------------------------------------------------------------
# Module layer: import-graph reachability from the entry points
# ---------------------------------------------------------------------------


def _unreachable_package_members(
    unreachable: frozenset[str], modules: dict[str, ShippedModule]
) -> dict[str, list[str]]:
    """Unreachable package members."""
    members: dict[str, list[str]] = {}
    for name in sorted(unreachable):
        if not modules[name].is_package:
            continue
        below = [other for other in modules if other == name or other.startswith(name + ".")]
        if all(other in unreachable for other in below):
            members[name] = below
    return members


def _ancestors(name: str) -> Iterator[str]:
    parts = name.split(".")
    for end in range(1, len(parts) + 1):
        yield ".".join(parts[:end])


def _known_prefixes(name: str, known: frozenset[str]) -> Iterator[str]:
    yield from (candidate for candidate in _ancestors(name) if candidate in known)


def _string_module_target(value: str, module: ShippedModule, known: frozenset[str]) -> str | None:
    """Resolve a string literal to the shipped module it names, if any.

    Accepts ``pkg.mod``, ``pkg.mod:attr``, and package-relative ``.mod``
    spellings; everything else is prose and is ignored.
    """
    if not _DOTTED_SPEC.match(value):
        return None
    target = value.partition(":")[0]
    if target.startswith("."):
        level = len(target) - len(target.lstrip("."))
        remainder = target[level:] or None
        resolved = resolve_relative_import(module.name, module.is_package, level, remainder)
        return resolved if resolved in known else None
    return target if target in known else None


def _spawn_edges(module: ShippedModule, known: frozenset[str]) -> frozenset[str]:
    """Return the modules ``module`` starts as a ``python -m`` child interpreter.

    A console script that spawns another shipped package as a child process
    reaches it as surely as an import does; the operator types one product
    command and the target runs. Modelling only import edges would report that
    package as ``python -m``-only, which is exactly backwards: the ``python -m``
    surface is the mechanism, and a product command is the caller.

    The edge is only drawn on positive evidence of both halves in the same
    module: the ``-m`` interpreter flag as a literal, and a literal naming a
    shipped package that owns a ``__main__``. A module mentioning a package name
    for any other reason draws nothing, because the flag will be absent.
    """
    literals = {
        node.value for node in _walked(module.tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    if _MODULE_EXEC_FLAG not in literals:
        return frozenset[str]()
    targets: set[str] = set()
    for name in literals:
        main = f"{name}.__main__"
        if name in known and main in known:
            targets.update((name, main))
    return frozenset(targets)


def module_edges(module: ShippedModule, known: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(runtime_edges, type_only_edges)`` from ``module`` to shipped modules."""
    guarded = type_checking_guarded_nodes(module.tree)
    runtime: set[str] = set()
    type_only: set[str] = set()
    for node in _walked(module.tree):
        targets = _node_module_targets(node, module, known)
        if targets is None:
            continue
        (type_only if id(node) in guarded else runtime).update(targets)
    return frozenset(runtime), frozenset(type_only - runtime)


def reachable_closure(
    roots: Iterable[str],
    modules: dict[str, ShippedModule],
    edges: dict[str, frozenset[str]],
) -> frozenset[str]:
    """Breadth-first closure over ``edges``; importing a module imports its ancestors."""
    seen: set[str] = set()
    queue: deque[str] = deque(root for root in roots if root in modules)
    while queue:
        current = queue.popleft()
        for name in _ancestors(current):
            if name in modules and name not in seen:
                seen.add(name)
                queue.extend(target for target in edges[name] if target not in seen)
    return frozenset(seen)


def _collapse_packages(unreachable: frozenset[str], modules: dict[str, ShippedModule]) -> list[tuple[str, int]]:
    """Report a folder once when every module under it is unreachable.

    Returns ``(module_name, spanned_count)`` pairs: packages first, then the
    loose modules no reported package covers.
    """
    members = _unreachable_package_members(unreachable, modules)
    maximal = [pkg for pkg in members if not any(pkg != other and pkg.startswith(other + ".") for other in members)]
    covered = {name for pkg in maximal for name in members[pkg]}
    findings = [(pkg, len(members[pkg])) for pkg in sorted(maximal)]
    findings.extend((name, 1) for name in sorted(unreachable) if name not in covered)
    return findings


def _import_aliases(module: ShippedModule, known: frozenset[str]) -> dict[str, str]:
    """Map every local binding that names a shipped module to that module.

    Both spellings bind a module to a name: ``import a.b as c`` and
    ``from . import orm as _orm``. The relative form is resolved through the
    importing module's own position, so a package-relative alias is not lost.
    """
    aliases: dict[str, str] = {}
    for node in _walked(module.tree):
        _read_import_alias_node(node, module, known, aliases)
    return aliases


def resolved_symbol_uses(
    module: ShippedModule, known: frozenset[str], receivers: ReceiverTypes | None = None
) -> set[tuple[str, str]]:
    """Return every ``(defining module, symbol)`` pair this module actually reaches.

    Only two syntaxes can reach a top-level symbol across a module boundary:
    a ``from M import N``, and an attribute read on a binding that names ``M``.
    Both are resolved here; a bare identifier load is deliberately not, because
    it says nothing about which module defined the name.
    """
    uses: set[tuple[str, str]] = resolved_member_uses(module, known, receivers=receivers)
    for node in _walked(module.tree):
        if isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
            if base in known:
                uses.update((base, alias.name) for alias in node.names)
    aliases = _import_aliases(module, known)
    if aliases:
        for node in _walked(module.tree):
            _read_alias_attribute_use(node, aliases, uses)
    return uses


def _shipped_importers(edges: Mapping[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    """Reverse ``edges`` into "who imports this", over shipped modules only.

    Both runtime and type-checking edges count. The question the reverse graph
    answers is "does anything shipped still name this module", and a
    type-checking-only importer names it just as definitely as a runtime one
    even though the statement never executes.
    """
    reverse: dict[str, set[str]] = {}
    for source, targets in edges.items():
        for target in targets:
            reverse.setdefault(target, set()).add(source)
    return {target: frozenset(sources) for target, sources in reverse.items()}


def _importers_of_span(
    name: str,
    modules: Mapping[str, ShippedModule],
    importers: Mapping[str, frozenset[str]],
) -> tuple[str, ...]:
    """Shipped importers of ``name``'s whole span, excluding the span itself.

    A package finding stands for every module beneath it, so an importer of
    any member is an importer of the finding. Members importing each other are
    internal traffic and say nothing about whether anything outside still
    needs the span.
    """
    span: set[str] = set()
    for member in modules:
        if member == name or member.startswith(name + "."):
            span.add(member)
    outside_importers: set[str] = set()
    for member in span:
        for source in importers.get(member, frozenset()):
            if source not in span:
                outside_importers.add(source)
    return tuple(sorted(outside_importers))


def _node_module_targets(node: ast.AST, module: ShippedModule, known: frozenset[str]) -> list[str] | None:
    """Resolve one import or deferred string before its guard assigns the edge."""
    targets: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            targets.extend(_known_prefixes(alias.name, known))
    elif isinstance(node, ast.ImportFrom):
        base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
        if base is None:
            return None
        targets.extend(_known_prefixes(base, known))
        targets.extend(f"{base}.{alias.name}" for alias in node.names if f"{base}.{alias.name}" in known)
    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        resolved = _string_module_target(node.value, module, known)
        if resolved is not None:
            targets.append(resolved)
    else:
        return None
    return targets


def _read_import_alias_node(
    node: ast.AST, module: ShippedModule, known: frozenset[str], aliases: dict[str, str]
) -> None:
    """Read import alias node."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in known:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
    elif isinstance(node, ast.ImportFrom):
        base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
        if base is None:
            return
        for alias in node.names:
            target = f"{base}.{alias.name}"
            if target in known:
                aliases[alias.asname or alias.name] = target


def _read_alias_attribute_use(node: ast.AST, aliases: dict[str, str], uses: set[tuple[str, str]]) -> None:
    """Read alias attribute use."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        owner = aliases.get(node.value.id)
        if owner is not None:
            uses.add((owner, node.attr))
