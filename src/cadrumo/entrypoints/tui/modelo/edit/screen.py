"""The mounted C3 editor surface for one admitted modelo edit.

Every decision this screen makes about a value is delegated. The lexeme goes
to :class:`~cadrumo.entrypoints.tui.modelo.edit.fields.ScalarFieldSet`, which
delegates to the contract's own parser; leaving goes to
:class:`~cadrumo.entrypoints.tui.modelo.edit.review.ReviewGate`. This module
decides only what is on screen, what has focus, and what the operator is told
-- it computes nothing about tax and stages nothing the headless layer has not
already accepted.

The controls are built from the admitted permitted surface, so a casilla the
contract will not accept has no widget to type into. That is the same
structural guarantee the controller makes one layer down, carried onto the
screen: an operator cannot address what the admission did not permit, because
there is nothing there to address it with.

FOCUS IS THE ERROR CHANNEL. A refused lexeme returns focus to the input that
carried it and leaves the operator's text in place to be corrected. The
alternative -- accepting the keystroke, clearing the box, and reporting the
problem somewhere else on screen -- makes the operator hunt for which of
several fields was rejected, and is how a mistyped amount becomes a silently
abandoned one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Input, Label, Static

from .....core.config import load_settings
from .....core.i18n._render import tr
from ...components.theme import toggle_appearance
from ...components.widgets import ContentScroll
from .controller import ModeloEditController
from .review import ReviewRefusal

if TYPE_CHECKING:
    from collections.abc import Callable

    from .....domain.modelos.calculation_revision import CalculationRevisionCatalogue
    from .....domain.modelos.work_unit import WorkUnitCatalogue

type CatalogueSupplier = Callable[[], tuple[WorkUnitCatalogue, CalculationRevisionCatalogue]]
"""Re-reads the catalogues a review must be judged against, at the moment it is asked."""

__all__ = ["EditorLocaleMismatchError", "ModeloEditScreen", "casilla_input_id"]


class EditorLocaleMismatchError(RuntimeError):
    """Raised when the editor would display one language and parse another."""


def casilla_input_id(casilla_id: str) -> str:
    """Return the DOM id for one casilla's input.

    Derived rather than minted so a test, the focus handler and the mount
    path all name the same widget without a shared mutable registry. The
    casilla id is already unique across the permitted surface.
    """
    return f"edit-casilla-{casilla_id}"


class ModeloEditScreen(Screen[None]):
    """One admitted edit, rendered as editable controls over its permitted surface."""

    BINDINGS: ClassVar = [
        Binding("escape", "leave_editor", ""),
        Binding("f2", "review_edit", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(
        self,
        controller: ModeloEditController,
        *,
        catalogues: CatalogueSupplier,
        id: str | None = None,
    ) -> None:
        """Store the ALREADY-ADMITTED controller this screen renders.

        Admission is not performed here, deliberately. A screen that admitted
        on mount would exist in an unadmitted state with its widgets already
        composed, and the ordering guarantee the controller makes -- no
        control exists before admission succeeds -- would become a promise
        this class could break by rendering early.

        ``catalogues`` is a SUPPLIER rather than a pair of catalogues,
        because review must be judged against what the tree holds when the
        operator asks -- not against a snapshot taken when the screen was
        built. Caching them here would make a concurrent change invisible to
        exactly the check that exists to catch it.
        """
        super().__init__(id=id)
        self._controller = controller
        self._catalogues = catalogues

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="edit-header", classes="cadrumo-banner")
        with ContentScroll(id="edit-body", classes="cadrumo-scroll"):
            yield Static(id="edit-notice")
        yield Static(id="edit-footer")

    def on_mount(self) -> None:
        """Render the header and one control per permitted writable casilla."""
        self._require_display_and_parse_languages_agree()
        self.query_one("#edit-header", Static).update(tr("flows.modelo_edit.title"))
        self.query_one("#edit-footer", Static).update(tr("flows.modelo_edit.footer"))
        self._mount_controls()
        self._refresh_notice()

    def _require_display_and_parse_languages_agree(self) -> None:
        """Refuse to render a form that reads numbers in a language it is not showing.

        ``tr`` resolves the AMBIENT output language while the controller
        parses lexemes in the language it was admitted for. When those differ
        the operator is shown one language and typing into another, so
        "1.234,56" can be read as a different number than the one on screen
        -- silently, because both spellings are valid somewhere.

        Raised rather than reported as a notice: a divergence here means the
        route was constructed with the wrong locale, which is a programming
        error the operator cannot act on and must not be asked to.
        """
        displayed = load_settings().cadrumo_output_language
        if str(displayed) != str(self._controller.locale.value):
            message = (
                f"editor route parses in {self._controller.locale.value} but the operator is being shown "
                f"{displayed}; amounts would be read in a language the form is not displaying"
            )
            raise EditorLocaleMismatchError(message)

    def _mount_controls(self) -> None:
        """Mount one labelled input per casilla the admission permits writing."""
        body = self.query_one("#edit-body", ContentScroll)
        for casilla_id in self._controller.fields().casilla_ids():
            body.mount(Label(casilla_id, classes="cadrumo-field-label"))
            body.mount(Input(id=casilla_input_id(casilla_id), classes="cadrumo-field-input"))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Delegate the lexeme, and keep focus on it when it is refused."""
        casilla_id = self._casilla_for(event.input)
        if casilla_id is None:
            return
        state = self._controller.fields().submit_lexeme(casilla_id, event.value)
        if state.is_unresolved:
            event.input.focus()
        self._refresh_notice()

    def _casilla_for(self, widget: Input) -> str | None:
        """Recover which casilla an input addresses, without a parallel registry."""
        for casilla_id in self._controller.fields().casilla_ids():
            if widget.id == casilla_input_id(casilla_id):
                return casilla_id
        return None

    def _refresh_notice(self) -> None:
        """State the one thing currently blocking review, or say nothing at all.

        An empty notice reads as a rendering fault, so the widget carries a
        cleared string rather than a blank line when there is nothing to say.
        """
        notice = self.query_one("#edit-notice", Static)
        unresolved = self._controller.fields().unresolved()
        if unresolved:
            notice.update(
                tr("flows.modelo_edit.unresolved", casilla_id=unresolved[0].casilla_id, count=len(unresolved))
            )
            return
        if self._controller.in_stale_conflict:
            notice.update(tr("flows.modelo_edit.stale_conflict"))
            return
        notice.update("")

    def action_review_edit(self) -> None:
        """Ask the gate to review, and report a refusal without staging anything."""
        work_catalogue, calculation_catalogue = self._catalogues()
        outcome = self._controller.review_gate().review(
            work_catalogue=work_catalogue,
            calculation_catalogue=calculation_catalogue,
        )
        notice = self.query_one("#edit-notice", Static)
        if isinstance(outcome, ReviewRefusal):
            notice.update(tr(outcome.message_key))
            return
        notice.update(tr("flows.modelo_edit.review_ready", changed=len(outcome.changed_casilla_ids)))

    def action_leave_editor(self) -> None:
        """Refuse to leave silently while the operator has unsaved work.

        The screen does not decide what unsaved means: the gate does, over the
        same session the controls stage into. Dismissing here without asking
        would discard staged edits the operator never chose to abandon.
        """
        if self._controller.review_gate().leaving_with_unsaved_changes():
            self.query_one("#edit-notice", Static).update(tr("flows.modelo_edit.unsaved_on_leave"))
            return
        self.dismiss(None)

    def action_toggle_appearance(self) -> None:
        """Flip the shared appearance, never a locally defined palette."""
        toggle_appearance(self.app)
