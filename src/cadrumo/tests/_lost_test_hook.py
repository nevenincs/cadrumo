"""Make a run that silently dropped tests impossible to read as complete.

A thread-method timeout kills the worker PROCESS rather than raising inside
the test, so the worker dies before reporting. Its remaining tests are never
redistributed, and pytest's footer states only what came back. A five-test
module whose worker died mid-file reports ``1 failed, 2 passed`` -- a total
that is internally consistent, carries no error, no skip and no mismatch,
and is indistinguishable in shape from a complete run.

The cost is not the lost runtime. It is that every reader downstream takes
the FAILED list as the set of things wrong, when it is a subset of unknown
size. Conclusions drawn from such a run are drawn from a population nobody
knows the bounds of, and the arithmetic gives no hint: 1 + 2 = 3 is correct
about what was reported and silent about the two that never ran.

This hook changes nothing about what executes. It states the discrepancy
between what collection found and what the reporter heard back, so a run
with a hole in it announces the hole.

See Also:
    :mod:`cadrumo.tests._deselection_hook`
        The sibling reporter for the other way a run under-executes, where
        the tests were deliberately not selected rather than lost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest
    from _pytest.terminal import TerminalReporter

_OUTCOME_KEYS = ("passed", "failed", "error", "skipped", "xfailed", "xpassed")


def _executed_count(terminalreporter: TerminalReporter) -> int:
    """Return how many tests actually produced an outcome."""
    return sum(len(terminalreporter.stats.get(key, [])) for key in _OUTCOME_KEYS)


def _deselected_count(terminalreporter: TerminalReporter) -> int:
    """Return how many tests collection found and selection then dropped."""
    return len(terminalreporter.stats.get("deselected", []))


def _collected_count(terminalreporter: TerminalReporter) -> int | None:
    """Return the collected total, or ``None`` when the session cannot say.

    Reported by the controller after xdist merges its workers' collections,
    so it is the one figure that knows about tests a dead worker owned.
    """
    session = getattr(terminalreporter, "_session", None)
    collected = getattr(session, "testscollected", None)
    return collected if isinstance(collected, int) else None


def apply(
    terminalreporter: TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Report tests that were collected but never accounted for.

    Args:
        terminalreporter: The active reporter, whose ``stats`` carry the
            outcomes merged across xdist workers, and whose session carries
            the collected total those outcomes are measured against.
        exitstatus: The session exit status; unused, because a hole in the
            run is worth stating whether or not anything failed.
        config: The active configuration; unused, retained to match the
            hook signature its sibling reporters share.
    """
    del exitstatus, config

    collected = _collected_count(terminalreporter)
    if collected is None:
        return

    accounted = _executed_count(terminalreporter) + _deselected_count(terminalreporter)
    missing = collected - accounted
    if missing <= 0:
        return

    terminalreporter.write_sep("=", "INCOMPLETE RUN", red=True, bold=True)
    terminalreporter.write_line(
        f"{missing} of {collected} collected test(s) never reported an outcome.",
        red=True,
        bold=True,
    )
    terminalreporter.write_line(
        "The counts above describe only what came back. A worker that dies -- a "
        "thread-method timeout kills the process -- takes its remaining tests with "
        "it, and they are not redistributed.",
    )
    terminalreporter.write_line(
        "Do NOT read this run's failure list as the set of things wrong: it is a "
        "subset of unknown size. Re-run the affected path serially before drawing "
        "any conclusion from it.",
    )
