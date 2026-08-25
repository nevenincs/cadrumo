"""Fixed-point contract for configuration guidance and localization."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.i18n import tr
from cadrumo.entrypoints.cli._config.tests._isolated_storage_fixture import config_check_backend
from cadrumo.tests.cli_runner import invoke_cached_cli, semantic_cli_text

from ..._paths import REPO_ROOT
from .. import LocaleManager

__all__ = ["config_check_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PACKAGE_ROOT = REPO_ROOT / "src" / "cadrumo"
_CONFIG_ROOT = _PACKAGE_ROOT / "entrypoints" / "cli" / "_config"
_LOCALES_ROOT = _PACKAGE_ROOT / "locales"
_COMMAND = re.compile(r"\baeat\s+(?:config|app)\b", re.IGNORECASE)
_CONTEXT_FLATTENERS = frozenset({"str", "resolve_error_message", "_resolve_error_message"})
_ERROR_PARAMETER_NAMES = frozenset({"error", "exc", "exception", "refusal"})
_CONFIG_MODULE_NAMES = frozenset(
    {
        "__init__.py",
        "_apoderado.py",
        "_archive_cli.py",
        "_auth.py",
        "_auth_command_specs.py",
        "_auth_diagnostics.py",
        "_bucket_history.py",
        "_capabilities_cli.py",
        "_capabilities_payloads.py",
        "_censo_file.py",
        "_censo_payloads.py",
        "_censo_review_cli.py",
        "_certificate.py",
        "_check_cli.py",
        "_check_command_specs.py",
        "_check_hardware_rows.py",
        "_check_payloads.py",
        "_collab.py",
        "_collab_command_specs.py",
        "_collab_payloads.py",
        "_command_specs.py",
        "_complete_setup_cli.py",
        "_complete_setup_payloads.py",
        "_custody.py",
        "_custody_command_specs.py",
        "_descendiente.py",
        "_errors.py",
        "_google.py",
        "_google_command_specs.py",
        "_google_credential_source_cli.py",
        "_google_credential_source_payloads.py",
        "_google_errors.py",
        "_google_folder.py",
        "_google_folder_payloads.py",
        "_google_payloads.py",
        "_google_sync_calc.py",
        "_manager_dispatch.py",
        "_manager_frontend.py",
        "_passphrase.py",
        "_profile_command_specs.py",
        "_profile_delete.py",
        "_profile_inspect.py",
        "_profile_inventory_specs.py",
        "_profile_list_cli.py",
        "_profile_repeatable_row.py",
        "_profile_readiness.py",
        "_profile_status_cli.py",
        "_profile_support.py",
        "_provision_cli.py",
        "_provision_command_specs.py",
        "_provision_payloads.py",
        "_repair_cli.py",
        "_repair_command_specs.py",
        "_repair_profile.py",
        "_reset_cli.py",
        "_reset_command_specs.py",
        "_restore_cli.py",
        "_root_cli.py",
        "_scripted_registration.py",
        "_secure_input.py",
        "_spec_policies.py",
        "_status_rendering.py",
        "_storage_cli.py",
        "_storage_command_specs.py",
        "_storage_payloads.py",
    },
)


def _production_modules() -> tuple[Path, ...]:
    discovered = {path.name for path in scan_directory(_CONFIG_ROOT, pattern="*.py")}
    assert discovered == _CONFIG_MODULE_NAMES, (
        "The S89 config action audit has an incomplete or stale source scope. "
        f"missing={sorted(_CONFIG_MODULE_NAMES - discovered)} "
        f"unexpected={sorted(discovered - _CONFIG_MODULE_NAMES)}"
    )
    return tuple(_CONFIG_ROOT / name for name in sorted(_CONFIG_MODULE_NAMES))


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_docstring(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> bool:
    expression = parents.get(node)
    owner = parents.get(expression) if isinstance(expression, ast.Expr) else None
    return isinstance(expression, ast.Expr) and isinstance(owner, (ast.Module, ast.FunctionDef, ast.ClassDef))


def _call_name(node: ast.expr) -> str:
    return node.id if isinstance(node, ast.Name) else ""


def _assignment_names(node: ast.Assign | ast.AnnAssign | ast.NamedExpr) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return {target.id for target in targets if isinstance(target, ast.Name)}


def _assignment_value(node: ast.Assign | ast.AnnAssign | ast.NamedExpr) -> ast.expr | None:
    return node.value


def _exception_names(tree: ast.AST) -> set[str]:
    names = {
        handler.name
        for handler in ast.walk(tree)
        if isinstance(handler, ast.ExceptHandler) and isinstance(handler.name, str)
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names.update(
            argument.arg
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            if argument.arg in _ERROR_PARAMETER_NAMES
        )
        if node.args.vararg is not None and node.args.vararg.arg in _ERROR_PARAMETER_NAMES:
            names.add(node.args.vararg.arg)
        if node.args.kwarg is not None and node.args.kwarg.arg in _ERROR_PARAMETER_NAMES:
            names.add(node.args.kwarg.arg)
    return names


def _is_exception_flattening(
    node: ast.AST | None,
    *,
    exception_names: set[str],
    flattened_names: set[str],
) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id in flattened_names
    if not isinstance(node, ast.Call):
        return any(
            _is_exception_flattening(child, exception_names=exception_names, flattened_names=flattened_names)
            for child in ast.iter_child_nodes(node)
        )
    name = _call_name(node.func)
    if name in _CONTEXT_FLATTENERS - {"str"}:
        return True
    if name == "str" and any(
        isinstance(argument, ast.Name) and argument.id in exception_names for argument in node.args
    ):
        return True
    return any(
        _is_exception_flattening(child, exception_names=exception_names, flattened_names=flattened_names)
        for child in ast.iter_child_nodes(node)
    )


def _flattened_context_failures(path: Path, tree: ast.AST) -> list[str]:
    exception_names = _exception_names(tree)
    flattened_names: set[str] = set()
    assignments = sorted(
        (node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))),
        key=lambda node: (node.lineno, node.col_offset),
    )
    changed = True
    while changed:
        changed = False
        for assignment in assignments:
            if not _is_exception_flattening(
                _assignment_value(assignment),
                exception_names=exception_names,
                flattened_names=flattened_names,
            ):
                continue
            new_names = _assignment_names(assignment) - flattened_names
            flattened_names.update(new_names)
            changed = changed or bool(new_names)

    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "context":
                continue
            if _is_exception_flattening(
                keyword.value,
                exception_names=exception_names,
                flattened_names=flattened_names,
            ):
                failures.append(f"{path.name}:{node.lineno}: flattened exception text in context")
    return failures


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


def test_config_error_contexts_preserve_typed_exception_information() -> None:
    failures: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        failures.extend(_flattened_context_failures(path, tree))
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
            for key in manager.get_yaml_keys(manager.load_locale(_LOCALES_ROOT / locale))
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


@pytest.mark.parametrize("locale", ("ca", "en", "es", "hu"))
def test_config_check_json_and_text_resolve_the_same_localized_action_surface(
    config_check_backend: None,
    locale: str,
) -> None:
    """The live check verb keeps JSON data locale-neutral and text catalogue-derived."""
    json_result = invoke_cached_cli(["--format", "json", "--language", locale, "config", "check"])
    text_result = invoke_cached_cli(["--language", locale, "config", "check"])

    assert json_result.exit_code in (0, 2), json_result.output
    assert text_result.exit_code == json_result.exit_code, text_result.output
    document = json.loads(json_result.output)
    result = document["result"]
    assert document["command"] == "config.check"
    assert set(result) == {"profile_id", "ok", "capabilities", "dependencies", "preflight", "issues"}
    assert all(
        set(dependency) == {"service", "available", "facts", "precondition_action"}
        for dependency in result["dependencies"]
    )
    assert all(
        set(preflight)
        == {
            "check",
            "healthy",
            "severity",
            "facts",
            "precondition_action",
        }
        for preflight in result["preflight"]
    )
    serialized = json.dumps(document, ensure_ascii=False, sort_keys=True)
    assert "next_action" not in serialized

    text = semantic_cli_text(text_result.output)
    assert f"{tr('cli.config.check.profile_label', locale=locale)}\t" in text
    assert f"{tr('cli.config.check.preflight_label', locale=locale)}\t" in text
