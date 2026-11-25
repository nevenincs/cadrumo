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

from .settling import settle_until

if TYPE_CHECKING:
    from ..profile.overview import ProfileManagerScreen

__all__ = ["wait_until_settled"]


async def wait_until_settled(app: ProfileManagerScreen, pilot) -> None:
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

    Two settled rounds at minimum, and the second is not padding. The
    settling handler clears the flag and then repaints, and a rebuild mounts
    widgets that the round which delivered the completion never walked.
    Reading immediately after the flag cleared can therefore see the tables
    the redraw has already replaced.

    The wait is bounded by time, not by a count of pauses: a write through
    the real encrypted door runs key derivation on a worker thread, and on a
    loaded machine that outlasts any fixed number of pauses.

    Deliberately not a :meth:`textual.worker.WorkerManager.wait_for_complete`:
    joining the write worker directly would hold the UI task against a
    dismissal that can only come from the pilot. Callers waiting for a
    page to *appear* are asking a different question and must not use
    this.
    """
    await settle_until(
        pilot, lambda: app._pending_write is None, "the page to settle its write in flight", workers=False
    )
