"""Confirmation prompts for workbench actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .....application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormOrigin,
    address_key,
    confirmable,
    section_fields,
)
from .....core.i18n.render import tr
from ...search import TuiSearchHostV1
from .bulk_confirm import BulkConfirmScreen
from .casilla_list import CasillaList
from .casilla_list_models import AddressKey
from .navigator import section_of
from .page_items import page_of
from .screen_constants import (
    _NONE_TO_CONFIRM_LOCALE_KEYS,
)
from .sources import GoToCasilla, OpenSourceSurface, SourcesChoice, WorkbenchSourcesScreen, surface_target
from .vocabulary import TYPED_EDITABILITIES

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchConfirmationMixin:
    """Own the confirmation behavior for the modelo workbench."""

    def action_bulk_confirm(self: ModeloWorkbenchScreen) -> None:
        """List the assumed values of the section under the cursor, or of the page, to confirm them together.

        Never the whole declaration at once: the filer reads the values of one
        part of the form before saying they are right. Where none of the
        assumed values here can be confirmed from a list, the first one's panel
        opens instead, which says what can be done about it.
        """
        if not self._may_confirm():
            self._edit_unavailable()
            return
        fields, in_section = self._confirm_scope()
        assumed = tuple(field for field in fields if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM)
        if not assumed:
            self._notice(tr(_NONE_TO_CONFIRM_LOCALE_KEYS[in_section]))
            return
        if not any(confirmable(field) for field in assumed):
            self._open_box(address_key(assumed[0].address))
            return
        self.app.push_screen(
            BulkConfirmScreen(assumed, language=self._language, status_line=self._status_line()), self._bulk_confirmed
        )

    def _open_box(self: ModeloWorkbenchScreen, key: AddressKey) -> None:
        """Put the cursor on one box and open its panel."""
        self._go_to(key)
        entry = self.query_one(CasillaList).highlighted
        if entry is not None and entry.key == key:
            self._open_editor(entry)

    def _may_confirm(self: ModeloWorkbenchScreen) -> bool:
        form = self.form
        return self._actions is not None and form is not None and not self.recorded and form.edit_admitted

    def _confirm_scope(self: ModeloWorkbenchScreen) -> tuple[tuple[ModeloFormField, ...], bool]:
        """The fields ``b`` offers: the section under the cursor, else the page; and whether it is a section."""
        entry = self.query_one(CasillaList).highlighted
        index = self._page_index if entry is None else page_of(self._pages, entry.key)
        if not self._pages or index is None:
            return (), False
        page = self._pages[index]
        section = None if entry is None else section_of(page, entry.key)
        if section is not None:
            return section_fields(section), True
        return page.fields(), False

    def _confirm_next(self: ModeloWorkbenchScreen) -> None:
        """Offer the assumed values here, or go to the next part of the form that holds one and offer those.

        A page that does not apply this period holds nothing to do, so its
        assumed values are passed over here; ``b`` still offers them on request.
        """
        if not self._may_confirm():
            self._edit_unavailable()
            return
        fields, _ = self._confirm_scope()
        here = bool(self._pages) and self._applies(self._page_index)
        if here and any(field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM for field in fields):
            self.action_bulk_confirm()
            return
        target = self._next_assumed()
        if target is not None:
            self._go_to(target)
        self.action_bulk_confirm()

    def _next_assumed(self: ModeloWorkbenchScreen) -> AddressKey | None:
        """The next assumed box after the cursor in form order, on a page that applies, coming round to the start."""
        entry = self.query_one(CasillaList).highlighted
        ordered = self._assumed_address_keys()
        if not ordered:
            return None
        position = self._form_field_positions()
        here = -1 if entry is None else position.get(entry.key, -1)
        return next((key for key in ordered if position[key] > here), ordered[0])

    def _assumed_address_keys(self: ModeloWorkbenchScreen) -> list[AddressKey]:
        return [
            address_key(field.address)
            for index, page in enumerate(self._pages)
            if self._applies(index)
            for field in page.fields()
            if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        ]

    def _form_field_positions(self: ModeloWorkbenchScreen) -> dict[AddressKey, int]:
        return {
            address_key(field.address): order
            for order, field in enumerate(field for page in self._pages for field in page.fields())
        }

    def _bulk_confirmed(self: ModeloWorkbenchScreen, confirmed: tuple[ModeloFormField, ...] | None) -> None:
        if not confirmed:
            return
        refusals = [refusal for field in confirmed if (refusal := self._session.stage_confirmation(field)) is not None]
        self._refresh_after_staging()
        self._notice(tr(f"tui.modelo.workbench.stage_refused.{refusals[0].value}") if refusals else "")

    def on_casilla_list_clear_requested(self: ModeloWorkbenchScreen, message: CasillaList.ClearRequested) -> None:
        """Stage removing the value the filer declared on the casilla under the cursor."""
        self._after_stage(self._session.stage_clear(message.entry.field))

    def on_casilla_list_revert_requested(self: ModeloWorkbenchScreen, message: CasillaList.RevertRequested) -> None:
        """Drop the change staged on the casilla under the cursor."""
        if self._session.revert(message.entry.key):
            self._notice("")
            self._refresh_after_staging()

    def on_casilla_list_source_requested(self: ModeloWorkbenchScreen, message: CasillaList.SourceRequested) -> None:
        """Open the declaration's sources, on the casilla under the cursor when a source feeds it."""
        form = self.form
        if form is None:
            return
        self.app.push_screen(
            WorkbenchSourcesScreen(
                form,
                language=self._language,
                staged=self._session.display(),
                focus=message.entry.key,
                status_line=self._status_line(),
            ),
            self._sources_closed,
        )

    def _sources_closed(self: ModeloWorkbenchScreen, choice: SourcesChoice | None) -> None:
        if isinstance(choice, GoToCasilla):
            self._go_to(choice.key)
            entry = self.query_one(CasillaList).highlighted
            if entry is not None and entry.key == choice.key and entry.field.editability in TYPED_EDITABILITIES:
                self._open_editor(entry)
        elif isinstance(choice, OpenSourceSurface):
            self._open_surface(choice)

    def _open_surface(self: ModeloWorkbenchScreen, choice: OpenSourceSurface) -> None:
        navigate = self._navigate
        root = self.app
        if navigate is None and isinstance(root, TuiSearchHostV1):
            navigate = root.navigate_to
        target = surface_target(choice.surface)
        if navigate is None or target is None:
            self._notice(tr("tui.modelo.workbench.sources.not_here"))
            return
        self._leave_then(lambda: navigate(target))
