"""Dynamic aliases for the subordinate import checker."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Final, Literal

from .import_check_models import SourceModule
from .import_module_syntax import assigned_names, qualified_name

type DynamicLoaderKind = Literal["import_module", "raw_import", "run_module"]

#: The keyword each loader accepts for its module target when it is not positional.
DYNAMIC_TARGET_KEYWORDS: Final[dict[DynamicLoaderKind, str]] = {
    "import_module": "name",
    "raw_import": "name",
    "run_module": "mod_name",
}


@dataclass
class DynamicAliases:
    """Every local spelling one module binds for a first-party module loader."""

    import_module_names: set[str] = field(default_factory=lambda: {"importlib.import_module"})
    importlib_names: set[str] = field(default_factory=lambda: {"importlib"})
    raw_import_names: set[str] = field(default_factory=lambda: {"builtins.__import__", "__import__"})
    run_module_names: set[str] = field(default_factory=lambda: {"runpy.run_module"})
    runpy_names: set[str] = field(default_factory=lambda: {"runpy"})

    def loader_kind(self, call: ast.Call) -> DynamicLoaderKind | None:
        """Classify *call* as one module loader, judged by this call alone."""
        qualified = qualified_name(call.func)
        if qualified in self.raw_import_names:
            return "raw_import"
        if qualified in self.import_module_names:
            return "import_module"
        if _is_module_attribute(call.func, "import_module", self.importlib_names):
            return "import_module"
        if qualified in self.run_module_names or _is_module_attribute(call.func, "run_module", self.runpy_names):
            return "run_module"
        return None


def _is_module_attribute(function: ast.AST, attribute: str, module_names: set[str]) -> bool:
    """Recognise ``alias.attribute`` where ``alias`` names the loader's module."""
    return (
        isinstance(function, ast.Attribute)
        and function.attr == attribute
        and isinstance(function.value, ast.Name)
        and function.value.id in module_names
    )


def dynamic_aliases(module: SourceModule) -> DynamicAliases:
    """Collect dynamic-loader aliases in source traversal order."""
    aliases = DynamicAliases()
    for node in ast.walk(module.tree):
        _collect_dynamic_alias_node(node, aliases)
    return aliases


def _collect_dynamic_alias_node(node: ast.AST, aliases: DynamicAliases) -> None:
    """Collect dynamic alias node."""
    if isinstance(node, ast.Import):
        _collect_dynamic_import_aliases(node, aliases)
    elif isinstance(node, ast.ImportFrom) and node.level == 0:
        _collect_dynamic_from_aliases(node, aliases)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        _collect_dynamic_assigned_aliases(node, aliases)


def _collect_dynamic_import_aliases(node: ast.Import, aliases: DynamicAliases) -> None:
    """Collect dynamic import aliases."""
    for alias in node.names:
        local = alias.asname or alias.name.split(".", 1)[0]
        if alias.name == "importlib":
            aliases.importlib_names.add(local)
        elif alias.name == "importlib.import_module" and (alias.asname is not None and alias.asname):
            aliases.import_module_names.add(local)
        elif alias.name == "builtins":
            aliases.raw_import_names.add(f"{local}.__import__")
        elif alias.name == "builtins.__import__" and (alias.asname is not None and alias.asname):
            aliases.raw_import_names.add(local)
        elif alias.name == "runpy":
            aliases.runpy_names.add(local)


def _collect_dynamic_from_aliases(node: ast.ImportFrom, aliases: DynamicAliases) -> None:
    """Collect dynamic from aliases."""
    if node.module == "importlib":
        _collect_named_from_aliases(node, "import_module", aliases.import_module_names)
    elif node.module == "builtins":
        _collect_named_from_aliases(node, "__import__", aliases.raw_import_names)
    elif node.module == "runpy":
        _collect_named_from_aliases(node, "run_module", aliases.run_module_names)


def _collect_named_from_aliases(node: ast.ImportFrom, loader: str, names: set[str]) -> None:
    """Collect the local names a ``from module import loader`` statement binds."""
    for alias in node.names:
        if alias.name == "*":
            names.add(loader)
        elif alias.name == loader:
            names.add(alias.asname or alias.name)


def _collect_dynamic_assigned_aliases(node: ast.Assign | ast.AnnAssign, aliases: DynamicAliases) -> None:
    """Collect dynamic assigned aliases."""
    value = node.value
    if value is None:
        return
    qualified = qualified_name(value)
    for local in assigned_names(node.targets if isinstance(node, ast.Assign) else (node.target,)):
        _collect_dynamic_local_alias(local, qualified, value, aliases)


def _collect_dynamic_local_alias(local: str, qualified: str | None, value: ast.AST, aliases: DynamicAliases) -> None:
    """Collect dynamic local alias."""
    if qualified == "importlib" or qualified in aliases.importlib_names:
        aliases.importlib_names.add(local)
    if qualified == "runpy" or qualified in aliases.runpy_names:
        aliases.runpy_names.add(local)
    if qualified == "builtins":
        aliases.raw_import_names.add(f"{local}.__import__")
    if qualified in aliases.import_module_names or _is_module_attribute(
        value, "import_module", aliases.importlib_names
    ):
        aliases.import_module_names.add(local)
    if qualified in aliases.run_module_names or _is_module_attribute(value, "run_module", aliases.runpy_names):
        aliases.run_module_names.add(local)
    if qualified in aliases.raw_import_names:
        aliases.raw_import_names.add(local)
