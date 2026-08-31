"""Guard: every production secure-object namespace string is registry-declared.

Feature modules may spell a secure-object namespace as an inline string literal
rather than importing its registry constant. The domain repositories deliberately
do so to preserve the lazy-import (json-pipe-safety) contract, which forbids a
module-level ``cadrumo.adapters.persistence.storage`` import; the literal is
duplicated precisely to avoid eagerly pulling the storage package into every CLI
command's import chain.

This gate therefore does NOT require the constant import. It requires the weaker,
universally-satisfiable invariant that a namespace literal cannot drift from the
authority: every ``cadrumo.*`` namespace string that is assigned to a
``*_NAMESPACE`` target or passed as a secure-object call's ``namespace`` argument
must equal a namespace value declared in ``STORAGE_NAMESPACE_REGISTRY``. A literal
that matches no registered namespace is an unenrolled or typo'd namespace and fails
the gate.

The gate scans EVERY production root, not a hand-picked subset, and the anti-vacuity
floor plus the hostile-input and prefix-coherence probes below are load-bearing:
this gate silently went vacuous once already. The ``aeat.`` -> ``cadrumo.`` product
rename moved every namespace value while this gate's detection prefix was left at
``aeat.``, so it walked ~880 production files, matched zero literals, and asserted
that empty list was empty -- green while checking nothing. The floor reds on a
re-drift of either the prefix or the scanned roots; the coherence probe reds the
moment the detection prefix stops naming the registry's own namespaces.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ...adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ...tests import SRC_CADRUMO, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SECURE_OBJECT_METHODS = {
    "delete",
    "exists",
    "iter_records_with_failures",
    "list_object_keys",
    "load",
    "peek_metadata",
    "probe_namespace_integrity",
    "save",
}

#: The production secure-object namespace prefix. Every registry-declared
#: production namespace begins with it, so a namespace-position literal that
#: begins with it is a namespace string this gate must cross-check. Held in
#: lock-step with the registry by :func:`test_detection_prefix_still_names_the_registry`
#: below, because a silent drift of this prefix is exactly what emptied this gate
#: at the ``aeat.`` -> ``cadrumo.`` product rename.
_NAMESPACE_LITERAL_PREFIX = "cadrumo."

#: Every production root is scanned: a namespace literal drifting from the registry
#: is a hazard wherever it is spelled, and restricting the walk to a subset is how a
#: consumer re-introducing a drifted literal outside the subset escapes the gate.
_GUARDED_ROOTS = (SRC_CADRUMO,)


def test_production_secure_object_namespace_literals_match_the_registry(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    registry_values = _registry_namespace_values()
    scanned: list[str] = []
    offences: list[str] = []
    for path, tree in _iter_guarded_production_sources(source_tree_ast):
        relative = repo_relative(path)
        for node in ast.walk(tree):
            for value, lineno in _namespace_literal_usages(node):
                scanned.append(value)
                if value not in registry_values:
                    offences.append(
                        f"{relative}:{lineno}: secure-object namespace literal {value!r} "
                        f"is not declared in STORAGE_NAMESPACE_REGISTRY",
                    )

    # Anti-vacuity floor. With every consumer bound to the registry constant the
    # only namespace-position literals left are the registry's own declarations,
    # but there are ~64 of them, so a scan that finds far fewer means the detection
    # prefix or the scanned roots have drifted and the offence check below is
    # vacuous. This is the assertion that would have caught the aeat-to-cadrumo
    # rename emptying the gate.
    assert len(scanned) >= 40, (
        f"namespace gate matched only {len(scanned)} namespace-position literals; the detection "
        f"prefix {_NAMESPACE_LITERAL_PREFIX!r} or the scanned roots have drifted from the registry, "
        "so a green offence check means 'nothing was checked' rather than 'nothing is wrong'"
    )

    assert offences == []


def test_the_gate_flags_an_unregistered_namespace_literal() -> None:
    """Hostile-input probe: a namespace literal absent from the registry is caught.

    The green scan above proves nothing unless the offence check can fail. A
    synthetic module assigns a ``cadrumo.``-prefixed namespace literal that no
    registry definition declares and passes another to a secure-object ``save``;
    the extraction must surface both and the registry cross-check must reject
    them. The literal is built by concatenation so the gate over the real tree
    never sees this string as a production declaration.
    """
    registry_values = _registry_namespace_values()
    bogus = _NAMESPACE_LITERAL_PREFIX + "unregistered_probe_namespace"
    assert bogus not in registry_values, "probe literal collided with a real registry namespace"

    snippet = f'PROBE_NAMESPACE = "{bogus}"\nrepository.save("{bogus}", record)\n'
    tree = ast.parse(snippet)
    found = [value for node in ast.walk(tree) for value, _ in _namespace_literal_usages(node)]
    assert bogus in found, "extraction failed to see a namespace-position literal it must scan"

    offences = [value for value in found if value not in registry_values]
    assert offences == [bogus, bogus], (
        f"the registry cross-check did not flag the unregistered namespace literal: {offences}"
    )


def test_detection_prefix_still_names_the_registry() -> None:
    """The detection prefix must still name the registry's production namespaces.

    Root cause of the earlier vacuity: the detection prefix drifted from the
    authority (``aeat.`` -> ``cadrumo.``) and nothing caught it, so the walk matched
    nothing. Assert the registry's own production namespaces begin with the prefix,
    so the next such rename reds here immediately rather than emptying the gate.
    """
    registry_values = _registry_namespace_values()
    matched = [value for value in registry_values if value.startswith(_NAMESPACE_LITERAL_PREFIX)]
    assert len(matched) >= 40, (
        f"only {len(matched)} of {len(registry_values)} registry namespaces begin with "
        f"{_NAMESPACE_LITERAL_PREFIX!r}; the detection prefix has drifted from the authority and "
        "this gate no longer scans the namespaces it exists to protect"
    )


def _registry_namespace_values() -> frozenset[str]:
    return frozenset(item.namespace for item in STORAGE_NAMESPACE_REGISTRY.namespaces)


def _iter_guarded_production_sources(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    return tuple(
        sorted(
            (path, tree)
            for path, tree in production_ast_items(source_tree_ast)
            if any(path.is_relative_to(root) for root in _GUARDED_ROOTS)
        ),
    )


def _namespace_literal_usages(node: ast.AST) -> list[tuple[str, int]]:
    """Return ``(value, lineno)`` for every ``cadrumo.*`` namespace literal used as a
    secure-object namespace: assigned to a ``namespace`` / ``*_NAMESPACE`` target or
    passed as a secure-object call's ``namespace`` argument.
    """
    usages: list[tuple[str, int]] = []
    if isinstance(node, ast.Assign):
        if any(_is_namespace_target(target) for target in node.targets):
            _append_literal(usages, node.value)
    elif isinstance(node, ast.AnnAssign):
        if _is_namespace_target(node.target):
            _append_literal(usages, node.value)
    elif isinstance(node, ast.Call):
        for keyword in node.keywords:
            if keyword.arg == "namespace":
                _append_literal(usages, keyword.value)
        if node.args and leaf_name(node.func) in _SECURE_OBJECT_METHODS:
            _append_literal(usages, node.args[0])
    return usages


def _append_literal(usages: list[tuple[str, int]], node: ast.expr | None) -> None:
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(_NAMESPACE_LITERAL_PREFIX)
    ):
        usages.append((node.value, getattr(node, "lineno", -1)))


def _is_namespace_target(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "namespace" or node.id.endswith("_NAMESPACE")
    if isinstance(node, ast.Attribute):
        return node.attr == "namespace" or node.attr.endswith("_NAMESPACE")
    return False
