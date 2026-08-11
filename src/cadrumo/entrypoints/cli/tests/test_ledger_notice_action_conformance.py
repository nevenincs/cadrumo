"""Structural contract for ledger notices and their canonical actions."""

from __future__ import annotations

import ast
import inspect
from types import ModuleType

import pytest

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


def test_ledger_notices_do_not_redeclare_actions_or_english_fallbacks() -> None:
    """Notice actions come from resolvers; context and prose cannot shadow them."""
    failures: list[str] = []
    for module in _LEDGER_NOTICE_MODULES:
        tree = ast.parse(inspect.getsource(module))
        name_bound_messages: dict[str, ast.Call] = {}
        for assignment in (node for node in ast.walk(tree) if isinstance(node, ast.Assign)):
            if (
                len(assignment.targets) == 1
                and isinstance(assignment.targets[0], ast.Name)
                and isinstance(assignment.value, ast.Call)
            ):
                name_bound_messages[assignment.targets[0].id] = assignment.value
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "Notice":
                continue
            keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}
            message = keywords.get("message")
            resolved_message = name_bound_messages.get(message.id) if isinstance(message, ast.Name) else message
            context = keywords.get("context")
            action = keywords.get("action")
            location = f"{module.__name__}:{call.lineno}"
            if isinstance(message, ast.Constant) and isinstance(message.value, str):
                failures.append(f"{location}: raw notice message")
            if isinstance(resolved_message, ast.Call) and any(
                keyword.arg == "default" for keyword in resolved_message.keywords
            ):
                failures.append(f"{location}: notice translation has an English default")
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
