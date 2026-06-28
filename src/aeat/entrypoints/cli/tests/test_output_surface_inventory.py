"""Inventory gate for production CLI output surfaces.

The centralized-output-redaction contract makes ``_emit``/``_emit_envelope`` and
``write_stderr`` the owned output boundaries. This test keeps direct output
exceptions explicit so new ``typer.echo``, ``print``, or stream writes do not
silently bypass the redacted renderer.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SRC_ROOT = Path(__file__).resolve().parents[3]

_CLI_ROOT = _SRC_ROOT / "entrypoints" / "cli"
_DIAGNOSTICS_ROOT = _SRC_ROOT / "diagnostics"
_APPLICATION_OUTPUT_ROOTS = (_SRC_ROOT / "application" / "wizard",)

_EXCLUDED_MODULES: set[Path] = set()

_ALLOWED_DIRECT_OUTPUTS = {
    ("entrypoints/cli/__init__.py", "typer.echo"),
    # Auth-preflight diagnostics are emitted already redacted via
    # ``typer.echo(redact_for_cli_output(line), err=True)`` — an audited
    # exception that honours the redaction boundary.
    ("entrypoints/cli/_app_live_auth_preflight.py", "typer.echo"),
    ("entrypoints/cli/_common.py", "typer.echo"),
    ("entrypoints/cli/_errors.py", "write"),
    # Last-resort crash-boundary fallbacks (``# pragma: no cover``) used only
    # when typer/rich rendering is unavailable: the abort marker and the
    # ClickException usage message. They cannot route through the rich path
    # they are the fallback for.
    ("entrypoints/cli/_terminal_errors.py", "write"),
    ("entrypoints/cli/_exit_codes.py", "typer.echo"),
    ("application/wizard/_commands.py", "typer.echo"),
}


@dataclass(frozen=True)
class OutputCall:
    """A direct production output call discovered by the inventory scan."""

    path: Path
    lineno: int
    kind: str
    source: str

    def key(self) -> tuple[str, str]:
        return (self.path.as_posix(), self.kind)

    def render(self) -> str:
        return f"{self.path.as_posix()}:{self.lineno}: {self.kind}: {self.source.strip()}"


def _production_modules() -> tuple[Path, ...]:
    modules: list[Path] = []
    for root in (_CLI_ROOT, _DIAGNOSTICS_ROOT, *_APPLICATION_OUTPUT_ROOTS):
        for path in root.rglob("*.py"):
            relative = path.relative_to(_SRC_ROOT)
            if relative in _EXCLUDED_MODULES:
                continue
            if path.name.startswith("test_") or path.name == "conftest.py":
                continue
            modules.append(path)
    return tuple(sorted(modules))


def _call_kind(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "print":
        return "print"
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id in {"typer", "_typer"} and func.attr == "echo":
            return "typer.echo"
        if func.attr == "print":
            return "print"
        if func.attr == "write":
            return "write"
    return None


def _line_for(path: Path, node: ast.expr | ast.stmt) -> str:
    return path.read_text(encoding="utf-8").splitlines()[node.lineno - 1]


def _direct_output_calls(path: Path) -> tuple[OutputCall, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative = path.relative_to(_SRC_ROOT)
    calls: list[OutputCall] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _call_kind(node)
        if kind is None:
            continue
        calls.append(OutputCall(relative, node.lineno, kind, _line_for(path, node)))
    return tuple(calls)


def test_production_direct_output_surfaces_are_owned() -> None:
    """Every direct output call must be a reviewed exception to the renderer boundary."""

    calls = [call for path in _production_modules() for call in _direct_output_calls(path)]
    unowned = [call.render() for call in calls if call.key() not in _ALLOWED_DIRECT_OUTPUTS]

    assert not unowned, (
        "New direct production CLI output call(s) bypass the centralized "
        "redaction boundary; route through _emit/_emit_envelope/write_stderr "
        "or add an audited exception:\n" + "\n".join(unowned)
    )


def test_plan_owned_direct_outputs_still_exist() -> None:
    """The allow-list must not retain stale entries after output migrations."""

    discovered_keys = {call.key() for path in _production_modules() for call in _direct_output_calls(path)}
    stale = sorted(_ALLOWED_DIRECT_OUTPUTS - discovered_keys)

    assert stale == []


def test_emit_boundaries_are_present_for_success_output() -> None:
    """The success-output choke points must remain in the CLI common module."""

    common = (_CLI_ROOT / "_common.py").read_text(encoding="utf-8")

    assert "def _emit(" in common
    assert "def _emit_envelope(" in common
    assert "render_command_output(" in common
