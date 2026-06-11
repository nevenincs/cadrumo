"""Regression tests for audited CLI onboarding, help, and state boundaries."""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from pathlib import Path

import click
import pytest
from click.testing import Result

from ....tests.cli_runner import aeat_click_command, invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

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
def _isolated_cli_state(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path):
        yield


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


def _combined_output(result: Result) -> str:
    return result.output + (result.stderr or "")


def _assert_no_internal_leak(text: str) -> None:
    leaked = [fragment for fragment in _LEAK_FRAGMENTS if fragment in text]
    assert leaked == []


def test_modelo_bindings_help_uses_accepted_period_examples() -> None:
    """``bindings list`` help advertises the bare period tokens it
    accepts, consistent with ``work create`` and ``describe``.

    ``bindings list`` composes ``--year`` and ``--period`` separately,
    so its ``--period`` argument is a bare registry token (``0A``,
    ``1T``-``4T``, ``01``-``12``) — never a composed ``YYYY``-prefixed
    string. The help text must show those bare tokens and the censo
    tokens, the same guidance every modelo period surface gives.
    """

    bindings_help = _invoke(["app", "modelo", "bindings", "list", "--help"]).output
    work_help = _invoke(["app", "modelo", "work", "create", "--help"]).output
    describe_help = _invoke(["app", "modelo", "describe", "--help"]).output

    for surface in (bindings_help, work_help, describe_help):
        # Collapse Rich's line wrapping so a token split across two
        # help-panel rows is still matched.
        flat = " ".join(surface.split())
        assert "0A" in flat, surface
        assert "1T-4T" in flat, surface
        assert "01-12" in flat, surface
        # The censo tokens are named (the connector word is locale-
        # dependent, so each token is checked on its own).
        assert "alta" in flat and "modificacion" in flat and "baja" in flat, surface
        # The composed YYYY-prefixed forms are no longer advertised on
        # surfaces that compose --year and --period separately.
        assert "2026Q1" not in flat, surface


class TestOverviewCalendarRequiresProfileCreate:
    """Overview calendar tests that exercise the profile create path.

    Separated from the module-level ``isolated_runtime_profile`` autouse
    fixture because these tests call ``profile create`` and need an empty
    storage root — not one pre-populated with a runtime bucket.
    """

    @pytest.fixture(autouse=True)
    def _isolated_cli_state(self, tmp_path: Path) -> Iterator[None]:
        # Overrides the module-level _isolated_cli_state autouse fixture.
        # Profile create tests need an empty root; isolated_runtime_profile
        # pre-provisions a bucket that breaks NIF uniqueness checks.
        with isolated_profile_storage_root(tmp_path=tmp_path):
            yield

    def test_overview_calendar_for_general_iva_includes_modelo_303(self) -> None:
        init = _invoke(
            [
                "config",
                "profile",
                "create",
                "operator",
                "--quiet",
                "--tax-id",
                "12345678Z",
                "--activity",
                "software development",
                "--iva-regime",
                "GENERAL",
            ],
        )
        assert init.exit_code == 0, init.output

        # Modelo applicability is derived from the taxpayer model — declare
        # an autónomo (natural person with actividad económica) so Modelo
        # 303 is positively applicable rather than reported as incomplete.
        declared = _invoke(
            [
                "config",
                "profile",
                "edit",
                "operator",
                "--quiet",
                "--entity-type",
                "natural_person",
                "--irpf-income-categories",
                "actividad_economica",
            ],
        )
        assert declared.exit_code == 0, declared.output

        result = _invoke(
            [
                "--format",
                "json",
                "app",
                "overview",
                "calendar",
                "--from",
                "2026-01-01",
                "--to",
                "2026-12-31",
                "--allow-incomplete",
            ],
        )

        assert result.exit_code == 0, _combined_output(result)
        _assert_no_internal_leak(_combined_output(result))
        envelope = json.loads(result.output)
        modelos = {entry["modelo"] for entry in envelope["result"]["entries"]}
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
