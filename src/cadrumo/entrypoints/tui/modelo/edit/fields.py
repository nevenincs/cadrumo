"""Scalar editing controls for the Modelo editor's C3 destination.

Renders one control per casilla the ADMISSION permits editing, and no others.
The permitted set is read from the session rather than from a registry or a
workspace projection: an admission is a time-bounded authority, and a control
built from anything else would offer an edit the contract may already refuse.

Every lexeme the operator types goes straight back to the session, which parses
it through the Edit Contract's own parse request. This module never interprets
a lexeme, never coerces one, and never decides what a value means. It holds
exactly one thing the application layer cannot: what the operator has typed but
not yet resolved.

FOUR DISTINCTIONS THIS MODULE MUST NOT COLLAPSE, because each is a different
statement about the filing and only one of them is "no answer":

- UNCHANGED -- the operator never touched the control. No intent is staged.
- ZERO or FALSE -- the operator declared zero, or declared not-applicable.
  Both are answers, and both stage a typed value. A control that treated an
  empty-looking value as "nothing" would silently drop a declaration.
- CLEARED -- the operator removed a declaration that existed. This stages a
  removal, which is not the same as never having answered.
- UNRESOLVED -- the operator typed something the contract could not parse.
  Nothing is staged, and review is BLOCKED until it is resolved or discarded,
  because submitting around it would file the previous value while the screen
  shows the new one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .....domain.calculations.registry.schema_input_kind import InputKind

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .....application.modelo.edit_session import ModeloEditSession
    from .....core.external_constants import OutputLanguage

__all__ = ["ScalarFieldSet", "ScalarFieldState", "UnresolvedLexeme"]


@dataclass(frozen=True, slots=True)
class UnresolvedLexeme:
    """One control carrying text the contract refused to parse.

    The lexeme itself is deliberately absent. The contract refuses to echo a
    raw lexeme in any result derived from a parse request, and a review gate
    that reported one would leak it into whatever renders the blocker.
    """

    casilla_id: str
    message_key: str


@dataclass(slots=True)
class ScalarFieldState:
    """What one control knows about its own casilla.

    ``touched`` is the UNCHANGED distinction and is set by the operator's
    interaction, never inferred from the value: a control whose text happens
    to equal the declared value has still not been answered, and inferring
    otherwise would stage an intent nobody made.
    """

    casilla_id: str
    data_type: str
    touched: bool = False
    message_key: str | None = None

    @property
    def is_unresolved(self) -> bool:
        """Whether this control holds text the contract could not parse."""
        return self.message_key is not None


@dataclass(slots=True)
class ScalarFieldSet:
    """The controls for one admitted edit, and their unresolved state.

    Owns no widgets and draws nothing. It is the part of the editing surface
    that has to be correct rather than merely visible, so it is separated to
    be driven directly in tests -- a control whose distinctions can only be
    proven by mounting an application is a control whose distinctions are
    mostly unproven.
    """

    _session: ModeloEditSession
    _locale: OutputLanguage
    _states: dict[str, ScalarFieldState] = field(default_factory=dict, init=False)

    @classmethod
    def for_session(cls, session: ModeloEditSession, *, locale: OutputLanguage) -> ScalarFieldSet:
        """Build one control state per casilla the admission permits.

        The locale is supplied by the surface that is rendering, not resolved
        here: the language a lexeme is parsed in must be the language the
        operator was shown, and a module that looked it up independently could
        disagree with the screen after a language switch.
        """
        instance = cls(_session=session, _locale=locale)
        for writable in session.writable_scalars():
            instance._states[writable.casilla_id] = ScalarFieldState(
                casilla_id=writable.casilla_id,
                data_type=writable.data_type,
            )
        return instance

    def casilla_ids(self) -> tuple[str, ...]:
        """Return every editable casilla, in canonical order."""
        return tuple(sorted(self._states))

    def state(self, casilla_id: str) -> ScalarFieldState:
        """Return one control's state, refusing an address the admission did not permit."""
        try:
            return self._states[casilla_id]
        except KeyError:
            raise KeyError(
                f"casilla {casilla_id!r} is not on this admission's permitted surface; "
                "a control was built for an address the contract does not allow editing"
            ) from None

    def submit_lexeme(self, casilla_id: str, raw_lexeme: str) -> ScalarFieldState:
        """Hand what the operator typed to the session, and record the verdict.

        Marks the control touched WHETHER OR NOT the value parsed. A refused
        lexeme is still an interaction: forgetting it would let the surface
        report the field as unchanged while the operator is looking at text
        the contract rejected.
        """
        state = self.state(casilla_id)
        outcome = self._session.set_casilla(
            casilla_id,
            raw_lexeme,
            input_kind=InputKind.MANUAL,
            locale=self._locale,
        )
        state.touched = True
        state.message_key = None if outcome.accepted else outcome.message_key
        return state

    def clear(self, casilla_id: str) -> ScalarFieldState:
        """Remove a declared value, which is an answer rather than an absence.

        Clearing resolves any unresolved lexeme on the same control: the
        operator has replaced text the contract refused with a definite
        instruction, so nothing is left outstanding.
        """
        state = self.state(casilla_id)
        self._session.clear_casilla(casilla_id)
        state.touched = True
        state.message_key = None
        return state

    def revert(self, casilla_id: str) -> ScalarFieldState:
        """Discard the operator's own edit, returning the control to unanswered.

        Distinct from :meth:`clear`, which submits a removal. Reverting also
        resolves an unresolved lexeme, because the refused text is gone.
        """
        state = self.state(casilla_id)
        self._session.discard_casilla(casilla_id)
        state.touched = False
        state.message_key = None
        return state

    def unresolved(self) -> tuple[UnresolvedLexeme, ...]:
        """Return every control still holding text the contract refused."""
        return tuple(
            UnresolvedLexeme(casilla_id=state.casilla_id, message_key=state.message_key)
            for state in (self._states[key] for key in sorted(self._states))
            if state.message_key is not None
        )

    def blocks_review(self) -> bool:
        """Whether review must be refused because a lexeme is unresolved.

        Blocking is the point. Reviewing around an unparsed control would
        submit the value the field held BEFORE the operator typed over it,
        while the screen shows what they typed -- the submission and the
        surface would disagree, and only the surface is visible.
        """
        return bool(self.unresolved())

def unresolved_message_keys(fields: Iterable[UnresolvedLexeme]) -> tuple[str, ...]:
    """Return the localisation keys a surface must render to explain a block."""
    return tuple(item.message_key for item in fields)
