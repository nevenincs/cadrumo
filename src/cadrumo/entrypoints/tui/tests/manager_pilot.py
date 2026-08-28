"""Waiting for the profile manager to finish reacting, under the pilot.

Saving a dialog on the manager page only *starts* the work: a write runs
on a worker thread, and the page repaints when its completion is
delivered back to Textual's UI task. A test that
read the page straight after the press would read it one beat early, so
every pilot-driven manager test needs a wait — and four of them had grown
their own, with semantics that disagreed.

The disagreement mattered. One of those waits polled for the text it
expected to appear, which is a shape that can only hang or pass: it
cannot fail on the value that is actually there, and it was satisfied by
the progress line the press writes synchronously, before the worker had
run at all. :func:`wait_until_settled` waits on *state* instead and returns without
reading the page, so the caller asserts against whatever the page settled
on and fails on the real content.

The page's other asynchronous surface — a footer that recomposes its
children in answer to a bindings change — is deliberately not covered
here. It carries no pending flag to watch, so waiting for it is a
different question answered by draining a reading to a fixed point, and
it lives beside the one test that asks it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..profile.overview import ProfileManagerApp

__all__ = ["wait_until_settled"]

_SETTLE_BARRIER_LIMIT = 400
"""How many barriers the page gets to settle within before the test gives up.

A cap, not a wait: this bounds a failure rather than a success. A write
through the real encrypted door settles within single-digit barriers even
on a loaded machine, because a barrier yields to the event loop rather
than spinning on it, so exhausting a bound this size means the page is
not going to settle at all — which is a finding about the page rather
than about the machine's speed.
"""


async def wait_until_settled(app: ProfileManagerApp, pilot) -> None:
    """Drain the page's messages until no background work is left in flight.

    Waits on the page's own state — that it holds no unfinished write —
    rather than on an expected wording. That distinction is the point of
    this helper: the flag is cleared by the settling handler, which runs
    on the UI task and repaints before it returns, so a cleared flag is
    evidence the outcome has reached the page. A wait for particular text
    is evidence of nothing, because the press writes a progress line
    synchronously and any poll for "something is displayed" is satisfied
    by it.

    Nothing is returned, so the caller reads the page itself and asserts
    against what is really there. A page that never settles fails here
    naming what it was still holding, rather than falling through to an
    assertion that reports the progress line as though it were the
    outcome.

    Two barriers at minimum, and the second is not padding. The settling
    handler clears the flag and then repaints, and a rebuild mounts
    widgets that the barrier which delivered the completion never walked —
    :meth:`textual.pilot.Pilot.pause` only waits on the widgets present
    when it was posted. Reading immediately after the flag cleared can
    therefore see the tables the redraw has already replaced.

    Deliberately not a :meth:`textual.worker.WorkerManager.wait_for_complete`:
    joining the write worker directly would hold the UI task against a
    dismissal that can only come from the pilot. Callers waiting for a
    page to *appear* are asking a different question and must not use
    this.
    """
    for _ in range(_SETTLE_BARRIER_LIMIT):
        await pilot.pause()
        write = app._pending_write
        if write is None:
            await pilot.pause()
            return
    message = (
        f"the page never settled: a write was still in flight after {_SETTLE_BARRIER_LIMIT} drained message queues"
    )
    raise AssertionError(message)
