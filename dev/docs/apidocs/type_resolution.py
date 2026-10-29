"""Resolve and render source-defined public API type aliases."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING

from .source_bindings import statement_binds_name
from .source_context import (
    dotted_expression,
    module_import_context,
    module_source_path,
    source_import_binding,
    source_module_name,
    source_name_is_shadowed,
    source_package_root,
)
from .type_alias_policy import (
    BUILTIN_GENERIC_FACTORIES,
    BUILTIN_TYPE_EXPRESSIONS,
    TYPE_ALIAS_CALL_FACTORIES,
    TYPE_ALIAS_FACTORY_MODULES,
)

_UTF_8 = UTF_8_ENCODING


def type_alias_expression(
    value: ast.expr,
    path: Path | None = None,
    seen: frozenset[tuple[Path, str]] = frozenset(),
) -> bool:
    """Return whether *value* is a source expression that defines a type alias."""
    if isinstance(value, ast.Subscript):
        return _type_expression_factory(value.value, path, TYPE_ALIAS_FACTORY_MODULES, seen)
    if isinstance(value, ast.BinOp):
        return (
            isinstance(value.op, ast.BitOr)
            and _union_operand_is_type(value.left, path, seen)
            and _union_operand_is_type(value.right, path, seen)
        )
    if isinstance(value, ast.Call):
        return _type_expression_factory(
            value.func,
            path,
            TYPE_ALIAS_CALL_FACTORIES,
            seen,
            allow_source_type_factory=False,
        )
    return False


def is_type_checking_guard(test: ast.expr, path: Path) -> bool:
    """Return whether *test* names an unshadowed canonical TYPE_CHECKING import."""
    if isinstance(test, ast.Name):
        binding = source_import_binding(path, test.id)
        return binding is not None and binding[1:3] in {
            ("typing", "TYPE_CHECKING"),
            ("typing_extensions", "TYPE_CHECKING"),
        }

    parts = dotted_expression(test)
    if parts is None or len(parts) != 2 or parts[1] != "TYPE_CHECKING":
        return False
    binding = source_import_binding(path, parts[0])
    return binding is not None and binding[1] in {"typing", "typing_extensions"} and binding[2] is None


def _type_expression_factory(
    factory: ast.expr,
    path: Path | None,
    canonical_modules: dict[str, frozenset[str]],
    seen: frozenset[tuple[Path, str]],
    *,
    allow_source_type_factory: bool = True,
) -> bool:
    """Accept only canonical or source-resolved generic type factories."""
    if path is None:
        return False
    if isinstance(factory, ast.Name):
        return _named_type_factory(factory.id, path, canonical_modules, seen, allow_source_type_factory)

    parts = dotted_expression(factory)
    if parts is None:
        return False
    binding = source_import_binding(path, parts[0])
    if binding is None:
        return False
    _, module_name, imported_name, has_alias = binding
    if imported_name is not None:
        return False
    qualified = ".".join((module_name, *parts[1:])) if has_alias else ".".join(parts)
    for owner, names in canonical_modules.items():
        prefix = f"{owner}."
        if qualified.startswith(prefix) and qualified[len(prefix) :] in names:
            return True
    return False


def _named_type_factory(
    name: str,
    path: Path,
    canonical_modules: dict[str, frozenset[str]],
    seen: frozenset[tuple[Path, str]],
    allow_source_type_factory: bool,
) -> bool:
    if allow_source_type_factory and name in BUILTIN_GENERIC_FACTORIES:
        try:
            stat = path.stat()
        except OSError:
            return False
        _, shadowed = module_import_context(path, stat.st_mtime_ns, stat.st_size)
        if name not in shadowed:
            return True
    binding = source_import_binding(path, name)
    if binding is not None:
        _, module_name, imported_name, _ = binding
        if imported_name is not None and imported_name in canonical_modules.get(module_name, ()):
            return True
    if not allow_source_type_factory:
        return False
    return module_symbol_is_type(path, name, seen)


def _union_operand_is_type(
    value: ast.expr,
    path: Path | None,
    seen: frozenset[tuple[Path, str]] = frozenset(),
) -> bool:
    """Recognize operands of PEP 604 type unions without treating value unions as types."""
    if isinstance(value, ast.Constant):
        return value.value is None
    if isinstance(value, ast.Name):
        is_source_type = path is not None and module_symbol_is_type(path, value.id, seen)
        is_unshadowed_builtin = value.id in BUILTIN_TYPE_EXPRESSIONS and (
            path is None or not source_name_is_shadowed(path, value.id)
        )
        return is_source_type or is_unshadowed_builtin
    if isinstance(value, ast.Subscript):
        return type_alias_expression(value, path, seen) or _union_operand_is_type(value.value, path, seen)
    if isinstance(value, ast.BinOp):
        return type_alias_expression(value, path, seen)
    return False


def module_symbol_is_type(path: Path, symbol: str, seen: frozenset[tuple[Path, str]] = frozenset()) -> bool:
    """Follow an imported symbol to confirm it is a class or source type alias."""
    key = (path.resolve(), symbol)
    if key in seen:
        return False
    seen = seen | {key}
    try:
        source = path.read_text(encoding=_UTF_8)
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False

    for statement in reversed(tree.body):
        if not statement_binds_name(statement, symbol):
            continue
        return _bound_symbol_is_type(statement, path, tree, symbol, seen)
    return _imported_symbol_is_type(path, tree, symbol, seen)


def _bound_symbol_is_type(
    statement: ast.stmt, path: Path, tree: ast.Module, symbol: str, seen: frozenset[tuple[Path, str]]
) -> bool:
    if isinstance(statement, ast.ClassDef):
        return True
    if isinstance(statement, ast.TypeAlias):
        return True
    if isinstance(statement, ast.AnnAssign):
        return isinstance(statement.annotation, ast.Name) and statement.annotation.id == "TypeAlias"
    if isinstance(statement, ast.Assign):
        if type_alias_expression(statement.value, path, seen):
            return True
        if isinstance(statement.value, ast.Name):
            return module_symbol_is_type(path, statement.value.id, seen)
        return False
    if isinstance(statement, (ast.ImportFrom, ast.Import)):
        return _imported_symbol_is_type(path, tree, symbol, seen, statement)
    return False


def _imported_symbol_is_type(
    path: Path,
    tree: ast.Module,
    symbol: str,
    seen: frozenset[tuple[Path, str]] = frozenset(),
    binding_statement: ast.stmt | None = None,
) -> bool:
    """Return whether a module imports *symbol* from a class or alias owner."""
    source_root = source_package_root(path)
    if source_root is None:
        return False
    module_name = source_module_name(source_root, path)
    package = module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]
    statements = (binding_statement,) if binding_statement is not None else tuple(tree.body)
    for statement in statements:
        if not isinstance(statement, ast.ImportFrom):
            continue
        if _import_from_is_type(statement, package, source_root, symbol, seen):
            return True
    return False


def _import_from_is_type(
    statement: ast.ImportFrom, package: str, source_root: Path, symbol: str, seen: frozenset[tuple[Path, str]]
) -> bool:
    for imported in statement.names:
        local_name = imported.asname or imported.name
        if local_name != symbol:
            continue
        try:
            imported_module = f"{'.' * statement.level}{statement.module or ''}"
            module_name = importlib.util.resolve_name(imported_module, package)
        except ImportError:
            continue
        imported_path = module_source_path(source_root, module_name)
        if imported_path is not None and module_symbol_is_type(imported_path, imported.name, seen):
            return True
    return False
