"""Clear a registry-coded enum member only when the registry actually declares its code."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from cadrumo.core.toml import TomlDecodeError, parse_toml
from dev._paths import UTF_8
from dev.quality.source_import_analysis import resolve_relative_import
from dev.quality.unread_inputs import format_unread_notice

from .unreachable_models import ShippedModule
from .unreachable_references import _data_paths
from .unreachable_tree import ShippedTreeSpec

CODED_ENUM_BASE = "RegistryCodedEnum"
CODE_SOURCE_METHOD = "_form_code_source"

#: ``fact_id -> {entry key}``: the codes each mapping fact declares.
DeclaredCodes = Mapping[str, frozenset[str]]
#: ``(module, class name) -> (fact_id, key prefix)`` read from ``_form_code_source``.
CodeSources = Mapping[tuple[str, str], tuple[str, str]]


def declared_form_codes(spec: ShippedTreeSpec) -> DeclaredCodes:
    """Read every mapping fact's entry keys from the shipped declarations, live.

    Only a fact's own ``fact_id`` and its mapping ``entries`` keys count, so a
    member is cleared by a declaration that names its code and never by a word
    that merely appears in the payload.
    """
    declared: dict[str, set[str]] = {}
    unread: list[str] = []
    for path in _data_paths(spec):
        if path.suffix != ".toml":
            continue
        try:
            text = path.read_text(encoding=UTF_8)
            if "fact_id" not in text or "entries" not in text:
                continue
            parsed = parse_toml(text)
        except (OSError, UnicodeDecodeError, TomlDecodeError) as error:
            unread.append(f"{path}: {type(error).__name__}: {error}")
            continue
        fact = parsed.get("fact")
        if isinstance(fact, dict) and isinstance(fact.get("fact_id"), str):
            declared.setdefault(fact["fact_id"], set()).update(_entry_keys(fact))
    if unread:
        raise OSError(
            format_unread_notice("unreachable-code form-code declarations", "coverage is unproven", unread).rstrip()
        )
    return {fact_id: frozenset(keys) for fact_id, keys in declared.items()}


def _entry_keys(fact: dict[str, object]) -> set[str]:
    keys: set[str] = set()
    variants = fact.get("variants")
    for variant in variants if isinstance(variants, list) else ():
        payload = variant.get("payload") if isinstance(variant, dict) else None
        entries = payload.get("entries") if isinstance(payload, dict) else None
        for entry in entries if isinstance(entries, list) else ():
            if isinstance(entry, dict) and isinstance(entry.get("key"), str):
                keys.add(entry["key"])
    return keys


def coded_enum_sources(modules: Mapping[str, ShippedModule]) -> CodeSources:
    """Find each registry-coded enum and the fact and prefix its ``_form_code_source`` names."""
    sources: dict[tuple[str, str], tuple[str, str]] = {}
    for name, module in modules.items():
        for node in module.tree.body:
            if isinstance(node, ast.ClassDef) and _inherits_coded_enum(node):
                source = _declared_source(node, module, modules)
                if source is not None:
                    sources[(name, node.name)] = source
    return sources


def _inherits_coded_enum(node: ast.ClassDef) -> bool:
    return any(
        (isinstance(base, ast.Name) and base.id == CODED_ENUM_BASE)
        or (isinstance(base, ast.Attribute) and base.attr == CODED_ENUM_BASE)
        for base in node.bases
    )


def _declared_source(
    node: ast.ClassDef, module: ShippedModule, modules: Mapping[str, ShippedModule]
) -> tuple[str, str] | None:
    """Read ``return <fact id>, "<prefix>"`` from the class's own source method."""
    method = next(
        (item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == CODE_SOURCE_METHOD),
        None,
    )
    if method is None:
        return None
    returns = [inner.value for inner in ast.walk(method) if isinstance(inner, ast.Return)]
    match returns:
        case [ast.Tuple(elts=[fact_node, prefix_node])]:
            fact_id = _string_value(fact_node, module, modules)
            prefix = _string_value(prefix_node, module, modules)
            return (fact_id, prefix) if fact_id and prefix else None
        case _:
            return None


def _string_value(node: ast.expr, module: ShippedModule, modules: Mapping[str, ShippedModule]) -> str:
    """Resolve a literal, or a module constant, locally or one import away."""
    match node:
        case ast.Constant(value=str() as text):
            return text
        case ast.Name(id=name):
            return _named_string(name, module, modules)
        case _:
            return ""


def _named_string(name: str, module: ShippedModule, modules: Mapping[str, ShippedModule]) -> str:
    local = _module_constant(module, name)
    if local:
        return local
    for statement in module.tree.body:
        if not isinstance(statement, ast.ImportFrom):
            continue
        for alias in statement.names:
            if (alias.asname or alias.name) != name:
                continue
            base = resolve_relative_import(module.name, module.is_package, statement.level, statement.module)
            target = modules.get(base) if base is not None else None
            return _module_constant(target, alias.name) if target is not None else ""
    return ""


def _assignment_parts(statement: ast.stmt) -> tuple[list[ast.Name], ast.expr | None] | None:
    """Return the simple names a plain or annotated assignment binds, with its value."""
    match statement:
        case ast.Assign(targets=targets, value=value):
            return [target for target in targets if isinstance(target, ast.Name)], value
        case ast.AnnAssign(target=ast.Name() as target, value=value):
            return [target], value
        case _:
            return None


def _module_constant(module: ShippedModule, name: str) -> str:
    for statement in module.tree.body:
        parts = _assignment_parts(statement)
        if parts is None:
            continue
        targets, value = parts
        match value:
            case ast.Constant(value=str() as text) if any(target.id == name for target in targets):
                return text
    return ""


def member_code_is_declared(
    module: str,
    owner: str,
    value: str,
    sources: CodeSources,
    declared: DeclaredCodes,
) -> bool:
    """Whether ``owner`` is a registry-coded enum whose fact declares ``<prefix>.<value>``."""
    source = sources.get((module, owner))
    if source is None or not value:
        return False
    fact_id, prefix = source
    return f"{prefix}.{value}" in declared.get(fact_id, frozenset())
