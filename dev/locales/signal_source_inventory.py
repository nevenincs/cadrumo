"""Source inventory for the authoritative locale audit."""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from dev._paths import UTF_8
from dev.first_party_source import is_test_source

from .manager import (
    LocaleManager,
)
from .signal_syntax import DOTTED_KEY_RE


def declare_dynamic_translation_keys(
    resolved_dynamic_keys: tuple[str, ...], declarations: dict[str, list[dict[str, object]]]
) -> None:
    """Declare dynamic translation keys."""
    for key in resolved_dynamic_keys:
        if DOTTED_KEY_RE.fullmatch(key):
            declarations[key].append(
                {
                    "kind": "dynamic_resolved",
                    "location": "f-string-registry",
                    "placeholders": [],
                    "semantic_signature": None,
                }
            )


def conflicting_translation_declarations(
    declarations: dict[str, list[dict[str, object]]], conflicting_duplicates: list[dict[str, object]]
) -> None:
    """Conflicting translation declarations."""
    for key, key_declarations in sorted(declarations.items()):
        signatures = {
            cast(tuple[str, ...], declaration["semantic_signature"])
            for declaration in key_declarations
            if declaration["semantic_signature"] is not None
        }
        if len(signatures) < 2:
            continue
        conflicting_duplicates.append(
            {
                "classification": "blocking",
                "kind": "conflicting_duplicate_translation_key",
                "key": key,
                "declarations": [
                    {name: value for name, value in declaration.items() if name != "semantic_signature"}
                    for declaration in key_declarations
                ],
                "next_action": "align duplicate translation-key placeholder declarations",
            }
        )


def collect_source_inventory(
    manager: LocaleManager,
    *,
    dynamic_resolved_keys: Iterable[str] = (),
) -> tuple[dict[str, int], list[dict[str, object]]]:
    """Inventory production translation calls and their concrete key values.

    Literal calls are observed directly from the source tree.  Bounded dynamic
    calls are supplied by the f-string registry as concrete values, because the
    AST scanner can only see their namespace marker.  The occurrence counters
    intentionally retain reuse while the unique counter is computed from a set;
    their difference is therefore an auditable duplicate-occurrence delta.
    """
    counts = Counter[str]()
    literal_keys = Counter[str]()
    key_occurrences: list[str] = []
    declarations: dict[str, list[dict[str, object]]] = defaultdict(list)
    findings: list[dict[str, object]] = []
    for root in (manager.src_dir, *manager.extra_src_dirs):
        for path in sorted(root.rglob("*.py")) if root.is_dir() else ():
            inventory_translation_source(path, root, counts, literal_keys, key_occurrences, declarations, findings)
    resolved_dynamic_keys = tuple(key for key in dynamic_resolved_keys if DOTTED_KEY_RE.fullmatch(key))
    key_occurrences.extend(resolved_dynamic_keys)
    declare_dynamic_translation_keys(resolved_dynamic_keys, declarations)
    conflicting_duplicates: list[dict[str, object]] = []
    conflicting_translation_declarations(declarations, conflicting_duplicates)
    findings.extend(conflicting_duplicates)
    unique_keys = set(key_occurrences)
    duplicate_occurrences = len(key_occurrences) - len(unique_keys)
    return {
        "production_occurrences": counts["tr_calls"],
        "tr_calls": counts["tr_calls"],
        "literal_tr_calls": counts["literal_tr_calls"],
        "raw_literal_key_occurrences": counts["literal_tr_calls"],
        "literal_tr_keys_unique": len(literal_keys),
        "literal_tr_reuse_occurrences": sum(count - 1 for count in literal_keys.values()),
        "literal_tr_keys_reused": sum(1 for count in literal_keys.values() if count > 1),
        "dynamic_tr_calls": counts["dynamic_tr_calls"],
        "dynamic_resolved_key_occurrences": len(resolved_dynamic_keys),
        "dynamic_resolved_localization_key_occurrences": len(resolved_dynamic_keys),
        "raw_localization_key_occurrences": len(key_occurrences),
        "unique_dot_keys": len(unique_keys),
        "duplicate_key_occurrence_delta": duplicate_occurrences,
        "conflicting_duplicate_declarations": len(conflicting_duplicates),
        "invalid_tr_calls": counts["invalid_tr_calls"],
        "naked_presentation_sites": counts["naked_presentation_sites"],
        "unread_or_invalid_sources": counts["unread_or_invalid_sources"],
    }, findings


def translation_call_names(tree: ast.Module) -> set[str]:
    """Return names imported from the canonical runtime translation module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not (node.module or "").endswith("i18n.render"):
            continue
        for alias in node.names:
            if alias.name == "tr":
                names.add(alias.asname or alias.name)
    return names


def is_translation_call(node: ast.expr, translation_names: set[str]) -> bool:
    """Recognize a canonical imported translation call or qualified translation member."""
    if isinstance(node, ast.Name):
        return node.id in translation_names
    return isinstance(node, ast.Attribute) and node.attr == "tr"


def source_finding(kind: str, path: Path, line: int, detail: str) -> dict[str, object]:
    """Describe a malformed or unreadable production translation source site."""
    return {
        "classification": "blocking",
        "kind": kind,
        "location": f"{path}:{line}" if line else str(path),
        "detail": detail,
        "next_action": "canonicalize production presentation declaration",
    }


def inventory_translation_source(
    path: Path,
    root: Path,
    counts: Counter[str],
    literal_keys: Counter[str],
    key_occurrences: list[str],
    declarations: dict[str, list[dict[str, object]]],
    findings: list[dict[str, object]],
) -> None:
    """Inventory translation source."""
    if is_test_source(path, root=root):
        return
    try:
        tree = ast.parse(path.read_text(encoding=UTF_8), filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        counts["unread_or_invalid_sources"] += 1
        findings.append(source_finding("source_unreadable", path, 0, type(exc).__name__))
        return
    translation_names = translation_call_names(tree)
    for node in ast.walk(tree):
        inventory_translation_node(
            node, translation_names, path, counts, literal_keys, key_occurrences, declarations, findings
        )


def inventory_translation_node(
    node: ast.AST,
    translation_names: set[str],
    path: Path,
    counts: Counter[str],
    literal_keys: Counter[str],
    key_occurrences: list[str],
    declarations: dict[str, list[dict[str, object]]],
    findings: list[dict[str, object]],
) -> None:
    """Inventory translation node."""
    if isinstance(node, ast.Call) and is_translation_call(node.func, translation_names):
        counts["tr_calls"] += 1
        if not node.args:
            counts["invalid_tr_calls"] += 1
            findings.append(source_finding("invalid_tr_call", path, node.lineno, "missing key argument"))
        elif isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            declare_literal_translation_key(
                node, node.args[0].value, counts, literal_keys, key_occurrences, declarations, findings, path
            )
        else:
            counts["dynamic_tr_calls"] += 1
        for keyword in node.keywords:
            if keyword.arg != "default":
                continue
            value = keyword.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                counts["naked_presentation_sites"] += 1
                findings.append(source_finding("naked_presentation_text", path, node.lineno, value.value))


def declare_literal_translation_key(
    node: ast.Call,
    key: str,
    counts: Counter[str],
    literal_keys: Counter[str],
    key_occurrences: list[str],
    declarations: dict[str, list[dict[str, object]]],
    findings: list[dict[str, object]],
    path: Path,
) -> None:
    """Declare literal translation key."""
    if DOTTED_KEY_RE.fullmatch(key):
        counts["literal_tr_calls"] += 1
        literal_keys[key] += 1
        key_occurrences.append(key)
        placeholders = tuple(
            sorted(
                keyword.arg
                for keyword in node.keywords
                if keyword.arg not in {"locale", "default"} and keyword.arg is not None
            )
        )
        declarations[key].append(
            {
                "kind": "literal",
                "location": f"{path}:{node.lineno}",
                "placeholders": list(placeholders),
                "semantic_signature": placeholders,
            }
        )
    else:
        counts["invalid_tr_calls"] += 1
        findings.append(source_finding("invalid_tr_call", path, node.lineno, "invalid dotted key"))
