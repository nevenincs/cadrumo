"""Stamp the host's load into the output stream just before a timeout fires.

``pyproject.toml`` sets a per-test ``timeout = 300``. That ceiling is a
WALL-CLOCK bound, and this repository's suites run on a box shared with the
operator's interactive session, several concurrent agent fleets, and
self-hosted CI runners. Under saturation a legitimately slow test crosses the
ceiling and pytest-timeout prints a stack dump of wherever the interpreter
happened to be -- which reads as a deadlock in the code under test. Nothing in
that traceback records how loaded the machine was, so the red cannot be
re-triaged later and reaches a ledger as a specific, plausible, entirely
fictitious defect WITH a traceback attached. This module makes every red in
that class interpretable by recording what the machine was doing as the ceiling
was approached.

What the stamp claims, exactly
------------------------------
The reading is taken at ``T-minus-lead``, roughly two seconds before the
ceiling -- NOT at the instant of the fire. That distinction is not pedantry: a
reader finding this line above a timeout traceback will otherwise take it for a
fire-time reading, and the two are different claims. Fire-time is not
obtainable, because the code that fires is pytest-timeout's own and it exits
the process rather than returning; T-minus-lead is the closest honest
approximation, and the lead is printed in the stamp itself so the gap is
visible rather than assumed. What the stamp supports is "the box was at 94%
with 130 python processes seconds before this test missed its deadline". What
it does not support is a claim about the instant of the fire.

Two earlier remedies for this defect would have passed review and done nothing
------------------------------------------------------------------------------
Recorded because the pattern is attractive and a third author will otherwise
reach for a third instance of it. The first proposal was to convert the ceiling
from wall-clock to CPU-time -- which cannot fire on the failure the ceiling
exists to catch, since a wedged or deadlocked process burns almost no CPU. The
second was to attach the stamp in ``pytest_runtest_makereport`` -- which cannot
fire on the platform whose saturation it measures, for the reason set out
immediately below. Both were instruments definitionally blind to their own
target, and both looked like strict improvements. Before changing the mechanism
here, ask first on which platform and on which failure the replacement actually
executes.

Why the reading is taken from a pre-fire timer rather than from a report hook
-----------------------------------------------------------------------------
The obvious home for this is ``pytest_runtest_makereport``, and it is the wrong
one. pytest-timeout selects its firing mechanism from the platform: it uses
``SIGALRM`` where that exists, and the THREAD method everywhere else. Windows
has no ``SIGALRM``, so every run on this box takes the thread method -- and the
thread method dumps stacks and then calls ``os._exit(1)`` directly. That call
terminates the interpreter without unwinding: no report hook, no teardown, no
``atexit``, and no buffered stream is flushed. A stamp attached at
report-render time would therefore be a structural no-op on precisely the host
whose contention it exists to explain, while passing on Linux CI (where the
signal method does reach the report hooks). A gate that only runs where the
problem is absent is worse than no gate, because it reads as coverage.

The value of the reading is also entirely in WHEN it is taken. Sampling at
report time -- or at setup time -- measures a different machine than the one
that missed the deadline. So the reading is taken on a timer armed to fire a
couple of seconds BEFORE the ceiling.

Where it is written matters just as much as when. A test runs under pytest's
fd-level capture, so a plain write to file descriptor 2 lands in a capture
buffer that ``os._exit`` then discards -- the stamp would be taken correctly
and thrown away. pytest-timeout solves this for its own stack dump by writing
through ``item.config.get_terminal_writer()``, which holds the ORIGINAL
stream rather than the captured one, and flushing before it exits. This module
writes through the same door, so the stamp lands a couple of seconds above the
``Timeout`` separator in the very same output the traceback appears in. Writing
to the raw descriptor is kept only as a fallback for the case where no terminal
writer can be reached.

pytest-timeout exposes exactly the seam this needs:
``pytest_timeout_set_timer`` and ``pytest_timeout_cancel_timer`` are
``firstresult`` hookspecs whose own implementations are registered
``trylast``. An implementation that returns ``None`` runs first, may arm its
own timer, and still lets pytest-timeout install the real one -- so this
module observes the ceiling without altering it.

Nothing here may change a test's outcome. Every reading is taken inside a
``try``/``except`` and a failure to measure degrades to a stamp that says so,
because a diagnostic that can itself fail a test is a new defect rather than a
tool for finding one.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pytest

#: Greppable prefix. Every stamp this module writes starts with it, so a red
#: run's log can be filtered to the load readings alone.
STAMP_PREFIX = "CADRUMO-HOST-LOAD"

#: How far ahead of the ceiling the reading is taken. Long enough to complete
#: the sample and the write before ``os._exit`` lands, short enough that the
#: reading still describes the machine that missed the deadline.
_STAMP_LEAD_SECONDS = 2.0

#: Blocking CPU sample window. ``psutil.cpu_percent`` returns 0.0 on its first
#: interval-less call (it has no previous reading to difference against), so an
#: explicit interval is required for the number to mean anything at all.
_CPU_SAMPLE_SECONDS = 0.25

_TIMER_ATTRIBUTE = "cadrumo_host_load_timer"


def _python_process_count(psutil: Any) -> str:
    """Return the count of live ``python*`` processes, or ``"?"`` if unmeasurable.

    This is the number that actually discriminates "the box is busy" from "the
    code hung": a fleet of agents each running a suite shows up here and
    nowhere else. It is measured separately from the rest of the reading, and
    guarded separately, because enumerating every process is the slowest and
    most failure-prone part of the sample and must not be able to cost us the
    cheap fields.
    """
    try:
        return str(sum(1 for proc in psutil.process_iter(["name"]) if (proc.info["name"] or "").startswith("python")))
    except Exception:
        return "?"


def format_host_load_reading(*, nodeid: str) -> str:
    """Return the one-line host-load stamp for ``nodeid``.

    The line is deliberately flat ``key=value`` text rather than JSON: it is
    read by a human triaging a red run and by ``rg``, both of which are better
    served by one greppable line than by a nested document.

    Args:
        nodeid: The pytest node id of the test whose ceiling is about to fire.

    Returns:
        A single line with no trailing newline. When the host cannot be
        sampled at all the line still identifies the node and states the
        reason, so an unmeasurable host is distinguishable from a quiet one.
    """
    try:
        import psutil
    except ImportError as exc:  # pragma: no cover - psutil is a pinned dev dependency
        return f"{STAMP_PREFIX} {nodeid} unavailable reason={type(exc).__name__}"

    try:
        cpu_percent = psutil.cpu_percent(interval=_CPU_SAMPLE_SECONDS)
        logical_cpus = psutil.cpu_count(logical=True)
        memory_percent = psutil.virtual_memory().percent
        process_count = len(psutil.pids())
    except Exception as exc:
        return f"{STAMP_PREFIX} {nodeid} unavailable reason={type(exc).__name__}"

    return (
        f"{STAMP_PREFIX} {nodeid} "
        f"cpu={cpu_percent:.1f}% "
        f"cpus={logical_cpus} "
        f"mem={memory_percent:.1f}% "
        f"processes={process_count} "
        f"python_processes={_python_process_count(psutil)} "
        f"lead={_STAMP_LEAD_SECONDS:.1f}s"
    )


def _emit(item: pytest.Item) -> None:
    """Sample the host and write the stamp where the timeout traceback goes.

    The terminal writer is the same channel pytest-timeout uses for its stack
    dump, and for the same reason: it holds the original stream, so it is not
    swallowed by the fd-level capture that is active while a test runs, and an
    explicit flush puts the bytes past Python's buffers before ``os._exit`` can
    discard them. Writing to the raw descriptor is the fallback for a
    configuration that exposes no terminal writer.
    """
    line = format_host_load_reading(nodeid=item.nodeid)
    try:
        terminal = item.config.get_terminal_writer()
    except Exception:
        terminal = None
    if terminal is not None:
        try:
            terminal.line(line)
            terminal.flush()
            return
        except Exception:  # noqa: S110 - fall through to the raw descriptor
            pass
    try:
        os.write(2, (line + "\n").encode("utf-8", errors="replace"))
    except Exception:
        return


def arm_pre_timeout_stamp(item: pytest.Item, settings: Any) -> None:
    """Arm the pre-fire host-load stamp for ``item``; never claim the hook.

    Returns ``None`` unconditionally. ``pytest_timeout_set_timer`` is a
    ``firstresult`` hookspec, so returning a value here would stop the hook
    call and pytest-timeout's own ``trylast`` implementation would never
    install the real timer -- silently disabling the ceiling this module exists
    to annotate.

    Args:
        item: The test item whose ceiling is being set.
        settings: pytest-timeout's per-item settings; ``settings.timeout`` is
            ``None`` or non-positive when no ceiling applies.
    """
    timeout = getattr(settings, "timeout", None)
    if not timeout or timeout <= 0:
        return

    # For a long ceiling this lands a fixed couple of seconds early; for a very
    # short one a fixed lead would be negative, so it falls back to a fraction
    # of the ceiling and still arrives before the fire.
    delay = max(timeout - _STAMP_LEAD_SECONDS, timeout * 0.9)
    timer = threading.Timer(delay, _emit, (item,))
    timer.daemon = True
    timer.name = f"cadrumo-host-load {item.nodeid}"
    setattr(item, _TIMER_ATTRIBUTE, timer)
    timer.start()


def disarm_pre_timeout_stamp(item: pytest.Item) -> None:
    """Cancel the stamp timer for ``item``; never claim the hook.

    Returns ``None`` for the same reason :func:`arm_pre_timeout_stamp` does:
    ``pytest_timeout_cancel_timer`` is ``firstresult``, and claiming it would
    leave pytest-timeout's real timer running past the test.

    Cancelling is tolerant of never having been armed -- pytest-timeout's own
    cancel counterpart documents that it can be reached without its setup
    having run (a ``skipif`` raised during setup, for instance).
    """
    timer = getattr(item, _TIMER_ATTRIBUTE, None)
    if timer is None:
        return
    try:
        timer.cancel()
    finally:
        setattr(item, _TIMER_ATTRIBUTE, None)
