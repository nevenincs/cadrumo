"""Dynamic checks for the subordinate import checker."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .import_check_models import Authority, Finding, SourceModule
from .import_dynamic_aliases import DYNAMIC_TARGET_KEYWORDS, DynamicLoaderKind, dynamic_aliases
from .import_dynamic_strings import carries_interpreter_payload, string_payload_imports
from .import_dynamic_targets import dynamic_target, metadata_target_set_targets
from .import_module_syntax import is_first_party, is_package
from .import_record_provenance import RecordTargetProvenance
from .import_static_checks import check_private
from .import_target_evaluation import TargetEvaluationContext


def check_dynamic_imports(
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    record_provenance: RecordTargetProvenance,
) -> None:
    """Resolve finite dynamic and interpreter-payload imports and report unsupported targets."""
    known = frozenset((*modules, *authority.root_packages))
    for module in modules.values():
        aliases = dynamic_aliases(module)
        dynamic_calls: list[tuple[ast.Call, DynamicLoaderKind]] = []
        payload_hosts: list[ast.AST] = []
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call):
                kind = aliases.loader_kind(node)
                if kind is not None:
                    dynamic_calls.append((node, kind))
            if carries_interpreter_payload(node):
                payload_hosts.append(node)
        if not (dynamic_calls or payload_hosts):
            continue
        context = TargetEvaluationContext(module.tree, module.name)
        for host in payload_hosts:
            _check_string_payloads(host, module, context, authority, modules, findings, known)
        for node, kind in dynamic_calls:
            _check_dynamic_call(node, kind, module, context, authority, modules, findings, known, record_provenance)


def _check_string_payloads(
    host: ast.AST,
    module: SourceModule,
    context: TargetEvaluationContext,
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
) -> None:
    """Apply the import rules to every first-party module an interpreter payload names."""
    for item in string_payload_imports(host, context):
        if not is_first_party(item.target, authority.root_names):
            continue
        if item.target not in known:
            findings.append(
                Finding(
                    "STATIC_TARGET_UNRESOLVED",
                    f"first-party interpreter payload target {item.target!r} does not exist",
                    module.path,
                    item.lineno,
                )
            )
            continue
        for symbol in item.symbols or ("",):
            child = f"{item.target}.{symbol}"
            if symbol and is_package(item.target, modules, authority.root_names) and child in known:
                check_private(module, child, symbol, modules, authority, findings, item.lineno)
            else:
                check_private(module, item.target, symbol, modules, authority, findings, item.lineno)


def _check_dynamic_target(
    target: str,
    module: SourceModule,
    node: ast.Call,
    context: TargetEvaluationContext,
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    kind: DynamicLoaderKind,
    computed_projection: bool,
    exhaustive_census: bool,
    record_provenance: RecordTargetProvenance,
) -> None:
    """Check dynamic target."""
    resolved = (
        None
        if kind == "run_module" and target.startswith(".")
        else dynamic_target(module, target, node, context, record_provenance=record_provenance)
    )
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
    if kind == "raw_import":
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
    kind: DynamicLoaderKind,
    module: SourceModule,
    context: TargetEvaluationContext,
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    record_provenance: RecordTargetProvenance,
) -> None:
    """Check dynamic call."""
    target_node = (
        node.args[0]
        if node.args
        else next(
            (keyword.value for keyword in node.keywords if keyword.arg == DYNAMIC_TARGET_KEYWORDS[kind]),
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
        module, target_node, node, context, authority, record_provenance
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
            kind,
            computed_projection,
            exhaustive_census,
            record_provenance,
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
    record_provenance: RecordTargetProvenance,
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
        targets = record_provenance.targets(module.name, target_node)
        computed_projection = targets is not None
    return targets, computed_projection, exhaustive_census
