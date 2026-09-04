"""Real-behaviour tests for the saved-run integrity judgement.

Every fixture here is a real pytest output shape taken from this repository's
own runs, not an invented one. The four unusable shapes each cost this campaign
a wrong conclusion before the banner existed to name them, and a classifier that
recognised only invented output would be describing a suite nobody runs.
"""

from __future__ import annotations

import pytest

from ..run_integrity import VERDICTS, classify_run

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CLEAN = """
dev/docs/preprocess/tests/test_hook.py .....                             [ 12%]
================= 23 failed, 294 passed in 121.71s (0:02:01) ==================
"""

_CRASHED = """
worker 'gw5' crashed while running 'dev/audit/tests/test_security_scan.py::test_real_timeout'
=============================== INCOMPLETE RUN ================================
2 of 317 collected test(s) never reported an outcome.
================= 24 failed, 291 passed in 344.66s (0:05:44) ==================
"""

_NOTHING = """
================================= NOTHING RAN =================================
This run executed 0 tests, and COLLECTED 0 -- so the selection is not the cause.
============================ no tests ran in 1.72s ============================
"""

_TRUNCATED = """
dev/docs/preprocess/tests/test_hook.py .....                             [ 12%]
dev/docs/preprocess/tests/test_pdf.py ..
"""


def test_a_complete_run_is_usable() -> None:
    """The ordinary case, and the one every other verdict is measured against."""
    result = classify_run(_CLEAN)
    assert result.verdict == "usable"
    assert result.usable
    assert result.counts == {"failed": 23, "passed": 294}
    assert result.crashed == ()


def test_a_lost_worker_makes_a_run_unusable_however_plausible_its_tally() -> None:
    """The failure list is a subset of unknown size, and the tally hides it.

    24 failed and 291 passed is 315 of 317 collected. Nothing about those two
    numbers looks wrong, which is why the run must be judged by the banner
    rather than by whether its arithmetic is surprising.
    """
    result = classify_run(_CRASHED)
    assert result.verdict == "lost_workers"
    assert not result.usable
    assert result.unreported == 2
    assert result.collected == 317
    assert result.crashed == (("gw5", "dev/audit/tests/test_security_scan.py::test_real_timeout"),)


def test_a_run_that_executed_nothing_is_not_a_run_with_no_failures() -> None:
    """A comparison reads an empty failure set as success."""
    result = classify_run(_NOTHING)
    assert result.verdict == "nothing_ran"
    assert not result.usable


def test_truncated_output_is_refused_rather_than_read_as_empty() -> None:
    """Output cut off by a pipe, or a process killed mid-write, has no summary.

    Calling that "nothing failed" is the mistake the module exists to stop, so
    the absence of a summary line is its own verdict rather than a default.
    """
    result = classify_run(_TRUNCATED)
    assert result.verdict == "no_summary"
    assert not result.usable
    assert result.counts == {}


def test_a_lost_worker_outranks_every_other_defect_in_the_same_run() -> None:
    """Reporting the lesser one invites fixing it and re-reading the same subset."""
    both = _CRASHED + _NOTHING
    assert classify_run(both).verdict == "lost_workers"


def test_every_verdict_is_declared_and_reachable() -> None:
    """A verdict with no proof stops being assigned without anyone noticing."""
    reached = {
        classify_run(_CLEAN).verdict,
        classify_run(_CRASHED).verdict,
        classify_run(_NOTHING).verdict,
        classify_run(_TRUNCATED).verdict,
    }
    assert reached == set(VERDICTS)


def test_the_headline_names_the_verdict_and_what_supports_it() -> None:
    """A verdict without its evidence is a number somebody has to trust."""
    headline = classify_run(_CRASHED).headline()
    assert "lost_workers" in headline
    assert "unreported=2/317" in headline
    assert "crashed=1" in headline


def test_the_counts_come_from_the_last_summary_line() -> None:
    """A run can print more than one summary-shaped line; the last is the result.

    Session-scoped output and a rerun both produce earlier lines matching the
    same shape, and reading the first would report a partial result as the
    total.
    """
    doubled = "==== 1 failed, 1 passed in 0.1s ====\n" + _CLEAN
    assert classify_run(doubled).counts == {"failed": 23, "passed": 294}


def test_error_and_warning_plurals_are_counted_under_one_name() -> None:
    """pytest writes ``1 error`` and ``2 errors``, and both are the same thing."""
    singular = classify_run("==== 1 failed, 1 error in 0.1s ====\n")
    plural = classify_run("==== 1 failed, 2 errors in 0.1s ====\n")
    assert singular.counts["errors"] == 1
    assert plural.counts["errors"] == 2


_XDIST = """
created: 6/6 workers
6 workers [356 items]
================= 356 passed in 155.70s (0:02:35) =========================
"""

_SERIAL = """
collected 24 items / 21 deselected / 3 selected
================= 3 passed, 21 deselected in 1.20s ========================
"""


def test_the_collected_population_is_read_from_the_xdist_worker_line() -> None:
    """Under xdist a marker-filtered run prints no deselection count at all.

    Its only trace is the population: ``6 workers [356 items]`` against
    ``[371 items]`` for the same directory unfiltered. The verdict cannot see
    the difference, so the number is reported and the caller supplies the
    expectation.
    """
    result = classify_run(_XDIST)
    assert result.collected == 356
    assert result.verdict == "usable"
    assert "collected=356" in result.headline()


def test_the_collected_population_is_read_from_a_serial_collection_line() -> None:
    """Without workers pytest writes the count differently, and says deselected."""
    result = classify_run(_SERIAL)
    assert result.collected == 24
    assert result.counts["deselected"] == 21
    assert result.counts["passed"] == 3


def test_a_lost_worker_run_keeps_the_population_from_its_own_banner() -> None:
    """The banner's figure is authoritative there and must not be overwritten.

    It states how many were collected against how many never reported, which is
    a stronger statement than the worker line and belongs to the same event.
    """
    result = classify_run(_CRASHED)
    assert (result.collected, result.unreported) == (317, 2)
    assert "unreported=2/317" in result.headline()


def test_a_run_with_no_collection_line_reports_no_population() -> None:
    """Absent is not zero, and a headline must not invent a number it lacks."""
    result = classify_run(_CLEAN)
    assert result.collected == 0
    assert "collected=" not in result.headline()
