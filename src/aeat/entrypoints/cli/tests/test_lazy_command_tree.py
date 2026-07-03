"""Lazy-subcommand-registration guards for the ``aeat`` CLI.

The AEAT command tree is wide: every leaf command module imports the
application layer and, transitively, the registry parse. Registering
every subcommand eagerly made constructing the ``aeat`` app object
import the whole tree — so ``aeat --version`` and ``aeat --help`` paid
the full registry cost even though neither dispatches into a
subcommand.

:mod:`aeat.entrypoints.cli._command_suggestions` now registers heavy
subcommand groups through :class:`LazySubcommand` loaders that import
their module only when the subtree is first resolved. These tests are
the structural guard for that contract:

* a real subprocess cold start of ``aeat --version`` must complete well
  under the time a registry parse alone would cost; and
* importing the CLI package, and invoking the ``--version`` / ``--help``
  surfaces, must not import the registry or any heavy command module.

A regression that re-introduces eager registration overshoots the
timing budget by seconds and re-populates ``sys.modules`` with the
registry — both assertions fail loudly.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import time

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# A cold ``aeat --version`` — fresh interpreter, no warm import cache —
# resolves in well under a second once the command tree is lazy. A
# re-introduced eager registration pulls the ~0.6 s registry parse (and
# its workflow / deadlines dependencies) into app construction, pushing
# a cold start back toward 3 s. 2.0 s is a deliberately generous ceiling
# that still fails hard on that regression without being flaky on a
# loaded CI host.
_COLD_START_BUDGET_S = 2.0

# Modules that must stay out of ``sys.modules`` after a state-free CLI
# surface runs. The registry parse is the headline cost; the heavy
# command modules are the eager-import vector that used to drag it in.
_FORBIDDEN_MODULE_PREFIXES = (
    "aeat.domain.calculations.registry",
    "aeat.application.workflow",
    "aeat.application.overview",
)
_FORBIDDEN_COMMAND_MODULES = (
    "aeat.entrypoints.cli._overview",
    "aeat.entrypoints.cli._ledger",
    "aeat.entrypoints.cli._app_live",
    "aeat.entrypoints.cli._modelo",
    "aeat.entrypoints.cli.registry",
    "aeat.entrypoints.cli._review",
    "aeat.entrypoints.cli._config",
)


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    """Execute ``code`` in a fresh interpreter and return the result."""

    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_version_cold_start_completes_under_budget() -> None:
    """A fresh-interpreter ``aeat --version`` returns inside the budget.

    This spawns the real console entry point in a new process — paying
    interpreter startup and every import — so the assertion covers the
    operator-visible cold start, not a warm in-process invocation. The
    ``main`` callable is the exact function the ``aeat`` console script
    binds, invoked with ``argv`` set to ``["aeat", "--version"]``.
    """

    code = """
        import sys
        sys.argv = ["aeat", "--version"]
        from aeat.entrypoints.cli import main
        try:
            main()
        except SystemExit as exit_:
            raise SystemExit(exit_.code)
        """
    start = time.perf_counter()
    completed = _run_python(code)
    elapsed = time.perf_counter() - start

    assert completed.returncode == 0, completed.stderr
    assert "aeat" in completed.stdout
    assert elapsed < _COLD_START_BUDGET_S, (
        f"aeat --version cold start took {elapsed:.2f}s (budget {_COLD_START_BUDGET_S}s) — "
        "lazy subcommand registration likely regressed to an eager import"
    )


def test_importing_cli_package_does_not_import_registry() -> None:
    """Importing ``aeat.entrypoints.cli`` must not import the registry.

    Constructing the ``aeat`` app object is import-only work. If it
    pulls the registry or a heavy command module, every CLI surface —
    including ``--version`` — inherits that cost.
    """

    forbidden = (*_FORBIDDEN_MODULE_PREFIXES, *_FORBIDDEN_COMMAND_MODULES)
    completed = _run_python(
        f"""
        import sys
        import aeat.entrypoints.cli  # noqa: F401
        forbidden = {forbidden!r}
        leaked = sorted(
            name
            for name in sys.modules
            if any(name == p or name.startswith(p + ".") for p in forbidden)
        )
        print("\\n".join(leaked))
        """,
    )

    assert completed.returncode == 0, completed.stderr
    leaked = [line for line in completed.stdout.splitlines() if line.strip()]
    assert leaked == [], f"importing the CLI package leaked heavy modules: {leaked}"


@pytest.mark.parametrize("argv", [["--version"], ["--help"], []])
def test_state_free_surface_does_not_import_registry(argv: list[str]) -> None:
    """``aeat`` (bare), ``aeat --version``, and ``aeat --help`` run without registry parse.

    State-free surfaces (version, help, and bare landing) short-circuit in the
    root callback before any subcommand is resolved, so no :class:`LazySubcommand`
    loader fires and no heavy command module is imported. The bare invocation
    surface shows the landing page (profile-creation wizard prompt) without
    registry access.
    """

    forbidden = (*_FORBIDDEN_MODULE_PREFIXES, *_FORBIDDEN_COMMAND_MODULES)
    args_repr = " ".join(argv) if argv else "(bare invocation)"
    completed = _run_python(
        f"""
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        import sys
        from click.exceptions import Exit as ClickExit
        from typer.main import get_command
        from aeat.entrypoints.cli import app

        stdout = StringIO()
        stderr = StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = get_command(app).main(args={argv!r}, prog_name="aeat", standalone_mode=False)
        except ClickExit as exit_:
            exit_code = exit_.exit_code
        else:
            exit_code = result if isinstance(result, int) else 0
        output = stdout.getvalue() + stderr.getvalue()
        assert exit_code == 0, output

        forbidden = {forbidden!r}
        leaked = sorted(
            name
            for name in sys.modules
            if any(name == p or name.startswith(p + ".") for p in forbidden)
        )
        print("\\n".join(leaked))
        """,
    )

    assert completed.returncode == 0, completed.stderr
    leaked = [line for line in completed.stdout.splitlines() if line.strip()]
    assert leaked == [], f"`aeat {args_repr}` imported heavy modules it must avoid: {leaked}"


def test_dispatching_a_subcommand_loads_its_module() -> None:
    """Invoking an ``app`` subcommand imports exactly that command module.

    The lazy loader is not a permanent shutout: dispatching into a
    subtree must import the module on demand. This is the
    counterpart proof to the import-absence tests — it confirms the
    on-demand import still happens when an operator actually reaches
    for the subtree, so no command silently becomes unreachable.
    """

    completed = _run_python(
        """
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        import sys
        from click.exceptions import Exit as ClickExit
        from typer.main import get_command
        from aeat.entrypoints.cli import app

        command = get_command(app)
        assert "aeat.entrypoints.cli._modelo" not in sys.modules

        stdout = StringIO()
        stderr = StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = command.main(args=["app", "modelo", "--help"], prog_name="aeat", standalone_mode=False)
        except ClickExit as exit_:
            exit_code = exit_.exit_code
        else:
            exit_code = result if isinstance(result, int) else 0
        assert exit_code == 0, stdout.getvalue() + stderr.getvalue()
        print("loaded" if "aeat.entrypoints.cli._modelo" in sys.modules else "missing")
        """,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "loaded"
