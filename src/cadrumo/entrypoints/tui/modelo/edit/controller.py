"""Route admission for the Modelo editor's C3 destination.

An editor route opens only after the complete compatibility tuple has been
judged against the live coordinates, and NO lexeme is accepted before that. The
guarantee is structural rather than procedural: until admission succeeds this
controller has no field set, no row set and no gate to hand out, so there is no
object on which a lexeme could be offered. A controller that admitted lazily,
or that exposed controls and checked compatibility when the first key was
pressed, would have the same intention and none of the guarantee.

The tuple is judged by the contract, not here. ``admit_modelo_edit`` compares
every axis -- request and result schema identity, definition digest, the
workspace refresh target and the financial operand coordinate -- and refuses
``unsupported_edit_compatibility`` before resolving any secure state. This
module's job is to ASK at the right moment and to refuse the route when the
answer is no; re-checking the axes here would be a second judge of one
question, free to disagree with the first.

A refused route is an ordinary outcome, not an error. The definition manifest
moves when the platform is upgraded, and an operator holding a stale screen
should be told the editor is unavailable and why -- not shown a traceback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .....application.modelo.edit_session import open_modelo_edit_session
from .....core.external_constants import OutputLanguage
from .fields import ScalarFieldSet
from .review import ReviewGate
from .rows import RepeatedRowSet

if TYPE_CHECKING:
    from .....application.modelo.edit_contract import (
        ModeloEditCompatibilityTupleV1,
        ModeloEditMutationFamily,
    )
    from .....application.modelo.edit_session import ModeloEditSession
    from .....application.modelo.workspace_models import ModeloWorkspaceTargetV1
    from .....domain.modelos.calculation_revision import CalculationRevisionCatalogue
    from .....domain.modelos.work_unit import WorkUnitCatalogue

__all__ = ["EditorRouteRefusedError", "ModeloEditController"]


class EditorRouteRefusedError(RuntimeError):
    """Raised when a control is requested from a route that was never admitted.

    Never raised at the operator: a refused admission is returned as an
    outcome for the surface to render. This fires only when code asks a
    controller for controls it does not have, which is a programming error
    rather than an operator one.
    """


@dataclass(slots=True)
class ModeloEditController:
    """One editor route, and the controls it exposes only once admitted."""

    _locale: OutputLanguage
    _session: ModeloEditSession | None = field(default=None, init=False)
    _fields: ScalarFieldSet | None = field(default=None, init=False)
    _rows: RepeatedRowSet | None = field(default=None, init=False)
    _refusal_key: str | None = field(default=None, init=False)
    _drifted: tuple[str, ...] = field(default=(), init=False)

    @classmethod
    def for_locale(cls, locale: OutputLanguage) -> ModeloEditController:
        """Build an unadmitted controller for one rendering language."""
        return cls(_locale=locale)

    @property
    def locale(self) -> OutputLanguage:
        """The language this route PARSES lexemes in.

        Public because it must be checkable against the language the operator
        is being shown. The two are different axes -- this one decides
        whether "1.234,56" is one number or a syntax error -- and a surface
        that displays one language while parsing another misreads amounts
        without any visible sign.
        """
        return self._locale

    @property
    def is_admitted(self) -> bool:
        """Whether this route has been admitted and may accept input."""
        return self._session is not None

    @property
    def refusal_message_key(self) -> str | None:
        """The localisation key explaining why admission was refused, if it was."""
        return self._refusal_key

    def admit(
        self,
        target: ModeloWorkspaceTargetV1,
        *,
        mutation_family: ModeloEditMutationFamily,
        bucket_id: str,
        work_catalogue: WorkUnitCatalogue,
        calculation_catalogue: CalculationRevisionCatalogue,
        compatibility: ModeloEditCompatibilityTupleV1,
    ) -> bool:
        """Judge the compatibility tuple and open the route, or refuse it.

        Returns whether the route opened. On refusal nothing is constructed,
        so the surface has no control to render and cannot accept a lexeme
        against a coordinate the contract has already rejected.
        """
        outcome = open_modelo_edit_session(
            target,
            mutation_family=mutation_family,
            bucket_id=bucket_id,
            work_catalogue=work_catalogue,
            calculation_catalogue=calculation_catalogue,
            compatibility=compatibility,
        )
        if outcome.session is None:
            self._refusal_key = outcome.message_key
            return False
        self._session = outcome.session
        self._fields = ScalarFieldSet.for_session(outcome.session, locale=self._locale)
        self._rows = RepeatedRowSet.for_session(outcome.session)
        self._refusal_key = None
        return True

    def refresh(
        self,
        *,
        work_catalogue: WorkUnitCatalogue,
        calculation_catalogue: CalculationRevisionCatalogue,
    ) -> tuple[str, ...]:
        """Recheck the admission and report which coordinates have drifted.

        An empty result means the route is still current. A non-empty one
        names the drifted coordinates and puts this route into STALE CONFLICT.

        What the route does NOT do is the substance of the row: it does not
        merge the operator's staged edits onto the newer state, does not
        rebase them, does not interpret a result ref to guess what changed,
        and does not patch the view it is already showing. Each would produce
        a screen that is neither what the operator wrote nor what the tree
        holds, and would then submit that. The staged edits and the baseline
        they are judged against are both left exactly as they were.
        """
        if self._session is None:
            raise EditorRouteRefusedError(self._unadmitted_message())
        drifted = self._session.refresh(
            work_catalogue=work_catalogue,
            calculation_catalogue=calculation_catalogue,
        )
        self._drifted = drifted
        return drifted

    @property
    def in_stale_conflict(self) -> bool:
        """Whether the last refresh found the admission had moved."""
        return bool(self._drifted)

    def fields(self) -> ScalarFieldSet:
        """Return the scalar controls, refusing before admission."""
        if self._fields is None:
            raise EditorRouteRefusedError(self._unadmitted_message())
        return self._fields

    def rows(self) -> RepeatedRowSet:
        """Return the repeated-row controls, refusing before admission."""
        if self._rows is None:
            raise EditorRouteRefusedError(self._unadmitted_message())
        return self._rows

    def review_gate(self) -> ReviewGate:
        """Return the mandatory review gate, refusing before admission."""
        if self._session is None or self._fields is None or self._rows is None:
            raise EditorRouteRefusedError(self._unadmitted_message())
        return ReviewGate.over(self._session, self._fields, self._rows)

    def _unadmitted_message(self) -> str:
        if self._refusal_key is not None:
            return f"editor route was refused ({self._refusal_key}); it exposes no controls"
        return "editor route has not been admitted; call admit() before requesting controls"
