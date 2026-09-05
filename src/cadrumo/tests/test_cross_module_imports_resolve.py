"""Cross-module import resolution gate.

Importing a package cleanly proves only that its own module body runs.
This gate proves the other direction: every
``from cadrumo.X import {name}`` statement under ``src/cadrumo/`` resolves
to an attribute that actually exists on ``cadrumo.X``.

Closes the foreign-WIP failure pattern that surfaced three times in
the linkage integrity regression where a sibling change added an import
to a caller without adding the matching name to the target package's
``__init__.py`` imports / ``__all__``. The consumer module then
raises ``ImportError`` the next time any test collection walks it,
breaking the whole suite at collection time even though the target
package itself imports cleanly.

The scan walks every ``.py`` file under ``src/cadrumo/``, parses each
via :mod:`ast`, collects every ``ImportFrom`` statement that targets
the in-repo ``cadrumo.*`` namespace (absolute or relative), resolves
the target package, and asserts every imported name is
attribute-accessible after :func:`importlib.import_module`. Conditional
imports inside ``if TYPE_CHECKING:`` blocks are skipped because their
names are never bound at runtime; everything else is in scope.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from .inventory import SRC_CADRUMO, package_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _is_type_checking_block(node: ast.AST) -> bool:
    """Return True when ``node`` is an ``if TYPE_CHECKING:`` guard."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _resolve_relative_module(source: Path, level: int, module: str | None) -> str | None:
    """Resolve ``from .module import X`` against ``source``'s package path.

    Python's relative-import semantics: ``level=1`` means *the package
    that contains this module*; ``level=2`` means that package's
    parent; and so on. For a non-``__init__`` file at
    ``cadrumo/sub/mod.py`` the containing package is ``cadrumo.sub``; for
    ``cadrumo/sub/__init__.py`` the file IS the package ``cadrumo.sub`` and
    the containing package is still ``cadrumo.sub``.

    Returns the absolute dotted module name (e.g. ``cadrumo.domain.modelos``)
    or ``None`` if the source file lives outside ``src/cadrumo`` (which
    would be a project layout violation; not this gate's concern).
    """
    try:
        relative = source.relative_to(SRC_CADRUMO.parent)
    except ValueError:
        return None
    parts = list(relative.with_suffix("").parts)
    # Whether ``source`` is an ``__init__.py`` (the package itself) or a
    # regular module (living inside its containing package), the package's
    # dotted path is recovered the same way: drop the trailing element.
    package_parts = parts[:-1]
    # ``level=1`` keeps every element; each additional level walks one
    # package up.
    if level - 1 > len(package_parts):
        return None
    anchor = package_parts[: len(package_parts) - (level - 1)] if level > 1 else package_parts
    if module:
        anchor = anchor + module.split(".")
    return ".".join(anchor)


def _walk_import_from(tree: ast.AST) -> Iterator[ast.ImportFrom]:
    """Yield every ``ImportFrom`` node not inside an ``if TYPE_CHECKING:`` block."""
    skip: set[int] = set()
    for node in ast.walk(tree):
        if _is_type_checking_block(node):
            for child in ast.walk(node):
                skip.add(id(child))
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.ImportFrom):
            yield node


def _collect_import_pairs(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> list[tuple[Path, str, str]]:
    """Walk every Cadrumo source and yield ``(source_file, module, name)`` import triples.

    Only ``from cadrumo.X import Y`` (absolute) and relative imports
    resolving back into the ``cadrumo.*`` tree are returned. ``import *``
    statements are excluded — they don't pin a specific name and the
    no-wildcard hygiene is a separate concern.
    """
    triples: list[tuple[Path, str, str]] = []
    for source, tree in package_ast_items(source_tree_ast, include_data=True):
        for node in _walk_import_from(tree):
            resolved = _resolve_relative_module(source, node.level, node.module) if node.level > 0 else node.module
            if not resolved or not resolved.startswith("cadrumo"):
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                triples.append((source, resolved, alias.name))
    return triples


# Committed-baseline allow-list of broken cross-module imports the gate
# captured on its first run. Each entry is a known finding tracked as a
# follow-up (see ``ratchet history`` in the schema-hardening plan). The gate
# asserts the live set of broken triples equals this baseline exactly:
# any NEW broken import fails fast (the regression we want to catch),
# and any allow-list entry that becomes resolvable also fails (so a
# silent fix can be acknowledged by trimming the baseline). Trim
# entries as the underlying breakage is fixed; the gate is fully green
# once this set is empty.
_BASELINE_BROKEN_IMPORTS: frozenset[tuple[str, str, str]] = frozenset[tuple[str, str, str]]()


@pytest.fixture(scope="module")
def cadrumo_import_triples(source_tree_ast: Mapping[Path, ast.AST]) -> list[tuple[Path, str, str]]:
    """Collect import triples once per module from the shared package AST cache."""
    return _collect_import_pairs(source_tree_ast)


def _check_triple(triple: tuple[Path, str, str]) -> str | None:
    """Return None when the triple resolves, or a one-line failure description otherwise.

    Two resolution paths: (a) ``name`` is bound as an attribute on the
    target package (the canonical ``__init__.py`` re-export pattern),
    or (b) ``name`` is a submodule importable as ``{module}.{name}``
    (the ``from pkg import mod`` shape Python resolves lazily). The
    gate must accept both — only a triple that fails both paths is a
    true broken-import finding.
    """
    source, module, name = triple
    try:
        target = importlib.import_module(module)
    except ImportError as exc:
        return (
            f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}  "
            f"(target module raised ImportError: {exc})"
        )
    if hasattr(target, name):
        return None
    # Submodule import path — ``from pkg import mod`` succeeds if
    # ``pkg.mod`` is a real importable module, regardless of whether
    # ``pkg.__init__`` binds ``mod`` as an attribute.
    try:
        importlib.import_module(f"{module}.{name}")
        return None
    except ImportError:
        pass
    return f"{source.relative_to(SRC_CADRUMO.parent).as_posix()}::{module}::{name}"


def test_cadrumo_cross_module_imports_resolve_against_baseline(
    cadrumo_import_triples: list[tuple[Path, str, str]],
) -> None:
    """Every ``from cadrumo.X import Y`` triple resolves, modulo the committed baseline.

    Walks every parsed import triple, classifies it as resolvable or
    broken, then asserts the broken set equals ``_BASELINE_BROKEN_IMPORTS``
    exactly. Fails fast on:

    * **regressions**: a new broken triple not in the baseline (the
      foreign-WIP-without-export pattern this gate exists to catch).
    * **silent fixes**: an allow-list entry that no longer fails (so
      the baseline gets trimmed instead of accruing dead entries).

    The companion ``__init__.py`` gate below extends this check to
    fail at ``__init__.py``-modification time, not just when a
    broken consumer is encountered.
    """
    live_breakage: set[tuple[str, str, str]] = set()
    for triple in cadrumo_import_triples:
        source, module, name = triple
        if _check_triple(triple) is None:
            continue
        live_breakage.add((source.relative_to(SRC_CADRUMO.parent).as_posix(), module, name))

    regressions = live_breakage - _BASELINE_BROKEN_IMPORTS
    silent_fixes = _BASELINE_BROKEN_IMPORTS - live_breakage

    failure_lines: list[str] = []
    if regressions:
        failure_lines.append(
            "New broken cross-module imports detected (regression — fix the import "
            "or update the target package's __init__.py + __all__):",
        )
        failure_lines.extend(f"  + {entry}" for entry in sorted(regressions))
    if silent_fixes:
        failure_lines.append("Allow-list entries are now resolvable (trim _BASELINE_BROKEN_IMPORTS):")
        failure_lines.extend(f"  - {entry}" for entry in sorted(silent_fixes))
    assert not failure_lines, "\n" + "\n".join(failure_lines)


def test_at_least_one_cadrumo_cross_module_import_was_collected(
    cadrumo_import_triples: list[tuple[Path, str, str]],
) -> None:
    """Sanity: the AST walk found import triples to validate.

    Guards against a future refactor that silently breaks the source
    discovery (e.g. renaming ``src/cadrumo`` or changing the package
    layout) and turns the gate into a zero-row no-op.
    """
    assert len(cadrumo_import_triples) > 100, (
        f"Cross-module import scan found only {len(cadrumo_import_triples)} import triples — "
        f"the source-tree walk probably broke. Expected hundreds of "
        f"``from cadrumo.X import Y`` statements across the package."
    )


# Per-file count cap for the __init__.py public-import-without-__all__ gate.
# Mirrors the singleton-warning regression cap idiom: each entry pins
# the maximum number of public sibling imports an
# ``__init__.py`` may carry without listing them in ``__all__``. The
# gate fails when a file's count grows (regression — public surface
# drifted further off ``__all__``) OR when a file's count shrinks
# (silent fix — trim the cap so the gain is locked in) OR when a
# new file enters the set (regression — new ``__init__.py`` skipped
# the discipline). Trim caps as packages clean up; the close state
# is an empty mapping.
_INIT_MISSING_FROM_ALL_BASELINE: dict[str, int] = {
    # Peer-introduced drift discovered by the import-resolution gate:
    # these entries set the regression cap at the current count so the
    # gate ratchets shut as packages clean up their __all__ exports.
    # Decrement the cap (never increment) as imports get listed.
    "cadrumo/entrypoints/cli/__init__.py": 1,
}


def _collect_init_missing_from_all(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> list[tuple[str, str]]:
    """For each ``__init__.py`` under src/cadrumo/, return public-import names absent from ``__all__``.

    The contract: any name (a) imported into the package's
    ``__init__.py`` from a sibling module via ``from .X import Y``,
    AND (b) public (no leading underscore), must also appear in
    ``__all__`` if the file declares one. Leading-underscore names
    are private and intentionally not re-exported. ``__init__.py``
    files without ``__all__`` are exempt (nothing to drift against).
    """
    findings: list[tuple[str, str]] = []
    for source, tree in package_ast_items(source_tree_ast, include_data=True):
        if source.name != "__init__.py":
            continue
        all_names = _extract_all_assignment(tree)
        if all_names is None:
            continue
        rel = source.relative_to(SRC_CADRUMO.parent).as_posix()
        # Only TOP-LEVEL ImportFrom nodes bind on the package's __init__
        # namespace. Function-body and class-body imports are runtime
        # locals; they neither bind on the package nor count as
        # implicit re-exports.
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            # Only the package's OWN siblings count — absolute imports
            # from elsewhere in Cadrumo or stdlib re-exports are caller's
            # choice, not a package-public-surface promise.
            if node.level == 0:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                exposed = alias.asname or alias.name
                if exposed.startswith("_"):
                    continue
                if exposed not in all_names:
                    findings.append((rel, exposed))
    return findings


def _extract_all_assignment(tree: ast.AST) -> set[str] | None:
    """Return the literal names listed in ``__all__``, or ``None`` if not declared."""
    for node in ast.iter_child_nodes(tree):
        target_name: str | None = None
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id == "__all__":
                target_name = tgt.id
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            target_name = node.target.id
            value = node.value
        if target_name is None or value is None:
            continue
        if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return None
        names: set[str] = set()
        for element in value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                names.add(element.value)
        return names
    return None


def test_init_public_imports_appear_in_all_against_baseline(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every public name imported into an ``__init__.py`` from a sibling must be in ``__all__``.

    Catches the half-export pattern: a package imports a public name
    into its ``__init__.py`` (binding it as an attribute on the
    package) but forgets to add it to ``__all__``. The wildcard
    consumer ``from pkg import *`` then misses the name, and the
    public-surface contract drifts off the ``__all__`` source of truth.

    Sibling check to the consumer-resolution gate above — together
    they pin every ``__init__.py`` re-export at both ends: the
    consumer-side proves imports resolve; this side proves the
    package's own re-exports are coherent.

    Uses the per-file count-cap idiom so historical findings stay
    tracked without an inline tuple list. Each cap is a regression
    boundary:
    a file's count cannot grow without the gate failing, and any
    shrink must be locked in by trimming the cap.
    """
    live_findings = _collect_init_missing_from_all(source_tree_ast)
    live_counts: dict[str, int] = {}
    for path, _name in live_findings:
        live_counts[path] = live_counts.get(path, 0) + 1

    failure_lines: list[str] = []
    for path, live_count in sorted(live_counts.items()):
        cap = _INIT_MISSING_FROM_ALL_BASELINE.get(path)
        if cap is None:
            failure_lines.append(
                f"  + {path!r}: new __init__.py with {live_count} public sibling import(s) missing from __all__",
            )
        elif live_count > cap:
            failure_lines.append(
                f"  + {path!r}: grew from {cap} to {live_count} public-import-without-__all__ findings",
            )
        elif live_count < cap:
            failure_lines.append(
                f"  - {path!r}: cap is {cap} but only {live_count} "
                f"finding(s) remain — trim _INIT_MISSING_FROM_ALL_BASELINE",
            )

    # Files in the baseline but absent from live findings are silent
    # fixes too — the entire cap should be removed.
    for path, cap in sorted(_INIT_MISSING_FROM_ALL_BASELINE.items()):
        if path not in live_counts and cap > 0:
            failure_lines.append(
                f"  - {path!r}: all {cap} finding(s) resolved — remove the entry from _INIT_MISSING_FROM_ALL_BASELINE",
            )

    if failure_lines:
        header = (
            "Public names imported into __init__.py but missing from __all__ "
            "(regression caps drifted — fix the underlying drift or update the cap):"
        )
        raise AssertionError("\n" + header + "\n" + "\n".join(failure_lines))
