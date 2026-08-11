"""Structural contract for ledger notices and their canonical actions."""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from dev.locales import LocaleManager, LocaleNode

from .. import (
    _ledger,
    _ledger_business_invoice_cli,
    _ledger_classify_cli,
    _ledger_counterparty_cli,
    _ledger_evidence_batch_cli,
    _ledger_evidence_cli,
    _ledger_evidence_confirm_notices,
    _ledger_evidence_consent_cli,
    _ledger_evidence_review_cli,
    _ledger_import_cli,
    _ledger_lifecycle_cli,
    _ledger_llm_cli,
    _ledger_read_cli,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LEDGER_NOTICE_MODULES: tuple[ModuleType, ...] = (
    _ledger,
    _ledger_business_invoice_cli,
    _ledger_classify_cli,
    _ledger_counterparty_cli,
    _ledger_evidence_batch_cli,
    _ledger_evidence_cli,
    _ledger_evidence_confirm_notices,
    _ledger_evidence_consent_cli,
    _ledger_evidence_review_cli,
    _ledger_import_cli,
    _ledger_lifecycle_cli,
    _ledger_llm_cli,
    _ledger_read_cli,
)

_COMMAND_PROSE = re.compile(r"(?i)\b(?:aeat\s+)?app\s+ledger\b")
_PACKAGE_ROOT = Path(inspect.getfile(_ledger)).parents[2]
_LOCALES_DIR = _PACKAGE_ROOT / "locales"


def _message_expressions(tree: ast.Module, expression: ast.expr) -> Iterator[ast.expr]:
    """Resolve module-bound values and local helper returns used as notice prose."""
    assignments: dict[str, list[ast.expr]] = {}
    returns: dict[str, list[ast.expr]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            assignments.setdefault(node.target.id, []).append(node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            returns[node.name] = [
                item.value for item in ast.walk(node) if isinstance(item, ast.Return) and item.value is not None
            ]

    pending = [expression]
    seen: set[int] = set()
    while pending:
        candidate = pending.pop()
        if id(candidate) in seen:
            continue
        seen.add(id(candidate))
        if isinstance(candidate, ast.Name) and candidate.id in assignments:
            pending.extend(assignments[candidate.id])
            continue
        if isinstance(candidate, ast.Call) and isinstance(candidate.func, ast.Name) and candidate.func.id in returns:
            pending.extend(returns[candidate.func.id])
            continue
        yield candidate


def _iter_locale_leaves(node: LocaleNode, prefix: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for key, child in node.items():
            yield from _iter_locale_leaves(child, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(node, str):
        yield prefix, node


def test_ledger_notices_do_not_redeclare_actions_or_english_fallbacks() -> None:
    """Notice actions come from resolvers; context and prose cannot shadow them."""
    failures: list[str] = []
    for module in _LEDGER_NOTICE_MODULES:
        tree = ast.parse(inspect.getsource(module))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "Notice":
                continue
            keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}
            message = keywords.get("message")
            context = keywords.get("context")
            action = keywords.get("action")
            location = f"{module.__name__}:{call.lineno}"
            if message is not None:
                for resolved_message in _message_expressions(tree, message):
                    if isinstance(resolved_message, ast.Constant) and isinstance(resolved_message.value, str):
                        failures.append(f"{location}: raw notice message")
                    if isinstance(resolved_message, ast.Call) and any(
                        keyword.arg == "default" for keyword in resolved_message.keywords
                    ):
                        failures.append(f"{location}: notice translation has a runtime default")
            if isinstance(context, ast.Dict) and any(
                isinstance(key, ast.Constant) and key.value == "actionability" for key in context.keys
            ):
                failures.append(f"{location}: context redeclares actionability")
            if (
                action is not None
                and not (
                    isinstance(action, ast.Call)
                    and isinstance(action.func, ast.Name)
                    and action.func.id in {"resolve_notice_action", "resolve_cli_precondition_action"}
                )
                and not (isinstance(action, ast.Name) and action.id == "action")
            ):
                failures.append(f"{location}: action bypasses a canonical resolver")
    assert failures == []


def test_ledger_locale_values_do_not_redeclare_command_guidance() -> None:
    """Localized ledger facts cannot carry executable command identity."""
    manager = LocaleManager(_PACKAGE_ROOT, _LOCALES_DIR)
    failures: list[str] = []
    for locale in ("ca", "en", "es", "hu"):
        catalogue = manager.load_locale(_LOCALES_DIR / f"{locale}.yml")
        failures.extend(
            f"{locale}:{key}"
            for key, value in _iter_locale_leaves(catalogue)
            if key.startswith("cli.ledger.") and _COMMAND_PROSE.search(value)
        )
    assert failures == []


def test_ledger_runtime_command_literals_are_provenance_only() -> None:
    """Raw command strings are allowed only as explicit source provenance."""
    failures: list[str] = []
    for module in _LEDGER_NOTICE_MODULES:
        tree = ast.parse(inspect.getsource(module))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for literal in (node for node in ast.walk(tree) if isinstance(node, ast.Constant)):
            if not isinstance(literal.value, str) or not _COMMAND_PROSE.search(literal.value):
                continue
            parent = parents.get(literal)
            if isinstance(parent, ast.keyword) and parent.arg == "source_command":
                continue
            if isinstance(parent, ast.Expr) and isinstance(
                parents.get(parent), (ast.Module, ast.FunctionDef, ast.ClassDef)
            ):
                continue
            failures.append(f"{module.__name__}:{literal.lineno}")
    assert failures == []


def test_pull_folder_does_not_flatten_typed_storage_errors() -> None:
    """The shared boundary, not the ledger callback, projects storage refusals."""
    tree = ast.parse(inspect.getsource(_ledger_lifecycle_cli))
    caught_names = {
        item.id
        for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler))
        if handler.type is not None
        for item in ast.walk(handler.type)
        if isinstance(item, ast.Name)
    }
    assert "OutboundStorageError" not in caught_names


def test_every_ledger_translation_is_catalogue_owned_without_a_runtime_fallback() -> None:
    """Every ledger translation resolves from the authored locale catalogues."""
    ledger_directory = Path(inspect.getfile(_ledger)).parent
    failures: list[str] = []
    for path in sorted(ledger_directory.glob("_ledger*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "tr":
                continue
            if any(keyword.arg == "default" for keyword in call.keywords):
                failures.append(f"{path.name}:{call.lineno}")
    assert failures == []
