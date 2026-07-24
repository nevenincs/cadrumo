"""Lazy-subcommand-registration guards for the ``cadrumo`` CLI.

The Cadrumo command tree is wide: every leaf command module imports the
application layer and, transitively, the registry parse. Registering
every subcommand eagerly made constructing the Cadrumo app object
import the whole tree — so ``aeat --version`` and ``aeat --help`` paid
the full registry cost even though neither dispatches into a
subcommand.

:mod:`cadrumo.entrypoints.cli._command_suggestions` now registers heavy
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
# a cold start back toward 3 s.
#
# The signal is the MARGINAL cost the CLI import adds over a bare
# interpreter, not the absolute wall time: on a saturated host the bare
# interpreter spawn itself dilates by seconds, so a fixed absolute
# ceiling flaked under parallel load even though the import cost had not
# regressed. We measure a bare-interpreter baseline with the identical
# spawn harness and assert the difference, so both terms scale together
# with host load and cancel. ``min`` over a few samples filters transient
# scheduler spikes (contention only ever adds time). Good runs measure a
# ~0.8 s margin; the eager-import regression overshoots ~2.9 s, so a 2.0 s
# marginal ceiling fails hard on the regression without flaking on load.
_MARGINAL_COLD_START_BUDGET_S = 2.0
_COLD_START_SAMPLES = 3

# Modules that must stay out of ``sys.modules`` after a state-free CLI
# surface runs. The registry parse is the headline cost; the heavy
# command modules are the eager-import vector that used to drag it in.
#
# ``httpx`` is here because guarding only the registry vector let a second,
# unwatched one grow: ``core.config`` imports ``TelemetryTier`` from
# ``core.telemetry``, whose facade eagerly imported the optional HTTP sink,
# whose module-scope ``import httpx`` (plus ``asyncio``) cost ~0.7s on EVERY
# surface -- including ``--version``, which never emits telemetry. The sink
# now imports it inside ``send``. This entry keeps that door shut: an
# outbound HTTP client must never be imported to print a version string.
_FORBIDDEN_MODULE_PREFIXES = (
    "cadrumo.domain.calculations.registry",
    "cadrumo.application.workflow",
    "cadrumo.application.overview",
    "httpx",
)
_FORBIDDEN_COMMAND_MODULES = (
    "cadrumo.entrypoints.cli._overview",
    "cadrumo.entrypoints.cli._ledger",
    "cadrumo.entrypoints.cli._app_live",
    "cadrumo.entrypoints.cli._modelo",
    "cadrumo.entrypoints.cli.registry",
    "cadrumo.entrypoints.cli._review",
    "cadrumo.entrypoints.cli._config",
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


def _min_cold_start(code: str, *, samples: int = _COLD_START_SAMPLES) -> tuple[float, subprocess.CompletedProcess[str]]:
    """Spawn ``code`` ``samples`` times; return the fastest wall time and the last result.

    ``min`` is the cleanest cold-start estimate: interpreter spawns only
    ever gain time under host contention, so the minimum reflects the
    unloaded cost while filtering transient scheduler spikes.
    """

    best = float("inf")
    completed: subprocess.CompletedProcess[str] | None = None
    for _ in range(samples):
        start = time.perf_counter()
        completed = _run_python(code)
        best = min(best, time.perf_counter() - start)
    assert completed is not None
    return best, completed


@pytest.mark.serial
def test_version_cold_start_completes_under_budget() -> None:
    """A fresh-interpreter ``aeat --version`` returns inside the budget.

    This spawns the real console entry point in a new process — paying
    interpreter startup and every import — so the assertion covers the
    operator-visible cold start, not a warm in-process invocation. The
    ``main`` callable is the exact function the ``cadrumo`` console script
    binds, invoked with ``argv`` set to ``["aeat", "--version"]``.
    """

    code = """
        import sys
        sys.argv = ["aeat", "--version"]
        from cadrumo.entrypoints.cli import main
        try:
            main()
        except SystemExit as exit_:
            raise SystemExit(exit_.code)
        """
    # A bare interpreter spawn through the identical harness is the
    # baseline; the marginal cost the CLI import adds over it is the
    # load-invariant signal (see the module-level note).
    baseline_elapsed, _ = _min_cold_start("import sys")
    sut_elapsed, completed = _min_cold_start(code)
    marginal = sut_elapsed - baseline_elapsed

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("CADRUMO ")
    assert marginal < _MARGINAL_COLD_START_BUDGET_S, (
        f"aeat --version cold start added {marginal:.2f}s over a bare interpreter "
        f"({sut_elapsed:.2f}s vs baseline {baseline_elapsed:.2f}s; budget "
        f"{_MARGINAL_COLD_START_BUDGET_S}s) — lazy subcommand registration likely "
        "regressed to an eager import"
    )


def test_importing_cli_package_does_not_import_registry() -> None:
    """Importing ``cadrumo.entrypoints.cli`` must not import the registry.

    Constructing the Cadrumo app object is import-only work. If it
    pulls the registry or a heavy command module, every CLI surface —
    including ``--version`` — inherits that cost.
    """

    forbidden = (*_FORBIDDEN_MODULE_PREFIXES, *_FORBIDDEN_COMMAND_MODULES)
    completed = _run_python(
        f"""
        import sys
        import cadrumo.entrypoints.cli  # noqa: F401
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
        from cadrumo.entrypoints.cli import app

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
    assert leaked == [], f"`cadrumo {args_repr}` imported heavy modules it must avoid: {leaked}"


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
        from cadrumo.entrypoints.cli import app

        command = get_command(app)
        assert "cadrumo.entrypoints.cli._modelo" not in sys.modules

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
        print("loaded" if "cadrumo.entrypoints.cli._modelo" in sys.modules else "missing")
        """,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "loaded"


def test_resolving_the_config_group_does_not_import_the_wizard() -> None:
    """Reaching ``config`` must not build the profile-setup wizard.

    ``build_wizard_command`` reaches the whole wizard dependency tail, and
    the two wizard verbs used to be CONSTRUCTED at ``_config`` package-import
    time — so every ``config`` verb, ``login`` included, paid for the wizard
    before parsing its own arguments. Deferring the import alone would not
    have held: the module-level call kept the tail eager, so the
    construction itself moved behind a per-leaf lazy registration.

    The guard is placed on group RESOLUTION rather than on process start
    because the group is where the regression would reappear: a future
    contributor adding a module-level wizard call to ``_config`` reds this
    test without having to notice the cold-start budget at all.
    """

    completed = _run_python(
        """
        import sys
        from typer.main import get_command
        from cadrumo.entrypoints.cli import app

        command = get_command(app)
        command.get_command(None, "config")
        print("imported" if "cadrumo.application.wizard" in sys.modules else "absent")
        """,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "absent"


def test_dispatching_a_wizard_verb_loads_the_wizard() -> None:
    """The wizard deferral is a delay, not a shutout.

    Counterpart to the absence guard above: an operator who actually asks
    for ``config profile create`` must still get the fully-built wizard
    command. Without this, the absence assertion could be satisfied by a
    verb that had silently become unreachable.
    """

    completed = _run_python(
        """
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        import sys
        from click.exceptions import Exit as ClickExit
        from typer.main import get_command
        from cadrumo.entrypoints.cli import app

        command = get_command(app)
        stdout = StringIO()
        stderr = StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = command.main(
                    args=["config", "profile", "create", "--help"],
                    prog_name="aeat",
                    standalone_mode=False,
                )
        except ClickExit as exit_:
            exit_code = exit_.exit_code
        else:
            exit_code = result if isinstance(result, int) else 0
        assert exit_code == 0, stdout.getvalue() + stderr.getvalue()
        rendered = stdout.getvalue()
        assert "--entity-type" in rendered, rendered
        print("loaded" if "cadrumo.application.wizard" in sys.modules else "missing")
        """,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "loaded"
