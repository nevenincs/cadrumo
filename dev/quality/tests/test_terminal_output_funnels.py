"""Operator-facing terminal writes must pass through terminal-context encoding.

Imported narratives and other untrusted text can carry ESC, CSI/OSC, carriage
return and bidi controls. Shipped code therefore reaches a terminal only through
an argument that is visibly a literal or a ``cadrumo.core.terminal_encoding``
call, or through a named funnel below whose argument is already encoded output
or a machine protocol line on a supervision pipe. Writes through a stream
variable inside a funnel (``target.write``) are the funnels themselves and are
covered by their behaviour tests.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import PurePosixPath

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SHIPPED_PACKAGES = (
    "src/cadrumo",
    "src/cadrumo_client",
    "src/cadrumo_runtime",
    "src/cadrumo_mcp",
    "src/cadrumo_agent_service",
)
_ECHO_MODULES = frozenset({"typer", "_typer", "click"})
_ECHO_FUNCTIONS = frozenset({"echo", "secho"})
_ENCODERS = frozenset({"encode_terminal_text", "encode_terminal_field"})

#: ``(path, enclosing qualname)`` -> why the raw write is safe there.
_FUNNELS: dict[tuple[str, str], str] = {
    ("src/cadrumo/entrypoints/cli/common.py", "_render_and_echo"): "emits render_command_output text",
    ("src/cadrumo/application/wizard/commands.py", "_echo_wizard_text"): "emits render_command_output text",
    ("src/cadrumo_client/commands/custody.py", "_emit_envelope"): "emits render_command_output text",
    ("src/cadrumo_runtime/commands/presentation.py", "emit_envelope"): "emits render_command_output text",
    ("src/cadrumo_runtime/host/caller_owned.py", "CallerOwnedRuntime._announce_ready"): (
        "readiness protocol line to the supervising parent"
    ),
    ("src/cadrumo_runtime/host/session_hold.py", "_emit"): "ASCII-bounded protocol line to the parent",
    ("src/cadrumo_runtime/host/session_hold.py", "_report_failure"): "registered error JSON for the parent log",
    ("src/cadrumo_runtime/host/session_watch.py", "_emit"): "ensure_ascii JSON protocol line",
    ("src/cadrumo_agent_service/main.py", "_publish"): "ensure_ascii JSON protocol line",
}


@dataclass(frozen=True, slots=True)
class _Sink:
    path: str
    qualname: str
    line: int
    encoded: bool


def _sink_kind(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "print"
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr in _ECHO_FUNCTIONS:
        return isinstance(func.value, ast.Name) and func.value.id in _ECHO_MODULES
    if func.attr == "write" and isinstance(func.value, ast.Attribute) and func.value.attr in {"stdout", "stderr"}:
        return isinstance(func.value.value, ast.Name) and func.value.value.id == "sys"
    return False


def _is_encoded(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.Call):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        return name in _ENCODERS
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_encoded(node.left) and _is_encoded(node.right)
    if isinstance(node, ast.JoinedStr):
        return all(
            isinstance(part, ast.Constant) or (isinstance(part, ast.FormattedValue) and _is_encoded(part.value))
            for part in node.values
        )
    return False


def _sinks(source: str, path: str) -> list[_Sink]:
    found: list[_Sink] = []

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = (*scope, node.name)
        if isinstance(node, ast.Call) and _sink_kind(node):
            encoded = not node.args or _is_encoded(node.args[0])
            found.append(_Sink(path, ".".join(scope) or "<module>", node.lineno, encoded))
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(ast.parse(source), ())
    return found


def _shipped_sinks() -> list[_Sink]:
    sinks: list[_Sink] = []
    for relative in repository_files(REPO_ROOT, under=_SHIPPED_PACKAGES):
        parts = PurePosixPath(relative).parts
        if not relative.endswith(".py") or "tests" in parts:
            continue
        sinks.extend(_sinks((REPO_ROOT / relative).read_text(encoding=UTF_8), relative))
    return sinks


def test_shipped_terminal_writes_are_encoded_or_named_funnels() -> None:
    unencoded = [
        f"{sink.path}:{sink.line} ({sink.qualname})"
        for sink in _shipped_sinks()
        if not sink.encoded and (sink.path, sink.qualname) not in _FUNNELS
    ]

    assert not unencoded, "wrap these terminal writes in encode_terminal_text/encode_terminal_field: " + ", ".join(
        unencoded
    )


def test_every_named_funnel_still_writes_to_the_terminal() -> None:
    present = {(sink.path, sink.qualname) for sink in _shipped_sinks()}

    assert not set(_FUNNELS) - present


@pytest.mark.parametrize(
    "statement",
    (
        "typer.echo(description)",
        "typer.echo(line, err=True)",
        "click.secho(text)",
        "print(value)",
        "sys.stderr.write(str(exc) + '\\n')",
        "sys.stdout.write(f'error: {exc}\\n')",
    ),
)
def test_gate_flags_raw_untrusted_writes(statement: str) -> None:
    (sink,) = _sinks(f"def emit():\n    {statement}\n", "fixture.py")

    assert sink.qualname == "emit"
    assert not sink.encoded


@pytest.mark.parametrize(
    "statement",
    (
        "typer.echo()",
        "typer.echo('Aborted.')",
        "typer.echo(encode_terminal_text(text), err=True)",
        "sys.stderr.write(encode_terminal_text(str(exc)) + '\\n')",
        "sys.stderr.write(f'error: {encode_terminal_field(value)}\\n')",
    ),
)
def test_gate_accepts_encoded_or_literal_writes(statement: str) -> None:
    (sink,) = _sinks(f"def emit():\n    {statement}\n", "fixture.py")

    assert sink.encoded


def test_gate_ignores_stream_variable_writes_and_unrelated_echo() -> None:
    source = "def emit(target, logger):\n    target.write(text)\n    logger.echo(text)\n"

    assert _sinks(source, "fixture.py") == []
