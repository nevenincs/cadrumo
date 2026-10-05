"""Dynamic checks for the subordinate import checker."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .import_check_models import Authority, Finding, SourceModule
from .import_dynamic_aliases import dynamic_aliases
from .import_dynamic_targets import computed_attribute_targets, dynamic_target, metadata_target_set_targets
from .import_module_syntax import is_first_party, qualified_name
from .import_static_checks import check_private
from .import_target_evaluation import TargetEvaluationContext


def check_dynamic_imports(
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    closed_attribute_targets: frozenset[str],
) -> None:
    """Resolve finite dynamic imports and report unsupported targets."""
    known = frozenset((*modules, *authority.root_packages))
    for module in modules.values():
        import_module_names, importlib_names, raw_import_names = dynamic_aliases(module)
        dynamic_calls: list[ast.Call] = []
        is_raw_import = False
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call):
                is_raw_import = _collect_dynamic_call(
                    node, import_module_names, importlib_names, raw_import_names, dynamic_calls
                )
        if not dynamic_calls:
            continue
        context = TargetEvaluationContext(module.tree, module.name)
        for node in dynamic_calls:
            _check_dynamic_call(
                node, module, context, authority, modules, findings, known, is_raw_import, closed_attribute_targets
            )


def _collect_dynamic_call(
    node: ast.Call,
    import_module_names: set[str],
    importlib_names: set[str],
    raw_import_names: set[str],
    dynamic_calls: list[ast.Call],
) -> bool:
    """Collect dynamic call."""
    qualified = qualified_name(node.func)
    is_import_module = qualified in import_module_names or (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "import_module"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in importlib_names
    )
    is_raw_import = qualified in raw_import_names or qualified in {"__import__", "builtins.__import__"}
    if not (is_import_module or is_raw_import):
        return is_raw_import
    dynamic_calls.append(node)
    return is_raw_import


def _check_dynamic_target(
    target: str,
    module: SourceModule,
    node: ast.Call,
    context: TargetEvaluationContext,
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    is_raw_import: bool,
    computed_projection: bool,
    exhaustive_census: bool,
) -> None:
    """Check dynamic target."""
    resolved = dynamic_target(module, target, node, context)
    if resolved is None or not resolved:
        findings.append(
            Finding(
                "UNRESOLVED_DYNAMIC_TARGET",
                f"dynamic target {target!r} cannot be resolved",
                module.path,
                node.lineno,
            )
        )
        return
    if is_raw_import:
        if is_first_party(resolved, authority.root_names):
            findings.append(
                Finding(
                    "RAW_FIRST_PARTY_IMPORT",
                    f"raw __import__ loads first-party target {resolved!r}",
                    module.path,
                    node.lineno,
                )
            )
        return
    if not is_first_party(resolved, authority.root_names):
        return
    _report_dynamic_spelling(module, resolved, target, node, computed_projection, authority, findings)
    if not exhaustive_census:
        check_private(
            module,
            resolved,
            resolved.rsplit(".", 1)[-1],
            modules,
            authority,
            findings,
            node.lineno,
        )
    if resolved not in known:
        findings.append(
            Finding(
                "DYNAMIC_TARGET_UNRESOLVED",
                f"first-party dynamic target {resolved!r} does not exist",
                module.path,
                node.lineno,
            )
        )


def _check_dynamic_call(
    node: ast.Call,
    module: SourceModule,
    context: TargetEvaluationContext,
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    is_raw_import: bool,
    closed_attribute_targets: frozenset[str],
) -> None:
    """Check dynamic call."""
    target_node = (
        node.args[0]
        if node.args
        else next(
            (keyword.value for keyword in node.keywords if keyword.arg == "name"),
            None,
        )
    )
    if target_node is None:
        findings.append(
            Finding(
                "UNSUPPORTED_DYNAMIC",
                "dynamic import has no module target argument",
                module.path,
                node.lineno,
            )
        )
        return
    targets, computed_projection, exhaustive_census = _resolve_dynamic_call_targets(
        module, target_node, node, context, authority, closed_attribute_targets
    )
    if targets is None or not targets:
        findings.append(
            Finding(
                "UNRESOLVED_DYNAMIC_TARGET",
                "computed dynamic import is not a finite closed target set",
                module.path,
                node.lineno,
            )
        )
        return
    for target in sorted(targets):
        _check_dynamic_target(
            target,
            module,
            node,
            context,
            authority,
            modules,
            findings,
            known,
            is_raw_import,
            computed_projection,
            exhaustive_census,
        )


def _report_dynamic_spelling(
    module: SourceModule,
    resolved: str,
    target: str,
    node: ast.Call,
    computed_projection: bool,
    authority: Authority,
    findings: list[Finding],
) -> None:
    """Report dynamic spelling."""
    in_cadrumo = module.name == "cadrumo" or module.name.startswith("cadrumo.")
    if (
        in_cadrumo
        and not computed_projection
        and not target.startswith(".")
        and is_first_party(resolved, frozenset({"cadrumo"}))
    ):
        findings.append(
            Finding(
                "CANONICAL_IMPORT_SPELLING",
                f"absolute canonical dynamic target {resolved!r}; relative spelling is optional style",
                module.path,
                node.lineno,
                advisory=True,
            )
        )


def _resolve_dynamic_call_targets(
    module: SourceModule,
    target_node: ast.AST,
    node: ast.Call,
    context: TargetEvaluationContext,
    authority: Authority,
    closed_attribute_targets: frozenset[str],
) -> tuple[frozenset[str] | None, bool, bool]:
    """Resolve dynamic call targets."""
    targets = context.values_for(target_node, node.lineno)
    metadata_backed = False
    exhaustive_census = False
    if targets is None or not targets:
        targets, exhaustive_census = metadata_target_set_targets(
            target_node, node.lineno, module, context, authority.repository
        )
        metadata_backed = targets is not None
    computed_projection = metadata_backed
    if targets is None or not targets:
        targets = computed_attribute_targets(target_node, node.lineno, context, closed_attribute_targets)
        computed_projection = targets is not None
    return targets, computed_projection, exhaustive_census
