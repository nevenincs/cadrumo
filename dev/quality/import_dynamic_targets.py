"""Dynamic targets for the subordinate import checker."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from cadrumo.tests.module_target_inventory import MetadataTargetSetError, load_all_target_sets, load_target_set

from .import_check_models import SourceModule
from .import_module_syntax import qualified_name, resolve_from
from .import_target_evaluation import TargetEvaluationContext

_MAX_CLOSED_DYNAMIC_TARGETS: Final[int] = 4096


def metadata_target_set_targets(
    target_node: ast.AST,
    lineno: int,
    module: SourceModule,
    context: TargetEvaluationContext,
    repository: Path,
) -> tuple[frozenset[str] | None, bool]:
    """Resolve a generic declared-metadata target-set loader call.

    The loader's checked-in JSON is the finite authority.  This deliberately
    recognises the reusable loader origin rather than a caller, artifact path,
    or target-set name, so any governed module can use a declared inventory.
    """
    targets: set[str] = set()
    resolved_any = False
    exhaustive = False
    for candidate in _metadata_target_set_candidate_nodes(target_node, lineno, context, set()):
        if not isinstance(candidate, ast.Call):
            continue
        loader = _metadata_target_set_loader(module, candidate.func)
        if loader is None:
            continue
        path_node = _call_argument(candidate, "metadata_path", positional_index=0)
        paths = context.values_for(path_node, candidate.lineno)
        if paths is None:
            return None, False
        resolved_any = True
        loaded, exhaustive = _load_metadata_paths(paths, loader, candidate, context, repository, targets, exhaustive)
        if not loaded:
            return None, False
        if len(targets) > _MAX_CLOSED_DYNAMIC_TARGETS:
            return None, False
    return (frozenset(targets) if resolved_any and targets else None), exhaustive


def _metadata_target_set_candidate_nodes(
    node: ast.AST,
    lineno: int,
    context: TargetEvaluationContext,
    resolving: set[tuple[int, str]],
) -> Iterable[ast.AST]:
    """Yield *node* and the finite assignment chain that can name its loader call."""
    yield node
    if not isinstance(node, ast.Name):
        return
    scope = context.nearest_function(node)
    key = (id(scope) if scope is not None else 0, node.id)
    if key in resolving:
        return
    assignments = context.latest_values(node.id, lineno, scope)
    if not (assignments is not None and assignments):
        return
    resolving.add(key)
    for assignment in assignments:
        yield from _metadata_target_set_candidate_nodes(assignment.value, assignment.lineno - 1, context, resolving)
    resolving.remove(key)


def _call_argument(node: ast.Call, name: str, *, positional_index: int) -> ast.AST | None:
    """Return a named or positional call argument without caller-specific syntax."""
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return node.args[positional_index] if len(node.args) > positional_index else None


def _metadata_target_set_loader(module: SourceModule, function: ast.AST) -> str | None:
    """Return the generic metadata loader kind resolved by *function*."""
    qualified = qualified_name(function)
    if qualified is None:
        return None
    expected: dict[str, str] = {
        "cadrumo.tests.module_target_inventory.load_all_target_sets": "all",
        "cadrumo.tests.module_target_inventory.load_target_set": "named",
    }
    if qualified in expected:
        return expected[qualified]
    head, separator, tail = qualified.partition(".")
    binding = module.bindings.get(head)
    if binding is None or binding.target is None:
        return None
    resolved = f"{binding.target}.{binding.imported_name}" if not separator else f"{binding.target}.{tail}"
    return expected.get(resolved)


def dynamic_target(module: SourceModule, target: str, call: ast.Call, context: TargetEvaluationContext) -> str | None:
    """Resolve one dynamic target against its explicit package anchor."""
    if not target.startswith("."):
        return target
    package = _dynamic_package(module, call, context)
    if package is None:
        return None
    level = len(target) - len(target.lstrip("."))
    remainder = target[level:] or None
    return resolve_from(package, True, level, remainder)


def _dynamic_package(module: SourceModule, call: ast.Call, context: TargetEvaluationContext) -> str | None:
    """Dynamic package."""
    package_node = next((keyword.value for keyword in call.keywords if keyword.arg == "package"), None)
    if package_node is None and len(call.args) > 1:
        package_node = call.args[1]
    if isinstance(package_node, ast.Name) and package_node.id == "__package__":
        package = module.name if module.is_package else module.name.rpartition(".")[0]
    else:
        package_values = context.values_for(package_node, call.lineno)
        if package_values is None or len(package_values) != 1:
            return None
        package = next(iter(package_values))
    return package


def _load_metadata_paths(
    paths: frozenset[str],
    loader: str,
    candidate: ast.Call,
    context: TargetEvaluationContext,
    repository: Path,
    targets: set[str],
    exhaustive: bool,
) -> tuple[bool, bool]:
    """Load metadata paths."""
    try:
        for path in paths:
            if loader == "all":
                exhaustive = True
                targets.update(load_all_target_sets(path, repository=repository))
            else:
                set_node = _call_argument(candidate, "target_set", positional_index=1)
                names = context.values_for(set_node, candidate.lineno)
                if names is None:
                    return False, False
                for name in names:
                    targets.update(load_target_set(path, name, repository=repository))
    except MetadataTargetSetError:
        return False, False
    return True, exhaustive
