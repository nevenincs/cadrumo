"""Binding inventory for the subordinate import checker."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping

from dev._paths import UTF_8

from .import_check_models import Authority, Finding, ImportBinding, SourceModule
from .import_module_syntax import assigned_names, is_first_party, is_import_alias, module_name, resolve_from


def read_modules(authority: Authority) -> tuple[dict[str, SourceModule], list[Finding]]:
    """Parse every governed source and collect its module binding facts."""
    modules: dict[str, SourceModule] = {}
    findings: list[Finding] = []
    for root in authority.roots:
        try:
            paths = sorted(root.path.rglob("*.py"), key=lambda item: item.as_posix())
        except OSError as exc:
            findings.append(Finding("READ_FAILURE", f"cannot enumerate governed root: {exc}", root.path, fatal=True))
            continue
        if not paths:
            findings.append(
                Finding(
                    "ZERO_FILES",
                    f"root {root.name!r} contains no governed Python files",
                    root.path,
                    fatal=True,
                )
            )
        for path in paths:
            try:
                source = path.read_text(encoding=UTF_8)
            except (OSError, UnicodeError) as exc:
                findings.append(Finding("READ_FAILURE", f"cannot read governed file: {exc}", path, fatal=True))
                continue
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError as exc:
                findings.append(
                    Finding("PARSE_FAILURE", f"cannot parse governed file: {exc.msg}", path, exc.lineno, True)
                )
                continue
            name = module_name(path, root)
            if name in modules:
                findings.append(Finding("INTERNAL_CHECKER", f"duplicate module identity {name!r}", path, fatal=True))
                continue
            modules[name] = SourceModule(name, path, tree, path.name == "__init__.py")

    for module in modules.values():
        _collect_bindings(module, authority.root_names)
    return modules, findings


def _collect_bindings(module: SourceModule, root_names: frozenset[str]) -> None:
    imported_names: set[str] = set()
    for node in _iter_binding_statements(module.tree.body):
        _collect_statement_binding(module, root_names, imported_names, node)


def _iter_binding_statements(nodes: Iterable[ast.stmt]) -> Iterable[ast.stmt]:
    """Yield module-scope bindings from guarded and exception-handling blocks."""
    for node in nodes:
        yield node
        if isinstance(node, ast.If):
            yield from _iter_binding_statements((*node.body, *node.orelse))
        elif isinstance(node, ast.Try):
            yield from _iter_binding_statements(node.body)
            for handler in node.handlers:
                yield from _iter_binding_statements(handler.body)
            yield from _iter_binding_statements(node.orelse)
            yield from _iter_binding_statements(node.finalbody)


def check_initializers(authority: Authority, modules: Mapping[str, SourceModule], findings: list[Finding]) -> None:
    """Report executable statements in first-party package initializers."""
    del authority
    for module in modules.values():
        if not module.is_package:
            continue
        for node in module.tree.body:
            if _is_allowed_initializer_node(module.tree, node):
                continue
            findings.append(
                Finding(
                    "ACTIVE_INITIALIZER",
                    "package initializer must contain only documentation, future imports, pass, or empty __all__",
                    module.path,
                    getattr(node, "lineno", None),
                )
            )


def _is_allowed_initializer_node(tree: ast.Module, node: ast.stmt) -> bool:
    if _is_docstring_node(tree, node) or isinstance(node, ast.Pass):
        return True
    if isinstance(node, ast.ImportFrom) and node.module == "__future__":
        return True
    return _is_empty_all_assignment(node)


def _is_docstring_node(tree: ast.Module, node: ast.stmt) -> bool:
    return bool(
        tree.body
        and tree.body[0] is node
        and isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_empty_all_assignment(node: ast.stmt) -> bool:
    if isinstance(node, ast.Assign):
        names = assigned_names(node.targets)
        value: ast.expr | None = node.value
    elif isinstance(node, ast.AnnAssign):
        names = assigned_names((node.target,))
        value = node.value
    else:
        return False
    return names == ("__all__",) and isinstance(value, (ast.Tuple, ast.List)) and not value.elts


def _collect_statement_binding(
    module: SourceModule, root_names: frozenset[str], imported_names: set[str], node: ast.stmt
) -> None:
    """Collect statement binding."""
    if isinstance(node, ast.Import):
        _collect_import_binding(module, root_names, imported_names, node)
    elif isinstance(node, ast.ImportFrom):
        _collect_from_binding(module, root_names, imported_names, node)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        module.local_definitions += 1
        module.bindings[node.name] = ImportBinding("definition")
    elif isinstance(node, ast.Assign):
        _collect_assigned_binding(module, imported_names, node)
    elif isinstance(node, ast.AnnAssign):
        _collect_annotated_binding(module, imported_names, node)
    elif isinstance(node, ast.TypeAlias):
        module.local_definitions += 1
        module.bindings[node.name.id] = ImportBinding("definition")


def _collect_import_binding(
    module: SourceModule, root_names: frozenset[str], imported_names: set[str], node: ast.Import
) -> None:
    """Collect import binding."""
    module.has_imports = True
    for alias in node.names:
        local = alias.asname or alias.name.split(".", 1)[0]
        module.bindings[local] = ImportBinding("import", target=alias.name)
        imported_names.add(local)
        if is_first_party(alias.name, root_names):
            module.imported_count += 1


def _collect_from_binding(
    module: SourceModule, root_names: frozenset[str], imported_names: set[str], node: ast.ImportFrom
) -> None:
    """Collect from binding."""
    module.has_imports = True
    target = resolve_from(module.name, module.is_package, node.level, node.module)
    for alias in node.names:
        if alias.name == "*":
            continue
        local = alias.asname or alias.name
        kind = "import" if target is not None and is_first_party(target, root_names) else "external-import"
        module.bindings[local] = ImportBinding(kind, target=target, imported_name=alias.name)
        imported_names.add(local)
        if kind == "import":
            module.imported_count += 1


def _collect_assigned_binding(module: SourceModule, imported_names: set[str], node: ast.Assign) -> None:
    """Collect assigned binding."""
    kind = "alias" if is_import_alias(node.value, imported_names) else "definition"
    for name in assigned_names(node.targets):
        if name == "__all__":
            continue
        module.bindings[name] = ImportBinding(kind)
        if kind == "definition":
            module.local_definitions += 1


def _collect_annotated_binding(module: SourceModule, imported_names: set[str], node: ast.AnnAssign) -> None:
    """Collect annotated binding."""
    kind = "alias" if node.value is not None and is_import_alias(node.value, imported_names) else "definition"
    for name in assigned_names((node.target,)):
        if name == "__all__":
            continue
        module.bindings[name] = ImportBinding(kind)
        if kind == "definition":
            module.local_definitions += 1
