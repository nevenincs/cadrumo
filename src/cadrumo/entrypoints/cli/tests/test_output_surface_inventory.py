"""Inventory gate for production CLI output surfaces.

The centralized-output-redaction contract makes ``emit_envelope`` and
``write_stderr`` the owned output boundaries. This test keeps direct output
exceptions explicit so new ``typer.echo``, ``print``, or stream writes do not
silently bypass the redacted renderer.

The scan covers the CLI, diagnostics, and wizard roots below. The canonical
``entrypoints/tui`` tree is outside it deliberately. The TUI renders a
frame the operator is looking at rather than a stream that can be redirected,
piped, or attached, and it carries its own privacy authority: a fact row's
``masked`` flag, decided from schema sensitivity, substitutes a mask token so
the raw value never reaches a widget. That authority also covers the one
durable artefact the TUI can emit — Textual's built-in ``Screenshot`` system
command, reachable from the default command palette on every app in that
tree, writes an SVG of the screen to the user's downloads directory, and a
masked fact's value does not appear in it while an unmasked one does.

Routing TUI rendering through ``redact_for_cli_output`` would be a regression
rather than a hardening. That policy keys on NIF/NIE shape, not on field
sensitivity, and the profile manager pre-fills an unmasked field's current
value into its edit input — so a redacted ``identity.tax_id`` would put a
``sha256:`` digest in the box, and an operator confirming it would write that
digest into the field. Showing the operator their own tax identifier is also
the status page's purpose: the same value is written in cleartext into the
fichero-BOE they file.

Exemptions are keyed by ``(module, enclosing function, primitive)`` and never by
line number. File granularity is not enough: a module that legitimately owns the
funnel — ``_common.py`` owns ``_render_and_echo`` —
would otherwise blanket-exempt every future emit added anywhere inside it, so a
bypass dropped into a neighbouring function in an already-listed module would
pass silently. Line numbers are rejected for the opposite reason: they move with
every unrelated edit above them, so they decay into noise and get bulk-refreshed
without review. The enclosing function is the smallest unit that is both stable
under reformatting and specific enough to name the reviewed decision.

Every exemption carries a written reason, structurally: the allow-list is a
mapping, so an entry cannot be added without one, and a blank reason fails.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import override

import pytest

from ....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SRC_ROOT = Path(__file__).resolve().parents[3]

_CLI_ROOT = _SRC_ROOT / "entrypoints" / "cli"
_DIAGNOSTICS_ROOT = _SRC_ROOT / "diagnostics"
_APPLICATION_OUTPUT_ROOTS = (_SRC_ROOT / "application" / "wizard",)

_EXCLUDED_MODULES: set[Path] = set()

# (module, enclosing function, primitive) -> why this site may reach a stream
# without passing the redacting renderer. Keep the reason specific enough that a
# reviewer can re-derive the decision without reading the call site.
_ALLOWED_DIRECT_OUTPUTS: dict[tuple[str, str, str], str] = {
    ("entrypoints/cli/_common.py", "_render_and_echo", "typer.echo"): (
        "IS the success funnel, and is now the ONLY one: echoes "
        "render_command_output()'s text arm, which applied redact_for_cli_output "
        "before returning. The closing envelope and the streamed progress channel "
        "both delegate here, so this is the single place operator-facing success "
        "text crosses into stdout. It replaced two entries that each owned a "
        "private copy of the same three lines."
    ),
    ("entrypoints/cli/errors.py", "write_stderr", "write"): (
        "IS the stderr funnel: every write in this function emits redacted_text, "
        "already through the error-path redaction boundary."
    ),
    ("entrypoints/cli/_common.py", "emit_help_text", "typer.echo"): (
        "Click-generated help text (ctx.get_help()), composed by click from "
        "static command metadata. It carries no operator data to redact."
    ),
    ("entrypoints/cli/_app_diagnostics.py", "_diagnostics_root", "typer.echo"): (
        "Group help fallback: renders the click-generated help text verbatim, not operator data subject to redaction."
    ),
    ("entrypoints/cli/__init__.py", "_emit_version_report_and_exit", "typer.echo"): (
        "Product identity and version string only. It is emitted on the "
        "--version short-circuit, before an app root or renderer context exists."
    ),
    ("entrypoints/cli/_app_live_auth_preflight.py", "_emit_live_auth_preflight", "typer.echo"): (
        "Already redacted: emits redact_for_cli_output(line) to stderr. Honours "
        "the redaction boundary, though it hand-calls the policy rather than "
        "going through the renderer, so it does not consult the "
        "reveal-identifiers opt-in the way the funnel does."
    ),
    ("entrypoints/cli/__init__.py", "_emit_operator_progress", "typer.echo"): (
        "Operator progress banner on stderr, deliberately keeping stdout pure. "
        "Tolerated rather than clean: its content today is a closed set (Cl@ve "
        "Movil auth banners and a translated TUI action label) that "
        "redact_for_cli_output leaves byte-identical, so funnelling it would be "
        "a no-op. OperatorProgress.message is nonetheless an unconstrained str "
        "behind a public sink, so a future caller could feed it redactable "
        "material. Revisit if that sink grows a caller carrying identity data."
    ),
    ("application/wizard/_commands.py", "_echo_wizard_text", "typer.echo"): (
        "IS the wizard funnel, and is now the ONLY one: echoes "
        "render_command_output()'s text arm after prepending the sandbox banner. "
        "The success surface and the save-and-exit disclosure both delegate here. "
        "It replaced two entries that each held a private copy of the "
        "render-and-echo pair -- which is how one of them came to bypass the "
        "boundary while its sibling did not."
    ),
    ("entrypoints/cli/_config/_secure_input.py", "write_to_controlling_terminal", "write"): (
        "Recovery-code display writes directly to the controlling terminal "
        "device (CONOUT$ / /dev/tty), deliberately BYPASSING stdout so the "
        "candidate mnemonic can never land in a redirected stream, JSON "
        "envelope, or log. Routing it through the envelope renderer would be "
        "the secret-serialization defect the channel exists to prevent."
    ),
    ("entrypoints/cli/_terminal_errors.py", "_render_click_exception_text", "write"): (
        "Last-resort crash-boundary fallback used only when typer/rich "
        "rendering is unavailable; it cannot route through the rich path it is "
        "the fallback for."
    ),
    ("entrypoints/cli/_terminal_errors.py", "_emit_abort", "write"): (
        "Last-resort crash-boundary fallback emitting the constant 'Aborted.' "
        "marker; no operator data passes through it."
    ),
}


@dataclass(frozen=True)
class OutputCall:
    """A direct production output call discovered by the inventory scan."""

    path: Path
    lineno: int
    kind: str
    source: str
    function: str

    def key(self) -> tuple[str, str, str]:
        return (self.path.as_posix(), self.function, self.kind)

    def render(self) -> str:
        return f"{self.path.as_posix()}:{self.lineno}: {self.function}: {self.kind}: {self.source.strip()}"


def _production_modules() -> tuple[Path, ...]:
    modules: list[Path] = []
    for root in (_CLI_ROOT, _DIAGNOSTICS_ROOT, *_APPLICATION_OUTPUT_ROOTS):
        for path in scan_directory(root, pattern="*.py", recursive=True):
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


class _OutputCallVisitor(ast.NodeVisitor):
    """Collect emit primitives, tracking the enclosing named scope.

    A ``lambda`` is deliberately not pushed as a scope of its own. The defect
    this gate exists to catch first appeared as
    ``on_item=(lambda item: typer.echo(...))`` passed as a callback argument, so
    attributing that call to the named function that builds the lambda is what
    makes the exemption key stable and reviewable; an anonymous scope would give
    every such site an unnameable key.
    """

    def __init__(self, relative: Path, source_lines: list[str]) -> None:
        self._relative = relative
        self._source_lines = source_lines
        self._scope: list[str] = []
        self.calls: list[OutputCall] = []

    def _visit_scope(self, node: ast.AST, name: str) -> None:
        self._scope.append(name)
        self.generic_visit(node)
        self._scope.pop()

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, node.name)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node, node.name)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, node.name)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        kind = _call_kind(node)
        if kind is not None:
            self.calls.append(
                OutputCall(
                    path=self._relative,
                    lineno=node.lineno,
                    kind=kind,
                    source=self._source_lines[node.lineno - 1],
                    function=".".join(self._scope) or "<module>",
                )
            )
        self.generic_visit(node)


def _output_calls_in_source(source: str, relative: Path) -> tuple[OutputCall, ...]:
    """Scan one module's source for emit primitives."""
    visitor = _OutputCallVisitor(relative, source.splitlines())
    visitor.visit(ast.parse(source, filename=str(relative)))
    return tuple(visitor.calls)


def _direct_output_calls(path: Path) -> tuple[OutputCall, ...]:
    return _output_calls_in_source(path.read_text(encoding="utf-8"), path.relative_to(_SRC_ROOT))


def _all_discovered_calls() -> tuple[OutputCall, ...]:
    return tuple(call for path in _production_modules() for call in _direct_output_calls(path))


def test_scan_scope_is_non_empty() -> None:
    """Anti-vacuity: the scan must actually select modules and find emit sites.

    Every other assertion in this module is a "nothing unowned" shape, which a
    scope filter selecting zero modules satisfies perfectly. Without this
    control, renaming a package or breaking ``_production_modules`` would turn
    the whole gate green while detecting nothing.
    """

    modules = _production_modules()
    assert modules, "output-surface scan selected no production modules"

    calls = _all_discovered_calls()
    assert calls, "output-surface scan found no emit primitives in any scanned module"


def test_detector_flags_a_bypass_shaped_call() -> None:
    """Anti-vacuity: the detector must still fire on the defect shape it exists to catch.

    This reconstructs the callback-lambda bypass in the abstract — a bare
    ``typer.echo`` of a per-item progress line handed to a runner as ``on_item``
    — and proves both that it is detected and that it is attributed to the
    enclosing named function rather than the lambda, which is what makes the
    exemption key reviewable.
    """

    bypass_source = (
        "import typer\n"
        "\n"
        "def register_command(app):\n"
        "    def handler(source):\n"
        "        run_batch(source, on_item=(lambda item: typer.echo(progress_line(item))))\n"
    )

    calls = _output_calls_in_source(bypass_source, Path("entrypoints/cli/_synthetic_bypass.py"))

    assert [call.key() for call in calls] == [
        ("entrypoints/cli/_synthetic_bypass.py", "register_command.handler", "typer.echo")
    ]
    assert calls[0].key() not in _ALLOWED_DIRECT_OUTPUTS


def test_every_exemption_states_a_reason() -> None:
    """An exemption without a written reason is not a reviewed decision."""

    unexplained = sorted(key for key, reason in _ALLOWED_DIRECT_OUTPUTS.items() if not reason.strip())

    assert unexplained == [], f"exemption(s) carry no stated reason: {unexplained}"


def test_production_direct_output_surfaces_are_owned() -> None:
    """Every direct output call must be a reviewed exception to the renderer boundary."""

    unowned = [call.render() for call in _all_discovered_calls() if call.key() not in _ALLOWED_DIRECT_OUTPUTS]

    assert not unowned, (
        "New direct production CLI output call(s) bypass the centralized "
        "redaction boundary; route through emit_envelope/write_stderr/"
        "emit_progress_line or add an audited exception keyed by "
        "(module, enclosing function, primitive):\n" + "\n".join(unowned)
    )


def test_plan_owned_direct_outputs_still_exist() -> None:
    """The allow-list must not retain stale entries after output migrations.

    A stale entry FAILS rather than being ignored: once a site is funnelled or
    deleted, its exemption stops describing anything, and a silently-tolerated
    dead entry is how an allow-list grows into a place where a future bypass can
    hide under a name nobody re-checks.
    """

    discovered_keys = {call.key() for call in _all_discovered_calls()}
    stale = sorted(_ALLOWED_DIRECT_OUTPUTS.keys() - discovered_keys)

    assert stale == [], f"exemption(s) no longer match any call site; remove them: {stale}"


def test_emit_boundaries_are_present_for_success_output() -> None:
    """The success-output choke points must remain in the CLI common module."""

    common = (_CLI_ROOT / "_common.py").read_text(encoding="utf-8")

    assert "def _emit(" not in common
    assert "def emit_envelope(" in common
    assert "render_command_output(" in common
    # The streamed text-mode progress channel is a choke point in its own right:
    # a command reporting per-item progress emits to stdout before the closing
    # envelope exists, so without a shared primitive each caller reinvents a
    # bare echo and the stream drifts from the envelope's redaction.
    assert "def emit_progress_line(" in common
    # Both choke points delegate to ONE writer. Sharing a renderer is not the
    # same as sharing an implementation: the streamed channel originally called
    # render_command_output itself and kept its own echo, which is a second copy
    # of the boundary and the shape the whole gate exists to prevent. Pinning the
    # count keeps a third emitter from quietly minting a third copy.
    assert "def _render_and_echo(" in common
    assert common.count("typer.echo(rendered.text)") == 1
