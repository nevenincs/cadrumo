"""Observe how many SQL transactions a composed secure-object write spans.

A service that mutates several encrypted catalogues can persist them either as
one unit of work or as a sequence of independent saves. The two are
indistinguishable from the returned value and from the final on-disk state; they
differ only in what survives a failure part-way through. This recorder makes the
difference observable by attaching to the live
:class:`~sqlalchemy.engine.Engine` the repositories already use, so the counted
sequence is the production statement stream -- no connection is wrapped,
replaced, or stubbed.

``before_cursor_execute`` sees every statement -- expanded to one marker per ROW,
because the write funnel is set-based -- and the DBAPI ``commit`` event
marks each transaction boundary; a commit falling between two secure-object
writes is exactly the seam a crash exploits, because whichever catalogue
committed first keeps its half of the change.

Pair every "zero commits between writes" assertion with an anti-tautology case
that persists the same catalogues through two independent saves and asserts the
recorder reports a non-zero count. Without it, a recorder that could never
report a seam would make the primary assertion vacuous.

That pairing is necessary and NOT sufficient, and the gap has bitten once. An
anti-tautology case proves the recorder can still FIRE; it says nothing about
the granularity at which it fires. When the write funnel became set-based, a
batch of N rows became one statement, and a statement-counting recorder went on
reporting seams correctly while losing the ability to tell four rows from one --
so the anti-tautology case kept passing while a group-size assertion became
unsatisfiable. Resolution can narrow silently underneath a proof that only
checks for a pulse. When something changes how many statements a write costs,
re-ask what every count here MEANS, not merely whether it still moves.

The cheap check, worth applying to any gate and not just this one: ask what
would have to change in the system UNDERNEATH it for its number to keep being
produced while meaning something else. Here that change is "the storage layer
batches", and nothing about it is visible from inside the gate. Both failures
of this kind found so far shared a shape -- the assertion was true of the world
and false of its own NAME. Neither was lying; the name promised a property the
measurement had quietly stopped delivering, which is why neither was findable
by reading the gate and both surfaced only when something else broke nearby.

Standing hazard, unguarded on purpose. This recorder and
``test_secure_object_write_batching`` now encode OPPOSITE expectations of one
funnel: that test asserts a batch collapses to a single ``INSERT``, while this
counts the rows inside it. Both are correct today. If the funnel changes again --
back to per-row, or chunked above some size -- that test fails LOUDLY while this
recorder silently changes what every atomicity assertion in the suite means, and
the silent one is the dangerous one. No guard is offered because any guard would
be another tally with the same exposure; the note is here instead, where a
reader meets it at the moment they would change the funnel.

See Also:
    :func:`~cadrumo.tests.secure_sql.isolated_runtime_profile`:
        Yields the encrypted-SQLite profile whose ``repository.engine`` this
        recorder attaches to.
"""

from __future__ import annotations

from collections.abc import Generator, Sized
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import event

if TYPE_CHECKING:  # pragma: no cover - typing-only engine import
    from sqlalchemy.engine import Engine

_COMMIT_MARKER = "<commit>"
_WRITE_MARKER = "write"


class WriteUnitRecorder:
    """Interleaved record of secure-object write statements and real commits.

    Attach to the engine a test's repositories already share, record across the
    operation under test, then read :meth:`commits_between_writes`.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self.events: list[str] = []

    def _on_statement(
        self,
        _conn: object,
        _cursor: object,
        statement: str,
        parameters: object = None,
        _context: object = None,
        executemany: bool = False,
    ) -> None:
        """Record one marker per secure-object ROW written, not per statement.

        The storage layer writes set-based SQL: a batch of N rows is one
        ``INSERT`` executemany rather than N separate statements. Counting
        statements therefore stopped answering the question this recorder
        exists to answer -- it reported a five-row atomic batch as a single
        write, which reads identically to five rows written one at a time and
        makes a "these rows shared a transaction" assertion unsatisfiable
        however correct the code is. The rows are what a crash can tear apart,
        so the rows are what is counted.
        """
        collapsed = " ".join(statement.split()).upper()
        if "SECURE_OBJECTS" not in collapsed or not collapsed.startswith(("INSERT", "UPDATE")):
            return
        rows = len(parameters) if executemany and isinstance(parameters, Sized) else 1
        self.events.extend([_WRITE_MARKER] * rows)

    def _on_commit(self, _conn: object) -> None:
        self.events.append(_COMMIT_MARKER)

    @contextmanager
    def recording(self) -> Generator[None]:
        """Listen on the engine for the duration of the block."""
        event.listen(self._engine, "before_cursor_execute", self._on_statement)
        event.listen(self._engine, "commit", self._on_commit)
        try:
            yield
        finally:
            event.remove(self._engine, "before_cursor_execute", self._on_statement)
            event.remove(self._engine, "commit", self._on_commit)

    def write_count(self) -> int:
        """Return how many secure-object writes were observed."""
        return self.events.count(_WRITE_MARKER)

    def write_groups(self) -> tuple[int, ...]:
        """Return the number of secure-object writes in each transaction, in order.

        ``commits_between_writes`` answers "was this one unit of work?" and is the
        right question when every write belongs together. A flow with a
        DELIBERATE second boundary -- a projection that must run only after the
        primary state commits -- needs the finer view: the group count says how
        many transactions there were, and each group's size says which writes
        shared one. Collapsing four separate saves into one batch changes the
        group shape even though a commit still legitimately falls between the
        batch and the projection.
        """
        groups: list[int] = []
        pending = 0
        for entry in self.events:
            if entry == _WRITE_MARKER:
                pending += 1
            elif pending:
                groups.append(pending)
                pending = 0
        if pending:
            groups.append(pending)
        return tuple(groups)

    def commits_between_writes(self) -> int:
        """Return how many commits fall between the first and last write.

        Zero means every secure-object write in the observed window landed in one
        transaction. Reads before and after the window commit too, so only the
        span between the first and last write is counted.

        Raises:
            AssertionError: If no secure-object write was observed at all, which
                would otherwise report zero and read as success.
        """
        write_positions = [index for index, entry in enumerate(self.events) if entry == _WRITE_MARKER]
        if not write_positions:
            raise AssertionError("no secure-object write was observed")
        span = self.events[write_positions[0] : write_positions[-1] + 1]
        return span.count(_COMMIT_MARKER)


__all__ = ["WriteUnitRecorder"]
