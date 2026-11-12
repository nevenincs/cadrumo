"""The statements the form serves, offered from the workbench and staged with the filer's other changes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.work_form_models import ModeloFormCarryAttestation
from .....core.i18n.render import tr
from .statements import StatementsScreen

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen

_NONE_LOCALE_KEY = "tui.modelo.statements.none"
_NOT_PLACED_LOCALE_KEY = "tui.modelo.statements.not_placed"


class WorkbenchStatementsMixin:
    """Own the statements offer of the modelo workbench."""

    def _served_statements(self: ModeloWorkbenchScreen) -> tuple[ModeloFormCarryAttestation, ...]:
        """Every statement the form serves now, in its order; none where the declaration takes no edit."""
        form = self.form
        if form is None or not self._may_confirm():
            return ()
        return form.carry_attestations

    def action_statements(self: ModeloWorkbenchScreen) -> None:
        """List every statement the form serves, so the filer can stage several of them for one review."""
        if not self._may_confirm():
            self._edit_unavailable()
            return
        served = self._served_statements()
        if not served:
            self._notice(tr(_NONE_LOCALE_KEY))
            return
        staged = frozenset(
            position for position, statement in enumerate(served) if self._session.stages_statement(statement)
        )
        self.app.push_screen(
            StatementsScreen(served, staged=staged, status_line=self._status_line()), self._statements_chosen
        )

    def _statements_chosen(self: ModeloWorkbenchScreen, chosen: tuple[ModeloFormCarryAttestation, ...] | None) -> None:
        """Stage every statement ticked and withdraw every one left unticked, then show the workbench with them."""
        form = self.form
        if chosen is None or form is None:
            return
        refused = False
        for statement in form.carry_attestations:
            if statement in chosen:
                refused = not self._session.stage_statement(form, statement) or refused
            else:
                self._session.withdraw_statement(statement)
        self._refresh_after_staging()
        self._notice(tr(_NOT_PLACED_LOCALE_KEY) if refused else "")


__all__ = ["WorkbenchStatementsMixin"]
