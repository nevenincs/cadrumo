"""Static checks for the subordinate import checker."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .import_check_models import Authority, Finding, ImportBinding, SourceModule
from .import_module_syntax import is_descendant, is_first_party, is_package, module_package, resolve_from


def check_static_imports(authority: Authority, modules: Mapping[str, SourceModule], findings: list[Finding]) -> None:
    """Check every static import for canonical ownership and target existence."""
    known = frozenset((*modules, *authority.root_packages))
    root_names = authority.root_names
    for module in modules.values():
        for node in ast.walk(module.tree):
            _check_static_node(authority, modules, findings, known, root_names, module, node)


def _report_import_spelling_advisory(
    module: SourceModule, target: str, node: ast.Import | ast.ImportFrom, findings: list[Finding]
) -> None:
    """Report absolute first-party spelling as non-architectural style advice."""
    is_absolute = isinstance(node, ast.Import) or node.level == 0
    in_cadrumo = module.name == "cadrumo" or module.name.startswith("cadrumo.")
    if is_absolute and in_cadrumo and (target == "cadrumo" or target.startswith("cadrumo.")):
        findings.append(
            Finding(
                "CANONICAL_IMPORT_SPELLING",
                f"absolute canonical import of {target!r}; relative spelling is optional style",
                module.path,
                node.lineno,
                advisory=True,
            )
        )


def _names_dunder_init_submodule(dotted: str) -> bool:
    """Recognise the spelling that addresses ``package.__init__`` itself."""
    return dotted == "__init__" or dotted.endswith(".__init__")


def check_private(
    module: SourceModule,
    target: str,
    imported_name: str,
    modules: Mapping[str, SourceModule],
    authority: Authority,
    findings: list[Finding],
    lineno: int,
) -> None:
    """Report an import that reaches another package private owner."""
    components = target.split(".")
    private_index = next(
        (
            index
            for index, component in enumerate(components)
            if component.startswith("_") and component not in {"__init__"}
        ),
        None,
    )
    if private_index is not None:
        owner = ".".join(components[:private_index])
        if not is_descendant(module.name, owner):
            findings.append(
                Finding(
                    "PRIVATE_CROSS_PACKAGE",
                    f"{module.name!r} reaches private module {target!r}",
                    module.path,
                    lineno,
                )
            )
    if imported_name.startswith("_") and not imported_name.startswith("__"):
        owner = module_package(target, modules, authority.root_names)
        if owner and not is_descendant(module.name, owner):
            findings.append(
                Finding(
                    "PRIVATE_CROSS_PACKAGE",
                    f"{module.name!r} reaches private symbol {imported_name!r}",
                    module.path,
                    lineno,
                )
            )


def _check_static_node(
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    root_names: frozenset[str],
    module: SourceModule,
    node: ast.AST,
) -> None:
    """Check static node."""
    if isinstance(node, ast.Import):
        _check_import_node(authority, modules, findings, known, root_names, module, node)
    elif isinstance(node, ast.ImportFrom):
        _check_from_node(authority, modules, findings, known, root_names, module, node)


def _check_import_node(
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    root_names: frozenset[str],
    module: SourceModule,
    node: ast.Import,
) -> None:
    """Check import node."""
    for alias in node.names:
        target = alias.name
        if _names_dunder_init_submodule(target):
            findings.append(
                Finding(
                    "DUNDER_INIT_SUBMODULE",
                    "do not import a package through a submodule named __init__",
                    module.path,
                    node.lineno,
                )
            )
        if not is_first_party(target, root_names):
            continue
        _report_import_spelling_advisory(module, target, node, findings)
        check_private(module, target, alias.name, modules, authority, findings, node.lineno)
        if target not in known:
            findings.append(
                Finding(
                    "STATIC_TARGET_UNRESOLVED",
                    f"first-party import target {target!r} does not exist",
                    module.path,
                    node.lineno,
                )
            )


def _check_from_node(
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    root_names: frozenset[str],
    module: SourceModule,
    node: ast.ImportFrom,
) -> None:
    """Check from node."""
    target = resolve_from(module.name, module.is_package, node.level, node.module)
    if _names_dunder_init_submodule(node.module or ""):
        findings.append(
            Finding(
                "DUNDER_INIT_SUBMODULE",
                "do not import a package through a submodule named __init__",
                module.path,
                node.lineno,
            )
        )
    if target is None:
        findings.append(
            Finding(
                "UNSUPPORTED_IMPORT",
                "relative import escapes its configured package root",
                module.path,
                node.lineno,
            )
        )
        return
    if not is_first_party(target, root_names):
        return
    _report_import_spelling_advisory(module, target, node, findings)
    if target not in known:
        findings.append(
            Finding(
                "STATIC_TARGET_UNRESOLVED",
                f"first-party import target {target!r} does not exist",
                module.path,
                node.lineno,
            )
        )
        return
    for alias in node.names:
        _check_from_alias(authority, modules, findings, known, root_names, module, node, target, alias)


def _check_from_alias(
    authority: Authority,
    modules: Mapping[str, SourceModule],
    findings: list[Finding],
    known: frozenset[str],
    root_names: frozenset[str],
    module: SourceModule,
    node: ast.ImportFrom,
    target: str,
    alias: ast.alias,
) -> None:
    """Check from alias."""
    if alias.name == "*":
        findings.append(
            Finding(
                "UNSUPPORTED_IMPORT",
                "wildcard first-party imports cannot prove a canonical home",
                module.path,
                node.lineno,
            )
        )
        return
    child = f"{target}.{alias.name}"
    if is_package(target, modules, root_names) and child in known:
        check_private(module, child, alias.name, modules, authority, findings, node.lineno)
        return
    check_private(module, target, alias.name, modules, authority, findings, node.lineno)
    target_module = modules.get(target)
    if target_module is None:
        return
    if target_module.is_package or target in root_names:
        findings.append(
            Finding(
                "PACKAGE_FACADE",
                f"symbol {alias.name!r} is consumed from package facade {target!r}",
                module.path,
                node.lineno,
            )
        )
        return
    binding = target_module.bindings.get(alias.name)
    _check_canonical_symbol(target_module, target, alias, findings, module, node, binding)


def _check_canonical_symbol(
    target_module: SourceModule,
    target: str,
    alias: ast.alias,
    findings: list[Finding],
    module: SourceModule,
    node: ast.ImportFrom,
    binding: ImportBinding | None,
) -> None:
    """Check canonical symbol."""
    if binding is None:
        findings.append(
            Finding(
                "CANONICAL_TARGET_MISSING",
                f"{target!r} does not define imported symbol {alias.name!r}",
                module.path,
                node.lineno,
            )
        )
    elif binding.kind in {"import", "alias", "external-import"}:
        category = (
            "FORWARDING_MODULE"
            if target_module.local_definitions == 0 and target_module.has_imports
            else "REEXPORT_OR_ALIAS"
        )
        findings.append(
            Finding(
                category,
                f"{target}.{alias.name} is not a canonical defining-module symbol",
                module.path,
                node.lineno,
            )
        )
