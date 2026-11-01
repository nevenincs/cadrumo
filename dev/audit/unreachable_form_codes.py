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
    for statement in node.body:
        if not (isinstance(statement, ast.FunctionDef) and statement.name == CODE_SOURCE_METHOD):
            continue
        returns = [inner.value for inner in ast.walk(statement) if isinstance(inner, ast.Return)]
        if len(returns) != 1 or not isinstance(returns[0], ast.Tuple) or len(returns[0].elts) != 2:
            return None
        fact_node, prefix_node = returns[0].elts
        fact_id = _string_value(fact_node, module, modules)
        prefix = _string_value(prefix_node, module, modules)
        return (fact_id, prefix) if fact_id and prefix else None
    return None


def _string_value(node: ast.expr, module: ShippedModule, modules: Mapping[str, ShippedModule]) -> str:
    """Resolve a literal, or a module constant, locally or one import away."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else ""
    if not isinstance(node, ast.Name):
        return ""
    local = _module_constant(module, node.id)
    if local:
        return local
    for statement in module.tree.body:
        if not isinstance(statement, ast.ImportFrom):
            continue
        for alias in statement.names:
            if (alias.asname or alias.name) != node.id:
                continue
            base = resolve_relative_import(module.name, module.is_package, statement.level, statement.module)
            target = modules.get(base) if base is not None else None
            return _module_constant(target, alias.name) if target is not None else ""
    return ""


def _module_constant(module: ShippedModule, name: str) -> str:
    for statement in module.tree.body:
        if isinstance(statement, ast.Assign):
            targets = [t for t in statement.targets if isinstance(t, ast.Name)]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            targets, value = [statement.target], statement.value
        else:
            continue
        if any(t.id == name for t in targets) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
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
