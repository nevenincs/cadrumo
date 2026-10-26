"""One way to say an instrument did not read part of its own corpus.

Twelve places across nine dev modules had grown the same block: a walk skips a
file it cannot read, and the skip is announced so an empty result is not mistaken
for a clean one. Writing it a thirteenth time is worse than sharing it - the
wording drifts, and a reader comparing two reports cannot tell whether they mean
the same thing.

What must NOT be shared is the consequence. "A key that is never seen declared
looks unused" and "a symbol only this test imports is listed unreached in error"
are different facts, and flattening them into one generic sentence would remove
the only part a reader acts on. So the consequence is the caller's, passed in;
the shape, the count and the file list are this module's.

This reports; it never refuses. A walk over a tree that a sibling process is
editing must survive a half-written file, and two existing tests in this
repository were written to enforce exactly that. Refusal belongs at the call
site, where the difference between a broken tracked file and a racing one is
known.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence


def format_unread_notice(instrument: str, consequence: str, unread: Sequence[str]) -> str:
    """Return the one-line notice for inputs an instrument could not read.

    Args:
        instrument: The reporting instrument, so a reader knows which run is
            incomplete when several write to the same stream.
        consequence: What the omission costs, in the caller's own words. This is
            the part a reader acts on and the reason this is a parameter.
        unread: The inputs that were skipped, each already describing itself.

    Returns:
        The notice, terminated by a newline. Empty when nothing was skipped, so
        a caller can write it unconditionally without emitting a blank line.
    """
    if not unread:
        return ""
    return f"{instrument}: {len(unread)} input(s) could not be read; {consequence}: {sorted(unread)!r}" + chr(10)


def report_unread(instrument: str, consequence: str, unread: Sequence[str]) -> None:
    """Announce the inputs an instrument could not read, if there were any.

    Silent when ``unread`` is empty. A notice that fired on every run would tell
    a reader nothing, which is the failure mode this reporting exists to avoid
    reproducing.
    """
    notice = format_unread_notice(instrument, consequence, unread)
    if notice:
        sys.stderr.write(notice)
