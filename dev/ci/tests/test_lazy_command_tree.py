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

* a real subprocess cold start of ``aeat --version`` must cost well
  under the CPU a registry parse alone would burn; and
* importing the CLI package, and invoking the ``--version`` / ``--help``
  surfaces, must not import the registry or any heavy command module.

A regression that re-introduces eager registration overshoots the
budget by CPU-seconds and re-populates ``sys.modules`` with the
registry — both assertions fail loudly.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from dev.ci.perf_measurement import SubprocessTiming, min_subprocess_cpu_seconds, wall_advisory_message

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The gate binds child-process CPU-TIME, per the `.github` control plane's
# honest-perf-gate invariant, and prints wall-clock as an advisory only.
#
# Wall-clock cannot carry this gate on this machine. It is shared with a large
# agent fleet and with CI runners for several repositories, and the dilation
# lands on the SPAWN itself: a bare ``python -c "import sys"`` measured 1.63 s
# to 5.00 s of wall for 0.08 s of CPU. An earlier revision tried to cancel that
# out by subtracting a bare-interpreter WALL baseline, which is why this test is
# on its second load-robustness attempt — the subtraction does not hold, because
# the two spawns are dilated by independent samples of a fluctuating load, not
# by a shared constant. CPU-time is stable across the same runs: 1.45-1.89 CPU-s
# for the CLI spawn while its wall moved 3.23 s to 6.75 s.
#
# The measurement is still MARGINAL over a bare-interpreter baseline, because
# the interpreter's own startup CPU is not the CLI's cost to answer for and
# differs across the fleet's two machine architectures. The baseline is small
# in CPU terms (~0.08 s), so this now corrects a floor rather than cancelling a
# dominant term. ``min`` over a few samples is the conservative reading:
# contention only ever ADDS CPU (SMT and cache pressure), never removes it.
#
# Budget derivation, not a guess: the lazy tree measures a 1.38-1.81 CPU-s
# marginal cost on the loaded workstation, and the fleet's measured
# contention inflation is 1.64x (``CPU_CONTENTION_MARGIN`` in
# ``dev/ci/perf_measurement.py``), so 1.81 x 1.64 rounds to the 3.0 ceiling.
# Restoring eager registration costs
# 5.75 CPU-s marginal — 1.9x the ceiling — and
# ``test_cold_start_budget_still_fails_on_eager_registration`` asserts that
# separation on every run so the budget can never go vacuous.
_MARGINAL_COLD_START_BUDGET_CPU_S = 3.0
_COLD_START_SAMPLES = 3
_COLD_START_TIMEOUT_S = 300.0

# The CPU conversion cannot see a WEDGE — a spawn blocked on a stalled mount
# burns no CPU however long it hangs — so the former wall budget is retained as
# a non-failing advisory rather than deleted. It is raised on the warnings
# channel, not printed: the broad serial pass runs without `-s`, so capture
# discards the print above on exactly the passing runs this is meant to
# annotate.
#
# Threshold and ratio are both derived from this site's own measurements, and
# the ratio has to be far looser here than at an in-process benchmark because
# the wall time of a SPAWN is dominated by process creation this SUT does not
# answer for: a bare `python -c "import sys"` measured 1.63-5.00 s of wall for
# 0.08 s of CPU on this box. The measured CLI spawn ran 3.23-6.75 s of wall
# against 1.45-1.89 CPU-s, so a healthy loaded spawn tops out near 4.7x. 12.0
# clears that with headroom; reaching it needs roughly 20 s of wall, about four
# times the worst spawn wait ever measured here.
_COLD_START_WALL_ADVISORY_S = 7.0
_COLD_START_WEDGE_WALL_TO_CPU_RATIO = 12.0

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

    return subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no shell
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _min_cold_start(code: str, *, samples: int = _COLD_START_SAMPLES) -> tuple[float, float, SubprocessTiming]:
    """Spawn ``code`` ``samples`` times; return (min CPU s, min wall s, last run).

    Delegates to the shared
    :func:`dev.ci.perf_measurement.min_subprocess_cpu_seconds`, which owns the
    platform-specific child-TREE CPU accounting for every perf gate in the
    repository.
    """

    return min_subprocess_cpu_seconds(
        [sys.executable, "-c", textwrap.dedent(code)],
        samples=samples,
        timeout_s=_COLD_START_TIMEOUT_S,
    )


#: A fresh-interpreter ``aeat --version`` through the real console entry point.
#: ``main`` is the exact callable the ``cadrumo`` console script binds.
_VERSION_COLD_START_CODE = """
    import sys
    sys.argv = ["aeat", "--version"]
    from cadrumo.entrypoints.cli import main
    try:
        main()
    except SystemExit as exit_:
        raise SystemExit(exit_.code)
    """


@pytest.mark.serial
def test_version_cold_start_completes_under_cpu_budget() -> None:
    """A fresh-interpreter ``aeat --version`` stays inside the CPU budget.

    This spawns the real console entry point in a new process — paying
    interpreter startup and every import — so the assertion covers the
    operator-visible cold start, not a warm in-process invocation.

    The gate binds the marginal CHILD CPU-time over a bare-interpreter
    baseline; wall-clock is measured and printed but never asserted, because
    on this shared machine the spawn's wall time reports the load average
    rather than the import cost (see the module-level note). Wall does keep a
    retained WARNING threshold, which is a different claim from an assertion:
    it fires only on the wedge shape a CPU ceiling is structurally blind to,
    and it cannot fail this test.
    """

    baseline_cpu, baseline_wall, _ = _min_cold_start("import sys")
    sut_cpu, sut_wall, completed = _min_cold_start(_VERSION_COLD_START_CODE)
    marginal_cpu = sut_cpu - baseline_cpu

    print(
        f"\n[perf advisory] aeat --version cold start: "
        f"marginal_cpu={marginal_cpu:.3f}s (gate=cpu<{_MARGINAL_COLD_START_BUDGET_CPU_S}s) "
        f"cpu={sut_cpu:.3f}s baseline_cpu={baseline_cpu:.3f}s | "
        f"wall={sut_wall:.3f}s baseline_wall={baseline_wall:.3f}s "
        f"marginal_wall={(sut_wall - baseline_wall):.3f}s (wall advisory, never asserted)",
    )

    wall_advisory_message(
        "aeat --version cold start",
        wall_seconds=sut_wall,
        cpu_seconds=sut_cpu,
        wall_advisory_seconds=_COLD_START_WALL_ADVISORY_S,
        hang_wall_to_cpu_ratio=_COLD_START_WEDGE_WALL_TO_CPU_RATIO,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("CADRUMO ")
    assert marginal_cpu < _MARGINAL_COLD_START_BUDGET_CPU_S, (
        f"aeat --version cold start added {marginal_cpu:.2f} CPU-s over a bare interpreter "
        f"({sut_cpu:.2f} vs baseline {baseline_cpu:.2f} CPU-s; budget "
        f"{_MARGINAL_COLD_START_BUDGET_CPU_S} CPU-s) — lazy subcommand registration likely "
        f"regressed to an eager import (wall {sut_wall:.2f}s is advisory only)"
    )


@pytest.mark.serial
def test_cold_start_budget_still_fails_on_eager_registration() -> None:
    """The cold-start budget is not vacuous: eager registration still breaks it.

    A ceiling nothing can exceed is worse than no ceiling, and moving a gate
    from wall-clock to CPU-time is exactly the change that can quietly make one
    unfalsifiable. This drives the real regression rather than simulating a
    delay: it imports the very command modules
    :data:`_FORBIDDEN_COMMAND_MODULES` names — which is what eager
    registration did — and asserts the resulting cold start exceeds the budget.

    Reading the module list from the same constant the absence guards use keeps
    the two halves from drifting: a module dropped from that tuple weakens both
    the guard and this proof together, visibly, rather than silently.
    """

    eager_imports = "\n".join(f"import {module}" for module in _FORBIDDEN_COMMAND_MODULES)
    code = f"{eager_imports}\n{textwrap.dedent(_VERSION_COLD_START_CODE)}"

    baseline_cpu, _, _ = _min_cold_start("import sys")
    eager_cpu, eager_wall, completed = _min_cold_start(code)
    marginal_cpu = eager_cpu - baseline_cpu

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("CADRUMO ")
    assert marginal_cpu > _MARGINAL_COLD_START_BUDGET_CPU_S, (
        f"eagerly importing every heavy command module cost only {marginal_cpu:.2f} marginal CPU-s, "
        f"which does NOT exceed the {_MARGINAL_COLD_START_BUDGET_CPU_S} CPU-s budget — the budget can "
        f"no longer detect a regression to eager registration and must be tightened "
        f"(wall {eager_wall:.2f}s, advisory)"
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


def test_every_lazy_registration_wires_a_cold_subcommand() -> None:
    """Every declared registration is reachable without importing its target.

    This observes the real command registrations, rather than comparing two data
    structures: deleting the registration loop or misspelling one group/name
    leaves the declared row without its lazy child and fails here. At the same
    time the check proves registration itself does not eagerly import any
    target module.
    """
    completed = _run_python(
        """
        import sys
        from cadrumo.entrypoints.cli import _LAZY_COMMAND_REGISTRATIONS, app
        from cadrumo.entrypoints.cli._command_suggestions import LazySubcommand, _LAZY_REGISTRY

        missing = []
        eager = []
        for group_name, command_name, module_name in _LAZY_COMMAND_REGISTRATIONS:
            child = _LAZY_REGISTRY.get(group_name, {}).get(command_name)
            if not isinstance(child, LazySubcommand):
                missing.append((group_name, command_name, type(child).__name__ if child is not None else None))
            qualified = "cadrumo.entrypoints.cli" + module_name
            if qualified in sys.modules:
                eager.append(qualified)
        print(repr((missing, eager)))
        """,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "([], [])", completed.stdout


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
