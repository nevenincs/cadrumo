"""Repeated-row editing state for the Modelo editor's C3 destination.

Rows are addressed by the natural key they already carry -- the member or
counterparty identity the declaration itself names -- and never by where they
sit on screen. A widget position is not an identity: it changes when a row
above is removed, when a filter is applied, and when the surface re-renders,
and a row edited by position after any of those edits the wrong row.

WHOLE-ROW OPERATIONS ONLY. A row is added, replaced or removed as a unit,
because the contract addresses it that way and because a partially applied row
has no meaning in a declaration: half a counterparty is not a smaller
counterparty, it is a malformed one.

MOVE IS NOT AVAILABLE, AND THAT IS NOT AN OMISSION. The contract's intent kind
documents why: every row-producer sorts by a content key before assigning
fichero occurrence numbers, so two calls supplying the same rows in different
orders render byte-identical output. There is no declared order for AEAT to
read, so a move would change nothing in the filing while implying to the
operator that it had. This module therefore offers no reorder and says so,
rather than offering one that quietly does nothing.

A DRAFT ROW IS NOT SUBMITTED UNTIL IT IS COMPLETE. A row under construction
lives here with a client correlation and no intent staged; only when it carries
its natural key and its payload does it reach the session. Staging an
incomplete draft would submit a declaration the operator had not finished
writing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .....application.modelo.edit_session import ModeloEditSession
    from .....domain.modelos.calculation_revision import ModeloDetailRow

__all__ = ["DraftRow", "RepeatedRowSet", "RowKey"]


@dataclass(frozen=True, slots=True)
class RowKey:
    """The natural-key address of one repeated row.

    Both halves are the declaration's own identity, never minted here: the
    kind is the row type the contract discriminates on, and the key is the
    business identity the row already carries.
    """

    detail_row_kind: str
    natural_key: str


@dataclass(slots=True)
class DraftRow:
    """One row the operator is still writing, with no persistence identity yet.

    Held here and NOT in the session, because an unfinished row is a surface
    concern: the contract has nothing to say about a declaration that does not
    yet name itself. It reaches the session only through
    :meth:`RepeatedRowSet.commit_draft`, and only when complete.
    """

    correlation_id: str
    detail_row_kind: str
    natural_key: str | None = None
    row: ModeloDetailRow | None = None

    @property
    def is_complete(self) -> bool:
        """Whether this draft carries both an identity and a payload."""
        return bool(self.natural_key) and self.row is not None


@dataclass(slots=True)
class RepeatedRowSet:
    """The repeated-row controls for one admitted edit.

    Owns no widgets. The part that must be correct is the addressing, so it is
    separated to be driven directly: a row set whose identity discipline can
    only be exercised by mounting an application is a row set whose identity
    discipline is mostly unproven.
    """

    _session: ModeloEditSession
    _drafts: dict[str, DraftRow] = field(default_factory=dict, init=False)

    @classmethod
    def for_session(cls, session: ModeloEditSession) -> RepeatedRowSet:
        """Build an empty row set over an open session."""
        return cls(_session=session)

    def stage(self, row: ModeloDetailRow, *, detail_row_kind: str) -> RowKey:
        """Add or replace one complete row, addressed by its own natural key.

        One method for add and replace, because whether the key is already
        declared is a fact about the work unit rather than about the
        operator's gesture. Asking the surface to choose would ask it to know
        something it would have to guess.

        Takes the row and returns the address it landed under, rather than
        accepting an address beside it. A caller supplying both could supply a
        key describing a different row than the one it passed, and the
        contract addresses by key while the row carries its own identity.
        """
        return RowKey(detail_row_kind=detail_row_kind, natural_key=self._session.stage_row(detail_row_kind, row))

    def remove(self, row: ModeloDetailRow, *, detail_row_kind: str) -> RowKey:
        """Stage the removal of one declared row.

        A row has no ambiguous middle state between declared and absent, so an
        absent key is sufficient to express removal and no separate
        "explicitly deleted" axis is needed.

        Takes the row for the same reason :meth:`stage` does, and because the
        joined key alone cannot yield the identity components the operation
        payload addresses by.
        """
        return RowKey(detail_row_kind=detail_row_kind, natural_key=self._session.remove_row(detail_row_kind, row))

    def revert(self, key: RowKey) -> bool:
        """Discard the operator's own staging for one row.

        Distinct from :meth:`remove`, which submits a deletion. This withdraws
        the edit so the declared row stands as it was.
        """
        return self._session.discard_row(key.detail_row_kind, key.natural_key)

    def staged_keys(self) -> tuple[RowKey, ...]:
        """Return every staged row address, in canonical order."""
        return tuple(
            RowKey(detail_row_kind=kind, natural_key=natural) for kind, natural in self._session.dirty_row_keys()
        )

    def open_draft(self, correlation_id: str, detail_row_kind: str) -> DraftRow:
        """Begin a row the operator has not finished writing.

        Idempotent on the correlation, so a re-render that reopens the same
        draft does not produce a second row. Nothing is staged yet.
        """
        existing = self._drafts.get(correlation_id)
        if existing is not None:
            return existing
        draft = DraftRow(correlation_id=correlation_id, detail_row_kind=detail_row_kind)
        self._drafts[correlation_id] = draft
        return draft

    def drafts(self) -> tuple[DraftRow, ...]:
        """Return every open draft, in the order it was opened."""
        return tuple(self._drafts.values())

    def commit_draft(self, correlation_id: str) -> RowKey | None:
        """Stage a completed draft, or refuse an incomplete one.

        Returns ``None`` when the draft is not yet complete, leaving it open
        for the operator to finish. Refusing here rather than staging a
        partial row is the whole reason drafts exist: the session accepts only
        whole rows, and a half-written declaration must not reach it.
        """
        draft = self._drafts.get(correlation_id)
        if draft is None or not draft.is_complete:
            return None
        assert draft.natural_key is not None
        assert draft.row is not None
        key = RowKey(
            detail_row_kind=draft.detail_row_kind,
            natural_key=self._session.stage_row(draft.detail_row_kind, draft.row),
        )
        del self._drafts[correlation_id]
        return key

    def abandon_draft(self, correlation_id: str) -> bool:
        """Discard one unfinished row, returning whether it was open."""
        return self._drafts.pop(correlation_id, None) is not None
