"""Regression tests for audited CLI onboarding, help, and state boundaries."""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from pathlib import Path

import click
import pytest
from click.testing import Result

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.tests.cli_runner import aeat_click_command, invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_LEAK_FRAGMENTS = (
    "Envelope[",
    "ValidationError",
    "TypeError",
    "Traceback",
    "original_exception",
    "INTERNAL_CLI_UNEXPECTED_BOUNDARY",
    "payload.",
    "extra_forbidden",
    "errors.pydantic.dev",
    "Pydantic",
    "pydantic",
)


@pytest.fixture(autouse=True)
def _isolated_cli_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    yield
    dispose_engine()


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


def _combined_output(result: Result) -> str:
    return result.output + (result.stderr or "")


def _assert_no_internal_leak(text: str) -> None:
    leaked = [fragment for fragment in _LEAK_FRAGMENTS if fragment in text]
    assert leaked == []


def test_modelo_bindings_help_uses_accepted_period_examples() -> None:
    result = _invoke(["app", "modelo", "bindings", "list", "--help"])

    assert result.exit_code == 0
    assert "2026Q1" in result.output
    assert "2026-01" in result.output
    assert "Q1, 2026-01" not in result.output


def test_overview_calendar_for_general_iva_includes_modelo_303() -> None:
    init = _invoke(
        [
            "config",
            "init",
            "--quiet",
            "--profile",
            "operator",
            "--tax-id",
            "12345678Z",
            "--activity",
            "software development",
            "--iva-regime",
            "GENERAL",
        ]
    )
    assert init.exit_code == 0

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "status",
            "--calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-12-31",
            "--allow-incomplete",
        ]
    )

    assert result.exit_code == 0
    _assert_no_internal_leak(_combined_output(result))
    payload = json.loads(result.output)
    modelos = {entry["modelo"] for entry in payload["calendar"]["entries"]}
    assert "303" in modelos


def test_every_visible_help_surface_is_clean() -> None:
    root = aeat_click_command()
    for path in _visible_command_paths(root):
        result = _invoke([*path, "--help"])
        assert result.exit_code == 0, path
        output = _combined_output(result)
        assert output.strip(), path
        assert "No such option" not in output
        _assert_no_internal_leak(output)
        assert not _contains_raw_translation_key(output), path


def _visible_command_paths(command: click.Command, prefix: tuple[str, ...] = ()) -> tuple[tuple[str, ...], ...]:
    paths = [prefix]
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            if child.hidden:
                continue
            paths.extend(_visible_command_paths(child, (*prefix, name)))
    return tuple(paths)


def _contains_raw_translation_key(output: str) -> bool:
    import re

    return re.search(r"\b(?:cli|wizard)\.[a-zA-Z0-9_.-]+", output) is not None


_TYPER_HELP_SURFACE_CALLABLES = frozenset({"Typer", "Option", "Argument", "command", "add_typer"})


def test_typer_help_sources_are_direct_translations() -> None:
    failures: list[str] = []
    for module in Path("src/aeat").rglob("*.py"):
        if module.name.startswith(("test_", "_test_")):
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        failures.extend(_typer_help_violations(tree, module=module))
    assert failures == []


def _typer_help_violations(tree: ast.AST, *, module: Path) -> tuple[str, ...]:
    """Return every help= value in ``tree`` that is not a direct ``tr("literal")`` call.

    Walks every ``ast.Call`` whose callee resolves to a Typer
    surface (Typer, Option, Argument, command, add_typer), filters
    keyword args to ``help=``, and tests each value against the
    direct-tr-literal predicate. Anything else — an f-string, a
    variable, a ``tr(name)`` with a non-constant arg — becomes a
    failure record so the test's diagnostic lists the offending
    site by ``path:line: source``.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node) not in _TYPER_HELP_SURFACE_CALLABLES:
            continue
        violations.extend(_typer_help_keyword_violations(node, module=module))
    return tuple(violations)


def _typer_help_keyword_violations(node: ast.Call, *, module: Path) -> tuple[str, ...]:
    """Return every ``help=`` keyword on one Typer call whose value is not a direct tr literal."""
    return tuple(
        f"{module}:{node.lineno}: help={ast.unparse(keyword.value)}"
        for keyword in node.keywords
        if keyword.arg == "help" and not _is_direct_tr_literal(keyword.value)
    )


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _is_direct_tr_literal(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "tr"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    )
