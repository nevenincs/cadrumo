"""Structural contract for ledger notices and their canonical actions."""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.entrypoints.cli import (
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
    _ledger_llm_cli,
    _ledger_payloads,
    _ledger_ratios_cli,
    _ledger_read_cli,
    _ledger_review_cli,
    _ledger_rules_cli,
    _ledger_support,
)
from cadrumo.entrypoints.cli import ledger_lifecycle_cli as _ledger_lifecycle_cli

from ..manager import LocaleManager, LocaleNode

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
    _ledger_ratios_cli,
    _ledger_read_cli,
    _ledger_review_cli,
    _ledger_rules_cli,
    _ledger_support,
)

_COMMAND_PROSE = re.compile(r"(?i)\b(?:aeat\s+)?app\s+ledger\b")
_PACKAGE_ROOT = Path(inspect.getfile(_ledger)).parents[2]
# ``_PACKAGE_ROOT`` already addresses ``src/cadrumo``; re-appending it doubled
# the path, so every catalogue read here resolved to a file that cannot exist.
_LOCALES_DIR = _PACKAGE_ROOT / "locales"
_REGISTERED_LEDGER_LOCALE_KEYS: set[str] = set()
"""Catalogue leaves consumed somewhere the ``cli.ledger.`` constant scan cannot see.

Empty today: every surviving ledger leaf is named by a literal in the scanned
package. An entry here admits a catalogue key the scan would otherwise report
as unconsumed, so it must state why the key is invisible to the walk."""
_TYPED_LEDGER_ERROR_NAMES = {
    "ConfirmationBlockedError",
    "InvoiceValidationError",
    "LLMConsentError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "TransactionIdPrefixError",
    "TransactionValidationError",
}


def _message_expressions(tree: ast.Module, expression: ast.expr) -> Iterator[ast.expr]:
    """Resolve module-bound values and local helper returns used as notice prose."""
    assignments: dict[str, list[ast.expr]] = {}
    returns: dict[str, list[ast.expr]] = {}
    for node in ast.walk(tree):
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


def _caught_names(handler: ast.ExceptHandler) -> set[str]:
    """Return names in an exception handler's optional type expression."""
    if handler.type is None:
        return set()
    return {item.id for item in ast.walk(handler.type) if isinstance(item, ast.Name)}


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


#: Floors for the two pattern-matched corpora below. Live: seven payload
#: modules and twenty-six ledger modules, against 221 .py files in the same
#: directory. Floors, not pinned counts.
_MINIMUM_PAYLOAD_MODULES = 3
_MINIMUM_LEDGER_MODULES = 10


def test_ledger_payloads_do_not_redeclare_notice_or_recovery_prose() -> None:
    """Advisories have one typed envelope home, never bespoke payload strings."""
    failures: list[str] = []
    payload_directory = Path(inspect.getfile(_ledger_payloads)).parent
    forbidden_suffixes = ("_notice", "_hint", "_suggestion", "_recovery")
    payload_modules = tuple(scan_directory(payload_directory, pattern="_ledger*payload*.py"))

    # The corpus is a GLOB, and the pattern pins a leading underscore. This
    # repository is actively promoting public symbols out of underscore
    # modules, so a rename lands the file one character outside the pattern,
    # the walk returns nothing, and an empty failure list reads as compliance.
    assert len(payload_modules) >= _MINIMUM_PAYLOAD_MODULES, (
        f"only {len(payload_modules)} ledger payload module(s) matched; below this the walk "
        "has stopped finding its subject and an empty failure list proves nothing"
    )

    for path in payload_modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id.endswith(forbidden_suffixes):
                    failures.append(f"{path.name}:{node.lineno}:{node.target.id}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    if argument.arg.endswith(forbidden_suffixes):
                        failures.append(f"{path.name}:{argument.lineno}:{argument.arg}")
    assert failures == []


def test_ledger_import_ux_has_no_rendered_message_or_forced_locale_assertions() -> None:
    """Import behavior tests bind machine contracts, not one rendered catalogue."""
    path = Path(inspect.getfile(_ledger_import_cli)).parent / "tests" / "test_ledger_import_ux.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"lower", "casefold"}
        ):
            failures.append(f"{path.name}:{node.lineno}: case-folded presentation assertion")
        if isinstance(node, ast.Compare):
            expressions = (node.left, *node.comparators)
            has_output = any(
                isinstance(expression, ast.Attribute) and expression.attr == "output" for expression in expressions
            )
            has_literal = any(
                isinstance(candidate, ast.Constant) and isinstance(candidate.value, str)
                for expression in expressions
                for candidate in ast.walk(expression)
            )
            if has_output and has_literal:
                failures.append(f"{path.name}:{node.lineno}: rendered literal assertion")
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [item.value for item in node.elts if isinstance(item, ast.Constant)]
            if "--language" in values and "en" in values:
                failures.append(f"{path.name}:{node.lineno}: forced English locale")
    assert failures == []


def test_ledger_locale_values_do_not_redeclare_command_guidance() -> None:
    """Localized ledger facts cannot carry executable command identity."""
    manager = LocaleManager(_PACKAGE_ROOT, _LOCALES_DIR)
    failures: list[str] = []
    for locale in ("ca", "en", "es", "hu"):
        catalogue = manager.load_locale(_LOCALES_DIR / locale)
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


def test_evidence_pull_all_does_not_flatten_typed_storage_errors() -> None:
    """The shared boundary, not the ledger callback, projects storage refusals."""
    tree = ast.parse(inspect.getsource(_ledger_lifecycle_cli))
    caught_names = {
        name
        for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler))
        for name in _caught_names(handler)
    }
    assert "OutboundStorageError" not in caught_names


def test_every_ledger_translation_is_catalogue_owned_without_a_runtime_fallback() -> None:
    """Every ledger translation resolves from the authored locale catalogues."""
    ledger_directory = Path(inspect.getfile(_ledger)).parent
    failures: list[str] = []
    ledger_modules = tuple(scan_directory(ledger_directory, pattern="_ledger*.py"))

    assert len(ledger_modules) >= _MINIMUM_LEDGER_MODULES, (
        f"only {len(ledger_modules)} ledger module(s) matched the pattern; below this the "
        "walk has stopped finding its subject and an empty failure list proves nothing"
    )

    for path in ledger_modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "tr":
                continue
            if any(keyword.arg == "default" for keyword in call.keywords):
                failures.append(f"{path.name}:{call.lineno}")
    assert failures == []


def test_translation_helpers_do_not_reintroduce_presentation_defaults() -> None:
    """A translation helper cannot hide fallback prose from the direct ``tr`` gate."""
    failures: list[str] = []
    for module in _LEDGER_NOTICE_MODULES:
        tree = ast.parse(inspect.getsource(module))
        failures.extend(
            f"{module.__name__}:{call.lineno}"
            for call in ast.walk(tree)
            if isinstance(call, ast.Call) and any(keyword.arg == "default" for keyword in call.keywords)
        )
    assert failures == []


def test_typed_ledger_errors_are_not_flattened_by_local_catches() -> None:
    """Typed exception identity and its verdict must reach the shared boundary."""
    failures: list[str] = []
    for module in _LEDGER_NOTICE_MODULES:
        tree = ast.parse(inspect.getsource(module))
        for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)):
            caught = _caught_names(handler)
            if not caught.intersection(_TYPED_LEDGER_ERROR_NAMES):
                continue
            for call in (node for node in ast.walk(handler) if isinstance(node, ast.Call)):
                if isinstance(call.func, ast.Name) and call.func.id == "_bad":
                    failures.append(f"{module.__name__}:{call.lineno}: typed error converted to BadParameter")
                if (
                    handler.name is not None
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "str"
                    and call.args
                    and isinstance(call.args[0], ast.Name)
                    and call.args[0].id == handler.name
                ):
                    failures.append(f"{module.__name__}:{call.lineno}: typed error converted to text")
    assert failures == []


def test_ledger_bad_parameters_do_not_embed_caught_exception_text() -> None:
    """Raw exception prose cannot become a CLI error message or context field."""
    failures: list[str] = []
    for module in _LEDGER_NOTICE_MODULES:
        tree = ast.parse(inspect.getsource(module))
        for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)):
            if handler.name is None:
                continue
            for call in (node for node in ast.walk(handler) if isinstance(node, ast.Call)):
                if not isinstance(call.func, ast.Name) or call.func.id != "_bad":
                    continue
                if any(
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "str"
                    and child.args
                    and isinstance(child.args[0], ast.Name)
                    and child.args[0].id == handler.name
                    for child in ast.walk(call)
                ):
                    failures.append(f"{module.__name__}:{call.lineno}")
    assert failures == []


def test_ledger_import_does_not_aggregate_typed_refusals_into_prose() -> None:
    """Per-file typed failures cannot be reduced to refusal strings or one `_bad`."""
    tree = ast.parse(inspect.getsource(_ledger_import_cli))
    forbidden_names = {"resolve_error_message", "_all_files_refused"}
    observed_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert observed_names.isdisjoint(forbidden_names)
    for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)):
        caught = _caught_names(handler)
        assert "CadrumoError" not in caught


def test_ledger_locale_key_sets_match_source_and_each_other() -> None:
    """Ledger catalogue leaves are complete, symmetric, and consumed by source."""
    manager = LocaleManager(_PACKAGE_ROOT, _LOCALES_DIR)
    source_keys: set[str] = set(_REGISTERED_LEDGER_LOCALE_KEYS)
    for path in scan_directory(_PACKAGE_ROOT, pattern="*.py", recursive=True):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        source_keys.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("cli.ledger.")
        )
    key_sets = {
        locale: {
            key
            for key in manager.get_yaml_keys(manager.load_locale(_LOCALES_DIR / locale))
            if key.startswith("cli.ledger.")
        }
        for locale in ("ca", "en", "es", "hu")
    }
    canonical = key_sets["en"]
    assert {locale: sorted(keys ^ canonical) for locale, keys in key_sets.items()} == {
        "ca": [],
        "en": [],
        "es": [],
        "hu": [],
    }
    assert sorted(canonical - source_keys) == []
