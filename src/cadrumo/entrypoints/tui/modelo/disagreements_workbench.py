"""The workbench's door to the disagreements dialog."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from ....application.modelo.work_form_issue_lines import ModeloFormIssueLine, form_issue_lines
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from .disagreements_screen import DisagreementsChangedV1, ModeloDisagreementsScreen

if TYPE_CHECKING:
    from .workbench.screen import ModeloWorkbenchScreen

UNAVAILABLE_LOCALE_KEY = "tui.modelo.disagreements.unavailable"


class WorkbenchDisagreementsMixin:
    """Own the disagreements journey of the modelo workbench."""

    def _disagreement_lines(self: ModeloWorkbenchScreen, language: OutputLanguage) -> tuple[ModeloFormIssueLine, ...]:
        """The form's lines that state a source disagreement, in the form's order, worded in ``language``."""
        form = self.form
        if form is None:
            return ()
        return tuple(line for line in form_issue_lines(form, language) if line.finding_id is not None)

    def action_disagreements(self: ModeloWorkbenchScreen) -> None:
        """List the source disagreements the declaration states and the answers held, and answer them."""
        form = self.form
        door = self._disagreements
        if form is None or door is None or form.calculation_revision_id is None:
            self._notice(tr(UNAVAILABLE_LOCALE_KEY))
            return
        self.app.push_screen(
            ModeloDisagreementsScreen(
                door, calculation_revision_id=form.calculation_revision_id, lines_for=self._disagreement_lines
            ),
            self._disagreements_closed,
        )

    def _disagreements_closed(self: ModeloWorkbenchScreen, changed: DisagreementsChangedV1 | None) -> None:
        """Read the declaration again after an answer, then say the application's sentence for it."""
        if changed is None:
            return
        self.run_worker(partial(self._read_then_say, changed.words), group="workbench-read", exclusive=True)

    async def _read_then_say(self: ModeloWorkbenchScreen, words: str) -> None:
        await self._read()
        self._notice(words)


__all__ = ["WorkbenchDisagreementsMixin"]
