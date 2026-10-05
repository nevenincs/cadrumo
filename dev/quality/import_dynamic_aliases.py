"""Dynamic aliases for the subordinate import checker."""

from __future__ import annotations

import ast

from .import_check_models import SourceModule
from .import_module_syntax import assigned_names, qualified_name


def dynamic_aliases(module: SourceModule) -> tuple[set[str], set[str], set[str]]:
    """Collect dynamic-loader aliases in source traversal order."""
    import_module_names = {"importlib.import_module"}
    importlib_names = {"importlib"}
    raw_import_names = {"builtins.__import__", "__import__"}
    for node in ast.walk(module.tree):
        _collect_dynamic_alias_node(module, node, import_module_names, importlib_names, raw_import_names)
    return import_module_names, importlib_names, raw_import_names


def _collect_dynamic_alias_node(
    module: SourceModule,
    node: ast.AST,
    import_module_names: set[str],
    importlib_names: set[str],
    raw_import_names: set[str],
) -> None:
    """Collect dynamic alias node."""
    if isinstance(node, ast.Import):
        _collect_dynamic_import_aliases(node, import_module_names, importlib_names, raw_import_names)
    elif isinstance(node, ast.ImportFrom) and node.level == 0:
        _collect_dynamic_from_aliases(node, import_module_names, importlib_names, raw_import_names)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        _collect_dynamic_assigned_aliases(node, import_module_names, importlib_names, raw_import_names)


def _collect_dynamic_import_aliases(
    node: ast.Import, import_module_names: set[str], importlib_names: set[str], raw_import_names: set[str]
) -> None:
    """Collect dynamic import aliases."""
    for alias in node.names:
        local = alias.asname or alias.name.split(".", 1)[0]
        if alias.name == "importlib":
            importlib_names.add(local)
        elif alias.name == "importlib.import_module" and alias.asname:
            import_module_names.add(local)
        elif alias.name == "builtins":
            raw_import_names.add(f"{local}.__import__")
        elif alias.name == "builtins.__import__" and alias.asname:
            raw_import_names.add(local)


def _collect_dynamic_from_aliases(
    node: ast.ImportFrom, import_module_names: set[str], importlib_names: set[str], raw_import_names: set[str]
) -> None:
    """Collect dynamic from aliases."""
    if node.module == "importlib":
        _collect_importlib_from_aliases(node, import_module_names)
    elif node.module == "builtins":
        _collect_builtins_from_aliases(node, raw_import_names)


def _collect_dynamic_assigned_aliases(
    node: ast.Assign | ast.AnnAssign,
    import_module_names: set[str],
    importlib_names: set[str],
    raw_import_names: set[str],
) -> None:
    """Collect dynamic assigned aliases."""
    value = node.value
    if value is None:
        return
    qualified = qualified_name(value)
    for local in assigned_names(node.targets if isinstance(node, ast.Assign) else (node.target,)):
        _collect_dynamic_local_alias(local, qualified, value, import_module_names, importlib_names, raw_import_names)


def _collect_dynamic_local_alias(
    local: str,
    qualified: str | None,
    value: ast.AST,
    import_module_names: set[str],
    importlib_names: set[str],
    raw_import_names: set[str],
) -> None:
    """Collect dynamic local alias."""
    if qualified == "importlib" or qualified in importlib_names:
        importlib_names.add(local)
    if qualified == "builtins":
        raw_import_names.add(f"{local}.__import__")
    _collect_import_module_assignment(local, qualified, value, import_module_names, importlib_names)
    if qualified == "builtins.__import__" or qualified in raw_import_names:
        raw_import_names.add(local)


def _collect_importlib_from_aliases(node: ast.ImportFrom, import_module_names: set[str]) -> None:
    """Collect importlib from aliases."""
    for alias in node.names:
        if alias.name == "*":
            import_module_names.add("import_module")
        elif alias.name == "import_module":
            import_module_names.add(alias.asname or alias.name)


def _collect_builtins_from_aliases(node: ast.ImportFrom, raw_import_names: set[str]) -> None:
    """Collect builtins from aliases."""
    for alias in node.names:
        if alias.name == "*":
            raw_import_names.add("__import__")
        elif alias.name == "__import__":
            raw_import_names.add(alias.asname or alias.name)


def _collect_import_module_assignment(
    local: str, qualified: str | None, value: ast.AST, import_module_names: set[str], importlib_names: set[str]
) -> None:
    """Collect import module assignment."""
    if (
        qualified == "importlib.import_module"
        or qualified in import_module_names
        or (
            isinstance(value, ast.Attribute)
            and value.attr == "import_module"
            and isinstance(value.value, ast.Name)
            and value.value.id in importlib_names
        )
    ):
        import_module_names.add(local)
