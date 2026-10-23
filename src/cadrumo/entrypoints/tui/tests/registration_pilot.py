"""Pilot helpers shared by the registration screen's tests.

Creation and recovery enrolment run real key derivation, and a pushed screen
is active before its ``compose`` has run, so a test waits for the screen and
for a widget laid out on it before it reads or clicks anything. Every wait is
a ``settle_until`` bounded by a wall-clock deadline: key derivation on a
contended host outlasted a fixed thirty-second budget, and a slow host is not
a failure of the screen under test.
"""

from __future__ import annotations

import sys
import threading
import traceback

from textual.css.query import NoMatches
from textual.pilot import Pilot
from textual.widget import Widget

from .settling import SETTLE_TIMEOUT_SECONDS, SettleTimeoutError, settle_until


def _thread_stacks() -> str:
    """Every live thread's stack, so a wait that expires says what it waited on."""
    frames = sys._current_frames()
    names = {thread.ident: thread.name for thread in threading.enumerate()}
    return "\n".join(
        f"--- {names.get(ident, ident)} ---\n{''.join(traceback.format_stack(frame)[-12:])}"
        for ident, frame in frames.items()
    )


def _laid_out[ResultT](pilot: Pilot[ResultT], screen_type: type, selector: str) -> bool:
    """Whether ``screen_type`` is active and ``selector`` has a non-empty region on it."""
    screen = pilot.app.screen
    if not isinstance(screen, screen_type):
        return False
    try:
        widget: Widget = screen.query_one(selector, Widget)
    except NoMatches:
        return False
    return widget.region.area > 0


async def wait_for_screen[ResultT](
    pilot: Pilot[ResultT],
    screen_type: type,
    *,
    composed: str,
    deadline_seconds: float = SETTLE_TIMEOUT_SECONDS,
) -> bool:
    """Wait for ``screen_type`` to be active AND for ``composed`` to be laid out on it.

    A pushed screen is active before its ``compose`` has run, and a composed
    widget has no place on screen until the next layout pass. A click sent
    in either window lands on nothing and presses nothing, so the widget
    having a non-empty region is what proves the screen can be driven.

    Returns False when the deadline passes first, after printing every
    thread's stack to stderr: the wait expires below the per-test timeout on
    purpose, so a stall reports what the threads were doing instead of the
    timeout killing the worker silently.
    """
    try:
        await settle_until(
            pilot,
            lambda: _laid_out(pilot, screen_type, composed),
            f"{screen_type.__name__} with {composed} laid out",
            workers=False,
            timeout=deadline_seconds,
        )
    except SettleTimeoutError:
        if _laid_out(pilot, screen_type, composed):
            return True
        print(
            f"{screen_type.__name__} did not appear within {deadline_seconds:g}s\n{_thread_stacks()}", file=sys.stderr
        )
        return False
    return True
