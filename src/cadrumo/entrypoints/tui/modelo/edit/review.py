"""The mandatory review gate between staging an edit and submitting it.

Every edit passes through here. The gate assembles what the operator is about
to submit -- every changed semantic address, scalar and row alike -- and hands
back the contract's own preflight verdict alongside the surface's own blockers.

WHAT THIS GATE DOES NOT DO, and the distinction is the point: it does not
approve anything. A green preflight is review material, not authorization; the
contract's execution path independently repeats every concurrency and
capability check at the guarded commit point. A gate that reported "approved"
would be fabricating a supervisor decision it has no standing to make, and the
operator would read it as a promise the apply will succeed.

TWO KINDS OF BLOCKER, kept apart because they are resolved differently:

- SURFACE blockers are unresolved lexemes -- text the operator typed that the
  contract could not parse. Nothing is staged for them, so submitting would
  file the value the field held before, while the screen shows the new text.
  The operator resolves these by fixing or discarding the entry.
- CONTRACT findings come from preflight and describe the staged submission
  itself. The operator resolves these by changing what they declared.

An empty edit is not reviewable. Offering review over nothing invites the
operator to confirm a submission with no intents, which either does nothing or
looks like it did something -- and neither is an honest outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .....application.modelo.edit_session import ModeloEditSession
    from .....domain.modelos.calculation_revision import CalculationRevisionCatalogue
    from .....domain.modelos.work_unit import WorkUnitCatalogue
    from .fields import ScalarFieldSet, UnresolvedLexeme
    from .rows import RepeatedRowSet, RowKey

__all__ = ["ReviewGate", "ReviewRefusal", "ReviewSummary", "UnsavedChoice"]


@dataclass(frozen=True, slots=True)
class ReviewRefusal:
    """Why review could not proceed, in terms the surface can render.

    ``message_key`` is a localisation key; ``blocking_casilla_ids`` names the
    controls the operator must return to. Naming them is what makes the
    refusal actionable rather than merely negative -- a gate that says "fix
    the errors" without saying where is a gate the operator has to search
    behind.
    """

    message_key: str
    blocking_casilla_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    """Everything the operator is about to submit, addressed semantically.

    Addresses rather than widgets: the summary is read after the operator has
    scrolled, filtered and re-rendered, and a positional reference would name
    whatever now sits where the edit used to be.
    """

    changed_casilla_ids: tuple[str, ...]
    changed_row_keys: tuple[RowKey, ...]
    preflight: object
    """The contract's own preflight result, passed through unmodified.

    Deliberately not narrowed or re-shaped here: the caller renders it, and a
    surface-local summary of a contract verdict would be a second reading of
    the same facts, free to disagree with the first.
    """


class UnsavedChoice:
    """The two honest answers to leaving with staged edits.

    A third option -- saving silently on the way out -- is deliberately
    absent. An edit the operator did not review is an edit they did not
    approve, and a surface that submitted one on navigation would file a
    declaration nobody confirmed.
    """

    STAY = "stay"
    ABANDON = "abandon"


@dataclass(slots=True)
class ReviewGate:
    """The one path from staged edits to a reviewable submission."""

    _session: ModeloEditSession
    _fields: ScalarFieldSet
    _rows: RepeatedRowSet

    @classmethod
    def over(cls, session: ModeloEditSession, fields: ScalarFieldSet, rows: RepeatedRowSet) -> ReviewGate:
        """Build the gate over one session and its two control sets."""
        return cls(_session=session, _fields=fields, _rows=rows)

    def surface_blockers(self) -> tuple[UnresolvedLexeme, ...]:
        """Return the unresolved lexemes standing between here and review."""
        return self._fields.unresolved()

    def review(
        self,
        *,
        work_catalogue: WorkUnitCatalogue,
        calculation_catalogue: CalculationRevisionCatalogue,
    ) -> ReviewSummary | ReviewRefusal:
        """Assemble the submission for review, or refuse with a reason.

        Refuses BEFORE calling preflight when the surface already knows the
        submission is not what the screen shows: sending it anyway would spend
        a real recheck on a request the operator did not mean.
        """
        blockers = self.surface_blockers()
        if blockers:
            return ReviewRefusal(
                message_key="flows.modelo_edit.review.unresolved_entries",
                blocking_casilla_ids=tuple(item.casilla_id for item in blockers),
            )
        if not self._session.is_dirty:
            return ReviewRefusal(message_key="flows.modelo_edit.review.nothing_staged")

        return ReviewSummary(
            changed_casilla_ids=self._session.dirty_casilla_ids(),
            changed_row_keys=self._rows.staged_keys(),
            preflight=self._session.review(
                work_catalogue=work_catalogue,
                calculation_catalogue=calculation_catalogue,
            ),
        )

    def leaving_with_unsaved_changes(self) -> bool:
        """Whether navigating away now would discard staged work.

        The surface asks this before leaving, and offers only
        :class:`UnsavedChoice`'s two answers.
        """
        return self._session.is_dirty and not self._session.is_closed

    def abandon(self) -> None:
        """Take the abandon branch: discard every staged edit and close."""
        self._session.abandon()
