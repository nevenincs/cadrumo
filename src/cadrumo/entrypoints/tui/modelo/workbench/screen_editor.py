"""Editor lifecycle and field interaction for the Modelo workbench."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from textual.await_remove import AwaitRemove

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.work_form_models import ModeloWorkForm
from .....core.i18n.render import tr
from .casilla_list import CasillaList
from .casilla_list_models import CasillaListEntry
from .editor import (
    CasillaEditorPanel,
    CasillaEditorScreen,
    EditorDecision,
    EditorOutcome,
    read_only_reason,
)
from .editor_explanations import affects_text
from .header import ResultView, result_view
from .ports import ModeloWorkbenchActionsV1, WorkbenchChangeKind
from .screen_constants import (
    _DOCKED_FROM,
    _FOLLOWING_LINES,
)
from .session import StagedChange, StageRefusal, WorkbenchEditSession
from .sources import OpenSourceSurface
from .vocabulary import aeat_imported_on

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchEditorMixin:
    """Own the editor behavior for the modelo workbench."""

    def _height(self: ModeloWorkbenchScreen) -> int:
        return self.size.height or self.app.size.height

    def _push_editor(
        self: ModeloWorkbenchScreen,
        entry: CasillaListEntry,
        actions: ModeloWorkbenchActionsV1,
        card: ModeloCasillaHelpCardV1 | None,
    ) -> None:
        """Open the box panel docked under the list, or as the centred dialog on a terminal too short for both.

        The host is chosen each time a panel opens. One already open stays
        where it is, whatever the terminal does, until the filer closes it, so
        nothing typed into it is lost to a resize.
        """
        recorded = self.recorded
        form = self.form
        result = self._editor_result(form, recorded)
        docked = self._height() >= _DOCKED_FROM
        panel = self._editor_panel(entry, actions, card, form, result, recorded, docked)
        self._show_editor(entry, panel, docked)

    def _editor_result(self: ModeloWorkbenchScreen, form: ModeloWorkForm | None, recorded: bool) -> ResultView | None:
        if form is None:
            return None
        return result_view(form, self._language, staged=len(self._session.changes), recorded=recorded)

    def _editor_panel(
        self: ModeloWorkbenchScreen,
        entry: CasillaListEntry,
        actions: ModeloWorkbenchActionsV1,
        card: ModeloCasillaHelpCardV1 | None,
        form: ModeloWorkForm | None,
        result: ResultView | None,
        recorded: bool,
        docked: bool,
    ) -> CasillaEditorPanel:
        field = entry.field
        probe = WorkbenchEditSession(self._language)
        return CasillaEditorPanel(
            field,
            parse=actions.parse,
            language=self._language,
            limits=() if card is None else card.constraints,
            can_clear=probe.stage_clear(field) is None,
            can_restore=probe.stage_restore(field) is None,
            read_only_reason=read_only_reason(field, self._language, recorded=recorded),
            # An unread card says nothing, rather than that the box affects nothing.
            affects=affects_text(card, form, result=result),
            calculation=self._editor_calculation(card),
            # Docked, the header stays in view and the panel need not repeat its result line.
            status_line=None if docked else self._status_line(),
            recorded=recorded,
            aeat_imported=aeat_imported_on(self.form),
            staged=self._staged_change(entry),
        )

    @staticmethod
    def _editor_calculation(card: ModeloCasillaHelpCardV1 | None) -> str | None:
        if card is None or card.formula is None:
            return None
        return "\n".join(part for part in (card.formula.text, card.formula.values_text) if part is not None)

    def _staged_change(self: ModeloWorkbenchScreen, entry: CasillaListEntry) -> StagedChange | None:
        return next((change for change in self._session.changes if change.key == entry.key), None)

    def _show_editor(
        self: ModeloWorkbenchScreen, entry: CasillaListEntry, panel: CasillaEditorPanel, docked: bool
    ) -> None:
        if docked:
            self._dock(entry, panel)
            return
        self._close_dock(refocus=False)
        self.app.push_screen(CasillaEditorScreen(panel), partial(self._editor_closed, entry))

    def _dock(self: ModeloWorkbenchScreen, entry: CasillaListEntry, panel: CasillaEditorPanel) -> None:
        """Put ``panel`` in place of the help band, refilling it when a panel is already there."""
        previous = self._docked
        self._docked = (entry, panel)
        self.add_class("-editing")
        # The list keeps the rows after the box in view itself, whenever it brings the box in.
        self.query_one(CasillaList).keep_following(_FOLLOWING_LINES)
        removed = None if previous is None else previous[1].remove()
        self.run_worker(self._mount_docked(panel, removed), group="workbench-dock")

    async def _mount_docked(
        self: ModeloWorkbenchScreen, panel: CasillaEditorPanel, removed: AwaitRemove | None
    ) -> None:
        """Mount ``panel`` once the one it replaces is gone, unless the filer closed it or another replaced it since."""
        if removed is not None:
            await removed
        docked = self._docked
        if docked is None or docked[1] is not panel:
            return
        # The list gives the panel its lines on the next layout, scrolling to keep the box in view.
        await self.mount(panel, before=self.query_one("#wb-help"))

    def _working_in_dock(self: ModeloWorkbenchScreen) -> bool:
        """Whether the filer's cursor is in the docked box panel."""
        docked = self._docked
        focused = self.focused
        return docked is not None and focused is not None and docked[1] in focused.ancestors_with_self

    def _close_dock(self: ModeloWorkbenchScreen, *, refocus: bool = True) -> None:
        """Take the docked panel away and give the help band back, with the cursor on the list when ``refocus``."""
        docked = self._docked
        if docked is None:
            return
        self._docked = None
        docked[1].remove()
        self.remove_class("-editing")
        casilla_list = self.query_one(CasillaList)
        casilla_list.keep_following(0)
        if self._pages and not self._legend_level:
            self._render_help(casilla_list.highlighted)
        if refocus:
            casilla_list.focus()

    def on_casilla_list_edit_requested(self: ModeloWorkbenchScreen, message: CasillaList.EditRequested) -> None:
        """Open the panel for the casilla under the cursor; one that cannot be typed into says why and where."""
        self._open_editor(message.entry)

    def on_casilla_editor_panel_closed(self: ModeloWorkbenchScreen, message: CasillaEditorPanel.Closed) -> None:
        """Answer the docked panel: stage the filer's decision, then refill it for the next box, or close it."""
        message.stop()
        docked = self._docked
        if docked is None or message.panel is not docked[1]:
            return
        entry = docked[0]
        decision = message.outcome
        if isinstance(decision, OpenSourceSurface):
            self._close_dock()
            self._open_surface(decision)
            return
        if decision is None:
            self._close_dock()
            return
        casilla_list = self.query_one(CasillaList)
        refusal = self._stage(entry, decision)
        if refusal is None and decision.advance:
            self._advance_attention(1)
            following = casilla_list.highlighted
            if following is not None and following.key != entry.key:
                self._open_editor(following)
                return
        self._close_dock()

    def _editor_closed(self: ModeloWorkbenchScreen, entry: CasillaListEntry, decision: EditorOutcome | None) -> None:
        if isinstance(decision, OpenSourceSurface):
            self._open_surface(decision)
            return
        if decision is None:
            return
        refusal = self._stage(entry, decision)
        if refusal is None and decision.advance:
            self._advance_attention(1)

    def _stage(self: ModeloWorkbenchScreen, entry: CasillaListEntry, decision: EditorDecision) -> StageRefusal | None:
        """Stage what the filer decided in a box's panel, then show the workbench with it or say why it was refused."""
        field = entry.field
        if decision.kind is WorkbenchChangeKind.SET:
            refusal = self._session.stage_value(field, decision.value, decision.display)
        elif decision.kind is WorkbenchChangeKind.CLEAR:
            refusal = self._session.stage_clear(field)
        else:
            refusal = self._session.stage_restore(field)
        self._after_stage(refusal)
        return refusal

    def _after_stage(self: ModeloWorkbenchScreen, refusal: StageRefusal | None) -> None:
        if refusal is not None:
            self._notice(tr(f"tui.modelo.workbench.stage_refused.{refusal.value}"))
            return
        self._notice("")
        self._refresh_after_staging()
