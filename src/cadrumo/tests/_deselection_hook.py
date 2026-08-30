"""Make marker deselection impossible to mistake for a full run.

``addopts`` pins every default invocation to the ``unit`` lane, so a plain
``pytest`` run silently skips roughly three thousand integration tests and
reports only what it chose to run. pytest's own footer mentions the
deselected count in passing, between the pass count and the runtime, where
it reads as noise; a reader sees "N passed" and reasonably concludes the
suite is green.

That silence has a measured cost. A path-scoped run over a module whose
every test carries ``integration`` prints "no tests ran" and exits without
a single failure, which is the sharpest edge: the run that looks fine
precisely because it did nothing. A green count over a path that selected
nothing has already let a real defect through, and a collection error
inside the deselected lane can sit invisible indefinitely.

This hook does not change WHAT runs -- the default lane's selection and
runtime are untouched, because narrowing the developer loop to the fast
lane is a deliberate choice. It changes only what the reader is told:
every deselection is stated plainly, and a run that selected nothing at
all is reported as the non-event it is rather than as success.

See Also:
    :mod:`cadrumo.tests._marker_hook`
        The marker-contract enforcer sharing this collection surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest
    from _pytest.terminal import TerminalReporter

_OUTCOME_KEYS = ("passed", "failed", "error", "skipped", "xfailed", "xpassed")


def _selection_expression(config: pytest.Config) -> str:
    """Return the active ``-m`` expression, or a placeholder when unset."""
    try:
        expression = config.getoption("-m")
    except ValueError:  # pragma: no cover - option always registered by pytest
        return "(unknown)"
    return str(expression).strip() or "(none)"


def _executed_count(terminalreporter: TerminalReporter) -> int:
    """Return how many tests actually produced an outcome."""
    return sum(len(terminalreporter.stats.get(key, [])) for key in _OUTCOME_KEYS)


def _remediation(expression: str) -> str:
    """Return advice that cannot reproduce the run that just selected nothing.

    Naming a fixed lane is wrong precisely when the operator already chose
    it: following "re-run with -m integration" after running -m integration
    reproduces the identical empty selection, so the remediation completes
    the defect instead of resolving it. When the selected lane is already
    the one that would otherwise be suggested, point at the selector that
    cannot be empty for a module that collected anything at all.
    """
    if "integration" in expression:
        return (
            "You already selected 'integration', so these tests carry a different marker: "
            "re-run with -m '' to select every lane, or `just test-both-lanes`."
        )
    return (
        "If you targeted a specific module, its tests likely carry a different marker: "
        "re-run with -m integration (or `just test-integration`)."
    )


def apply(
    terminalreporter: TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Report deselection prominently, and an empty selection as a non-result.

    Args:
        terminalreporter: The active reporter, whose ``stats`` carry the
            aggregated deselection count (already merged across xdist
            workers by the time the summary runs).
        exitstatus: The session exit status; unused, the message is
            informational and never changes the outcome.
        config: The session config, read only for the ``-m`` expression.
    """
    # A collect-only run executes nothing BY DESIGN, so warning about it would
    # fire on every inventory check and train the reader to ignore the banner —
    # which is the habit this hook exists to break.
    if config.getoption("--collect-only", default=False):
        return

    deselected = len(terminalreporter.stats.get("deselected", []))
    executed = _executed_count(terminalreporter)
    expression = _selection_expression(config)

    # The empty-selection case is reported WITHOUT relying on the deselected
    # count, because xdist performs marker deselection inside its workers and
    # the controller's stats never receive it. That count is therefore absent
    # on exactly the default `-n auto` invocation this hook most needs to
    # cover, so it is treated as a detail to include when known rather than
    # as the trigger.
    if executed == 0:
        scope = f"All {deselected} collected tests were" if deselected else "Every collected test was"
        terminalreporter.write_sep("=", "NOTHING RAN", red=True, bold=True)
        terminalreporter.write_line(
            f"This run executed 0 tests. {scope} deselected by -m {expression!r}.",
            red=True,
            bold=True,
        )
        terminalreporter.write_line(
            "A green result here means the selection matched nothing, NOT that the code is sound.",
            red=True,
        )
        terminalreporter.write_line(_remediation(expression))
        return

    if not deselected:
        return

    terminalreporter.write_sep("=", "PARTIAL RUN", yellow=True, bold=True)
    terminalreporter.write_line(
        f"{executed} tests ran; {deselected} were DESELECTED by -m {expression!r} and never executed.",
        yellow=True,
        bold=True,
    )
    terminalreporter.write_line(
        "Green here covers the selected lane only. Run the rest with `just test-integration`, "
        "or both lanes with `just test-both-lanes`.",
    )
