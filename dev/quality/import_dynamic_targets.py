"""Dynamic targets for the subordinate import checker."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final

from cadrumo.tests.module_target_inventory import MetadataTargetSetError, load_all_target_sets, load_target_set

from .import_check_models import SourceModule
from .import_module_syntax import is_first_party, qualified_name, resolve_from
from .import_target_evaluation import TargetEvaluationContext

_MAX_CLOSED_DYNAMIC_TARGETS: Final[int] = 4096


def discover_closed_attribute_targets(
    modules: Mapping[str, SourceModule], root_names: frozenset[str], known: frozenset[str]
) -> frozenset[str]:
    """Derive the finite module values carried by object ``.module`` fields.

    The product's outer resolvers pass immutable target records into
    ``import_module`` rather than keeping a second import map beside the
    declarations.  A checker that only evaluates bare strings would therefore
    mistake ``import_module(target.module)`` for an open computation.  Harvest
    the literal constructor values that can populate a module field, resolving
    relative values against the constructor's explicit package argument.  This
    is a closed set derived from source, not an allowlist: an unknown or
    unbounded constructor expression contributes nothing and remains a finding.
    """
    targets: set[str] = set()
    module_record_classes = _module_record_classes(modules)
    if not module_record_classes:
        return frozenset[str]()
    return _collect_closed_attribute_targets(modules, root_names, known, targets, module_record_classes)


def _module_record_classes(modules: Mapping[str, SourceModule]) -> frozenset[str]:
    """Find record classes that declare a ``module`` field."""
    classes: set[str] = set()
    for module in modules.values():
        for node in module.tree.body:
            _collect_module_record_class(node, module, classes)
    return frozenset(classes)


def _is_module_record_constructor(module: SourceModule, call: ast.Call, module_record_classes: frozenset[str]) -> bool:
    """Return whether a call names a locally or explicitly imported module record."""
    if not isinstance(call.func, ast.Name):
        return False
    local_name = call.func.id
    if f"{module.name}.{local_name}" in module_record_classes:
        return True
    binding = module.bindings.get(local_name)
    if binding is None or binding.target is None or binding.imported_name is None:
        return False
    return f"{binding.target}.{binding.imported_name}" in module_record_classes


def _constructor_argument(node: ast.Call, name: str, *, positional_index: int) -> ast.AST | None:
    """Return one constructor field expression without naming a product class."""
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return node.args[positional_index] if len(node.args) > positional_index else None


def _resolve_constructor_target(
    module: SourceModule,
    value: str,
    package_node: ast.AST | None,
    call: ast.Call,
    context: TargetEvaluationContext,
) -> str | None:
    """Resolve one literal constructor module value, or reject it as open."""
    if not value.startswith("."):
        return value
    if package_node is None:
        return None
    if isinstance(package_node, ast.Name) and package_node.id == "__package__":
        package = module.name if module.is_package else module.name.rpartition(".")[0]
    else:
        package_values = context.values_for(package_node, call.lineno)
        if package_values is None or len(package_values) != 1:
            return None
        package = next(iter(package_values))
    level = len(value) - len(value.lstrip("."))
    remainder = value[level:] or None
    return resolve_from(package, True, level, remainder)


def computed_attribute_targets(
    target_node: ast.AST,
    lineno: int,
    context: TargetEvaluationContext,
    closed_attribute_targets: frozenset[str],
) -> frozenset[str] | None:
    """Return the closed set for a projected module field, if one exists."""
    if isinstance(target_node, ast.Attribute) and target_node.attr == "module" and closed_attribute_targets:
        return closed_attribute_targets
    if isinstance(target_node, ast.Name) and closed_attribute_targets:
        scope = context.nearest_function(target_node)
        assignments = context.latest_values(target_node.id, lineno, scope)
        if assignments and any(
            _is_module_projection_expression(assignment.value, context, lineno, scope, set())
            for assignment in assignments
        ):
            return closed_attribute_targets
    return None


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
    if not assignments:
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


def _is_module_projection_expression(
    node: ast.AST,
    context: TargetEvaluationContext,
    lineno: int,
    scope: ast.AST | None,
    resolving: set[str],
) -> bool:
    """Recognise a finite expression that projects target records' module fields."""
    if isinstance(node, (ast.SetComp, ast.ListComp, ast.GeneratorExp)):
        return isinstance(node.elt, ast.Attribute) and node.elt.attr == "module"
    if isinstance(node, ast.Name) and node.id not in resolving:
        assignments = context.latest_values(node.id, lineno, scope)
        if assignments:
            resolving.add(node.id)
            result = any(
                _is_module_projection_expression(assignment.value, context, lineno, scope, resolving)
                for assignment in assignments
            )
            resolving.remove(node.id)
            return result
    return False


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


def _collect_module_record_class(node: ast.stmt, module: SourceModule, classes: set[str]) -> None:
    """Collect module record class."""
    if not isinstance(node, ast.ClassDef):
        return
    fields = {
        item.target.id for item in node.body if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }
    fields.update(
        item.targets[0].id
        for item in node.body
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name)
    )
    if "module" in fields:
        classes.add(f"{module.name}.{node.name}")


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


def _collect_closed_attribute_targets(
    modules: Mapping[str, SourceModule],
    root_names: frozenset[str],
    known: frozenset[str],
    targets: set[str],
    module_record_classes: frozenset[str],
) -> frozenset[str]:
    """Collect closed attribute targets."""
    for module in modules.values():
        constructors = [
            node
            for node in ast.walk(module.tree)
            if isinstance(node, ast.Call) and _is_module_record_constructor(module, node, module_record_classes)
        ]
        if not constructors:
            continue
        context = TargetEvaluationContext(module.tree, module.name)
        for node in constructors:
            if not _collect_constructor_targets(node, module, context, targets, root_names, known):
                return frozenset[str]()
    return frozenset(targets)


def _collect_constructor_targets(
    node: ast.Call,
    module: SourceModule,
    context: TargetEvaluationContext,
    targets: set[str],
    root_names: frozenset[str],
    known: frozenset[str],
) -> bool:
    """Collect bounded canonical targets from one constructor."""
    module_node = _constructor_argument(node, "module", positional_index=0)
    if module_node is None:
        return True
    values = context.values_for(module_node, node.lineno)
    if values is None:
        return True
    package_node = _constructor_argument(node, "package", positional_index=2)
    for value in values:
        resolved = _resolve_constructor_target(module, value, package_node, node, context)
        if resolved is None or not is_first_party(resolved, root_names) or resolved not in known:
            continue
        targets.add(resolved)
        if len(targets) > _MAX_CLOSED_DYNAMIC_TARGETS:
            return False
    return True


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
