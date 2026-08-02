"""Observe how many SQL transactions a composed secure-object write spans.

A service that mutates several encrypted catalogues can persist them either as
one unit of work or as a sequence of independent saves. The two are
indistinguishable from the returned value and from the final on-disk state; they
differ only in what survives a failure part-way through. This recorder makes the
difference observable by attaching to the live
:class:`~sqlalchemy.engine.Engine` the repositories already use, so the counted
sequence is the production statement stream -- no connection is wrapped,
replaced, or stubbed.

``before_cursor_execute`` sees every statement, and the DBAPI ``commit`` event
marks each transaction boundary; a commit falling between two secure-object
writes is exactly the seam a crash exploits, because whichever catalogue
committed first keeps its half of the change.

Pair every "zero commits between writes" assertion with an anti-tautology case
that persists the same catalogues through two independent saves and asserts the
recorder reports a non-zero count. Without it, a recorder that could never
report a seam would make the primary assertion vacuous.

See Also:
    :func:`~cadrumo.tests.secure_sql.isolated_runtime_profile`:
        Yields the encrypted-SQLite profile whose ``repository.engine`` this
        recorder attaches to.
"""

from __future__ import annotations

from collections.abc import Iterator
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

    def _on_statement(self, _conn: object, _cursor: object, statement: str, *_args: object) -> None:
        collapsed = " ".join(statement.split()).upper()
        if "SECURE_OBJECTS" in collapsed and collapsed.startswith(("INSERT", "UPDATE")):
            self.events.append(_WRITE_MARKER)

    def _on_commit(self, _conn: object) -> None:
        self.events.append(_COMMIT_MARKER)

    @contextmanager
    def recording(self) -> Iterator[None]:
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
