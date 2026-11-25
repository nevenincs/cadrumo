"""Resolve and render source-defined public API type aliases."""

from __future__ import annotations

import ast
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING

from .source_bindings import bound_names
from .type_resolution import is_type_checking_guard, module_symbol_is_type, type_alias_expression

_UTF_8 = UTF_8_ENCODING


def type_alias_declarations(path: Path) -> tuple[tuple[str, str], ...]:
    """Return public top-level type alias declarations from *path*."""
    source = path.read_text(encoding=_UTF_8)
    tree = ast.parse(source, filename=str(path))
    aliases: dict[str, str] = {}

    for statement in tree.body:
        if isinstance(statement, ast.If) and is_type_checking_guard(statement.test, path):
            for guarded_statement in statement.body:
                _collect_statement(guarded_statement, source, path, aliases)
            continue
        _collect_statement(statement, source, path, aliases)

    return tuple(sorted(aliases.items()))


def public_type_aliases(module_name: str, source_path: Path) -> list[str]:
    """Render type-alias targets and source declarations from their owner module."""
    lines: list[str] = []
    for alias, declaration in type_alias_declarations(source_path):
        lines.extend(
            (
                f".. py:type:: {alias}",
                f"   :module: {module_name}",
                "",
                "   Declared in source:",
                "",
                "   .. code-block:: python",
                "",
                *(f"      {line}" for line in declaration.splitlines()),
                "",
            )
        )
    return lines


def _collect_statement(statement: ast.stmt, source: str, path: Path, aliases: dict[str, str]) -> None:
    for name in bound_names(statement):
        aliases.pop(name, None)

    if isinstance(statement, ast.TypeAlias):
        if not statement.name.id.startswith("_"):
            declaration = ast.get_source_segment(source, statement) or ast.unparse(statement)
            aliases[statement.name.id] = declaration
        return

    alias = _annotated_alias(statement)
    if alias is not None:
        declaration = ast.get_source_segment(source, statement) or ast.unparse(statement)
        aliases[alias] = declaration
        return

    if not isinstance(statement, ast.Assign):
        return

    _collect_assignment(statement, source, path, aliases)


def _annotated_alias(statement: ast.stmt) -> str | None:
    if (
        not isinstance(statement, ast.AnnAssign)
        or statement.value is None
        or not isinstance(statement.target, ast.Name)
    ):
        return None
    if not isinstance(statement.annotation, ast.Name) or statement.annotation.id != "TypeAlias":
        return None
    return None if statement.target.id.startswith("_") else statement.target.id


def _collect_assignment(statement: ast.Assign, source: str, path: Path, aliases: dict[str, str]) -> None:
    targets = tuple(target.id for target in statement.targets if isinstance(target, ast.Name))
    public_targets = tuple(name for name in targets if not name.startswith("_"))
    if not public_targets:
        return

    value = statement.value
    is_type_expression = type_alias_expression(value, path)
    if is_type_expression or _referenced_type_alias(value, path):
        declaration = ast.get_source_segment(source, statement) or ast.unparse(statement)
        aliases.update((name, declaration) for name in public_targets)


def _referenced_type_alias(value: ast.expr, path: Path) -> bool:
    return isinstance(value, ast.Name) and module_symbol_is_type(path, value.id)
