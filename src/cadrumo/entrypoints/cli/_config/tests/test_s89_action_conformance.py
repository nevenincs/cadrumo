"""Fixed-point contract for configuration guidance and localization."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from dev.locales import LocaleManager

from .....core.i18n import tr

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CONFIG_ROOT = Path(__file__).parents[1]
_PACKAGE_ROOT = Path(__file__).parents[4]
_LOCALES_ROOT = _PACKAGE_ROOT / "locales"
_COMMAND = re.compile(r"\baeat\s+(?:config|app)\b", re.IGNORECASE)


def _production_modules() -> tuple[Path, ...]:
    modules = tuple(sorted(_CONFIG_ROOT.glob("*.py")))
    assert len(modules) >= 45
    return modules


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_docstring(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    expression = parents.get(node)
    owner = parents.get(expression) if isinstance(expression, ast.Expr) else None
    return isinstance(expression, ast.Expr) and isinstance(owner, (ast.Module, ast.FunctionDef, ast.ClassDef))


def test_config_runtime_has_no_fallback_or_raw_command_guidance() -> None:
    failures: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = _parents(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else ""
                if name in {"tr", "_tr"} and any(keyword.arg == "default" for keyword in node.keywords):
                    failures.append(f"{path.name}:{node.lineno}: translation fallback")
                if name in {"_CliRefusedBoundaryError", "CliRefusedBoundaryError"} and (
                    any(keyword.arg == "message" for keyword in node.keywords)
                    or any(
                        isinstance(argument, ast.Call)
                        and isinstance(argument.func, ast.Name)
                        and argument.func.id in {"str", "resolve_error_message"}
                        for argument in node.args
                    )
                ):
                    failures.append(f"{path.name}:{node.lineno}: flattened refusal message")
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _COMMAND.search(node.value):
                if _is_docstring(node, parents):
                    continue
                parent = parents.get(node)
                if isinstance(parent, ast.keyword) and parent.arg == "source_command":
                    continue
                failures.append(f"{path.name}:{node.lineno}: raw command guidance")
    assert failures == [], "\n".join(failures)


def test_config_notices_use_catalogue_messages_and_canonical_actions() -> None:
    failures: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in {"Notice", "_Notice"}:
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            message = keywords.get("message")
            if isinstance(message, (ast.Constant, ast.JoinedStr)):
                failures.append(f"{path.name}:{node.lineno}: raw notice message")
            action = keywords.get("action")
            if action is not None and not (
                isinstance(action, ast.Call)
                and isinstance(action.func, ast.Name)
                and action.func.id in {"resolve_notice_action", "resolve_cli_precondition_action"}
            ):
                failures.append(f"{path.name}:{node.lineno}: unresolved notice action")
    assert failures == [], "\n".join(failures)


def test_config_locale_keys_are_symmetric_resolved_and_consumed() -> None:
    manager = LocaleManager(_PACKAGE_ROOT, _LOCALES_ROOT)
    source_keys: set[str] = set()
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        source_keys.update(
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"tr", "_tr"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value.startswith("cli.config.")
        )
    key_sets = {
        locale: {
            key
            for key in manager.get_yaml_keys(manager.load_locale(_LOCALES_ROOT / f"{locale}.yml"))
            if key.startswith("cli.config.")
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
    assert sorted(source_keys - canonical) == []
    for locale in ("ca", "en", "es", "hu"):
        for key in source_keys:
            value = tr(key, locale=locale)
            assert isinstance(value, str) and value.strip() and value != key
