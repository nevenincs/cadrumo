"""Profile manager actions, search, and row interactions."""

from __future__ import annotations

from contextvars import copy_context
from typing import TYPE_CHECKING

from textual.events import DescendantFocus
from textual.message import Message
from textual.widgets import Button, Checkbox, DataTable, Input, Static
from textual.worker import Worker, WorkerState

from ....application.user_profile.acquisition_sources import (
    ProfileAcquisitionSourceV1,
    known_profile_acquisition_sources,
)
from ....core.i18n.render import tr
from ....domain.user_profile.plantilla_media import PLANTILLA_MEDIA_PATH
from ....domain.user_profile.values import ProfileSetupState
from ..components.widgets import (
    ContentScroll,
    SourceActionCard,
)
from .edit_screens import FieldEditScreen, RepeatableRowAddScreen, RepeatableRowRemoveScreen, field_help_text
from .overview_contracts import (
    _CONTINUE_BUTTON_ID,
    _DOCUMENT_READER_CARD_ID,
    _PLANTILLA_MEDIA_BUTTON_ID,
    _REQUIRED_ONLY_ID,
    _SEARCH_ID,
    _SEARCH_SETTLE_SECONDS,
)
from .plantilla_media import (
    PlantillaMediaRequest,
    PlantillaMediaScreen,
    PlantillaMediaSetRequest,
)
from .setup_journey import SETUP_STAGES, ProfileSetupStage

if TYPE_CHECKING:
    from ....application.user_profile.overview import ProfileFieldView, ProfileSectionView
    from ....domain.user_profile.plantilla_media import PlantillaMediaYear
    from .overview import ProfileManagerScreen


class ProfileOverviewInteractionMixin:
    """Implement profile manager actions, search, and row interactions."""

    async def on_button_pressed(self: ProfileManagerScreen, event: Button.Pressed) -> None:
        """Route setup, section, and acquisition buttons in their established order."""
        button_id = event.button.id or ""
        if await _handle_setup_button(self, button_id):
            return
        if _handle_section_button(self, button_id):
            return
        await _launch_source_button(self, event)

    def _section(self: ProfileManagerScreen, key: str) -> ProfileSectionView | None:
        """Return the displayed section without treating display order as identity."""
        return next((section for section in self.overview.sections if section.key == key), None)

    @staticmethod
    def _row_key_for_field(section: ProfileSectionView, field: ProfileFieldView) -> str:
        """Recover the stored row key from a schema-expanded fact path."""
        parts = field.path.split(".")
        if len(parts) == 2 and parts[0] == section.key:
            return ""
        if len(parts) == 3 and parts[0] == section.key:
            return parts[1]
        # A projected repeatable field must have one of these shapes.  Do not
        # guess from display position if a malformed projection reaches TUI.
        raise ValueError(f"cannot determine row identity from {field.path!r}")

    def _existing_row_key(
        self: ProfileManagerScreen, section: ProfileSectionView, table: DataTable[str] | None = None
    ) -> str | None:
        """Return the selected stable row only when it has an extant value."""
        table = table or self._table_by_section.get(section.key)
        if table is None or not table.is_valid_row_index(table.cursor_row):
            return None
        # DataTable exposes the key through its coordinate; use the field map
        # keyed by that path, not cursor order as the row identity.
        coordinate = table.coordinate_to_cell_key(table.cursor_coordinate)
        field = self._field_by_key.get(str(coordinate.row_key.value))
        if field is None:
            return None
        candidate = self._row_key_for_field(section, field)
        group = tuple(item for item in section.fields if self._row_key_for_field(section, item) == candidate)
        return candidate if any(item.present for item in group) else None

    @staticmethod
    def _has_existing_row(section: ProfileSectionView) -> bool:
        """Whether this projection contains a real row rather than its blank template."""
        return any(field.present for field in section.fields)

    def _open_add_row(self: ProfileManagerScreen, section_key: str) -> None:
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        section = self._section(section_key)
        if section is None or not section.repeatable or self._add_row is None:
            return
        baseline_revision = self.overview.record_revision
        baseline_digest = self.overview.content_digest
        self.app.push_screen(
            RepeatableRowAddScreen(section),
            lambda values: self._add_repeatable_row(section.key, values, baseline_revision, baseline_digest),
        )

    def _open_remove_selected_row(self: ProfileManagerScreen, section_key: str) -> None:
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        section = self._section(section_key)
        if section is None or self._remove_row is None:
            return
        row_key = self._existing_row_key(section)
        if row_key is None:
            return
        baseline_revision = self.overview.record_revision
        baseline_digest = self.overview.content_digest
        self.app.push_screen(
            RepeatableRowRemoveScreen(section.key, row_key),
            lambda confirmed: self._remove_repeatable_row(
                section.key, row_key, baseline_revision, baseline_digest, confirmed is True
            ),
        )

    @property
    def _plantilla_media_offered(self: ProfileManagerScreen) -> bool:
        """Whether this host wired the doors the average-workforce dialog needs."""
        return self._list_plantilla_media is not None and (
            self._set_plantilla_media is not None or self._remove_plantilla_media is not None
        )

    def _open_plantilla_media(self: ProfileManagerScreen) -> None:
        """Read the declared years off the event loop, then open the dialog on them."""
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        door = self._list_plantilla_media
        if door is None or not self._plantilla_media_offered or self._pending_listing is not None:
            return
        listing_context = copy_context()

        def _read() -> tuple[PlantillaMediaYear, ...]:
            return tuple(listing_context.run(door))

        self._pending_listing = self.run_worker(
            _read,
            name="profile-plantilla-media-list",
            group="profile-plantilla-media-list",
            exit_on_error=False,
            thread=True,
        )

    def _settle_listing(self: ProfileManagerScreen, worker: Worker[tuple[PlantillaMediaYear, ...]]) -> None:
        """Open the dialog on the years storage holds, or say why they could not be read."""
        self._pending_listing = None
        if worker.state is WorkerState.SUCCESS and worker.result is not None:
            self.app.push_screen(PlantillaMediaScreen(worker.result), self._apply_plantilla_media)
            return
        self._refuse_worker(worker.error, message_key="flows.manager.plantilla_media.list_failed")

    def _apply_plantilla_media(self: ProfileManagerScreen, request: PlantillaMediaRequest | None) -> None:
        """Send one dialog answer to its door; a dismissal requests nothing."""
        if request is None:
            return
        if isinstance(request, PlantillaMediaSetRequest):
            set_door = self._set_plantilla_media
            if set_door is None:
                return
            self._run_row_write(
                f"{PLANTILLA_MEDIA_PATH}:{request.year}",
                lambda: set_door(request.year, request.average_workforce, request.state),
            )
            return
        remove_door = self._remove_plantilla_media
        if remove_door is None:
            return
        self._run_row_write(f"{PLANTILLA_MEDIA_PATH}:{request.year}", lambda: remove_door(request.year))

    def on_data_table_row_highlighted(self: ProfileManagerScreen, event: Message) -> None:
        """Explain the field under the cursor of the table the operator is in.

        Every table reports a highlight as it is built, so only the focused
        one may speak; otherwise the last section built would explain itself
        whatever row the operator is on.
        """
        table: DataTable[str] | None = self._section_table(event.control)
        if table is not None and table.has_focus:
            self._explain_cursor_row(table)

    def on_descendant_focus(self: ProfileManagerScreen, event: DescendantFocus) -> None:
        """Explain the cursor row of a section table the moment it takes focus."""
        table: DataTable[str] | None = self._section_table(event.widget)
        if table is not None:
            self._explain_cursor_row(table)

    def _explain_cursor_row(self: ProfileManagerScreen, table: DataTable[str]) -> None:
        panel = self.query_one("#manager-field-help", Static)
        field = None
        if table.row_count and table.is_valid_row_index(table.cursor_row):
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            field = self._field_by_key.get(str(row_key)) if row_key is not None else None
        text = "" if field is None else field_help_text(field)
        panel.display = bool(text)
        panel.update(text)

    def on_data_table_row_selected(self: ProfileManagerScreen, event: DataTable.RowSelected) -> None:
        """Open the edit dialog for the selected field.

        Refused while a write is in flight: the door merges into the record
        as it loads it, so a second edit started before the first landed
        would merge into the pre-edit facts and drop the first field.

        """
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        key = event.row_key.value
        if key is None:
            return
        field = self._field_by_key.get(str(key))
        if field is None:
            return
        self._walking = False
        self._open_field_editor(field)

    def _open_field_editor(self: ProfileManagerScreen, field: ProfileFieldView, *, context: str | None = None) -> None:
        """Open the edit dialog for one field, or the add-row form for an unfilled row."""
        section = self._section(field.path.split(".", 1)[0])
        if section is not None and section.repeatable:
            row_key = self._row_key_for_field(section, field)
            row_fields = tuple(
                candidate for candidate in section.fields if self._row_key_for_field(section, candidate) == row_key
            )
            if not any(candidate.present for candidate in row_fields):
                # The unfilled group is the section's add affordance, not an
                # extant base row.  Opening an edit would turn omission into
                # an accidental update of an identity that does not exist.
                self._open_add_row(section.key)
                return
        apply = self._apply_edit_for(field)

        def _close(value: str | None) -> None:
            # Cancelling, or leaving the box blank, is the operator stepping
            # out of the walk; only an answer carries it on to the next one.
            if value is None or not value.strip():
                self._walking = False
            apply(value)

        self.app.push_screen(FieldEditScreen(field, validate=self._validator_for(field), context=context), _close)

    def action_focus_search(self: ProfileManagerScreen) -> None:
        """Move the cursor to the search box."""
        self.query_one(f"#{_SEARCH_ID}", Input).focus()

    def on_input_changed(self: ProfileManagerScreen, event: Input.Changed) -> None:
        """Filter the sections once typing in the search box pauses."""
        if event.input.id != _SEARCH_ID:
            return
        self._query = event.value
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(_SEARCH_SETTLE_SECONDS, self._apply_filters)

    def on_checkbox_changed(self: ProfileManagerScreen, event: Checkbox.Changed) -> None:
        """Show every field, or only the answers setup requires."""
        if event.checkbox.id != _REQUIRED_ONLY_ID:
            return
        self._required_only = event.value
        self.run_worker(self._apply_filters(), group="profile-filter")

    async def _apply_filters(self: ProfileManagerScreen) -> None:
        """Rebuild the sections under the current search and required-only switch."""
        self._search_timer = None
        async with self._render_lock:
            await self._render_sections(disclose_matches=bool(self._query.strip()))
            self._render_onboarding()
        # Each fold a search opens scrolls itself into view; the results read
        # from the top.
        body = self.query_one("#manager-body", ContentScroll)
        self.call_after_refresh(body.scroll_home, animate=False, immediate=True)

    def action_choose_language(self: ProfileManagerScreen) -> None:
        """Open the language chooser on the field that already holds it.

        The language is an ordinary profile field and is written through
        the ordinary door: this opens the same dialog selecting a row would
        open, on the same field, and hands the answer to the same callback,
        so there is no second way for the language to be set. What the
        binding adds is reachability — the setting that decides what every
        other row says should not itself be findable only by reading them.

        The tokens are shown as language names, because an operator whose
        page is in a language they do not read is exactly the one who
        cannot be asked to recognise ``hu``. Each name is written in its own
        language for the same reason: that operator cannot read "Húngaro"
        on a Spanish page either, but does read "Magyar".
        """
        field = self._language_field()
        if field is None:
            # A profile schema that declares no language field is not a
            # failure; the page simply has nothing to offer here. The
            # footer does not name the key in that case, so this answers
            # only an operator who pressed it unprompted.
            self._refuse(tr("flows.manager.language.unavailable"))
            return
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        self.app.push_screen(
            FieldEditScreen(
                field,
                prompt=tr("wizard.setup.profile.output-language.prompt"),
                choice_labels={
                    choice.value: tr(
                        f"wizard.setup.profile.output-language.choices.{choice.value}.label",
                        locale=choice.value,
                    )
                    for choice in field.choices
                },
                validate=self._validator_for(field),
            ),
            self._apply_edit_for(field),
        )


async def _handle_setup_button(screen: ProfileManagerScreen, button_id: str) -> bool:
    """Handle one setup stage action, leaving unrelated buttons for later routes."""
    if button_id == "manager-complete-setup":
        screen.action_complete_setup()
        return True
    if button_id == _CONTINUE_BUTTON_ID:
        await screen.action_continue_setup()
        return True
    if button_id == "onboarding-previous":
        index = SETUP_STAGES.index(screen._setup_stage)
        if index:
            await screen._show_setup_stage(SETUP_STAGES[index - 1])
        return True
    if not button_id.startswith("setup-stage-"):
        return False
    stage = ProfileSetupStage(button_id.removeprefix("setup-stage-"))
    if stage is not ProfileSetupStage.READY or screen.overview.setup_state is ProfileSetupState.COMPLETE:
        await screen._show_setup_stage(stage)
    return True


def _handle_section_button(screen: ProfileManagerScreen, button_id: str) -> bool:
    """Route repeatable-row and plantilla-media controls."""
    if button_id.startswith("manager-add-row-"):
        screen._open_add_row(button_id.removeprefix("manager-add-row-"))
        return True
    if button_id.startswith("manager-remove-row-"):
        screen._open_remove_selected_row(button_id.removeprefix("manager-remove-row-"))
        return True
    if button_id == _PLANTILLA_MEDIA_BUTTON_ID:
        screen._open_plantilla_media()
        return True
    return False


async def _launch_source_button(screen: ProfileManagerScreen, event: Button.Pressed) -> None:
    """Launch only an identified source after preserving the edit-in-flight guard."""
    card = event.button.parent
    if _open_document_reader_card(screen, card):
        return
    launch_source = screen._launch_source
    if launch_source is None:
        return
    source = _selected_acquisition_source(card)
    if source is None:
        return
    # Checked here rather than on entry so an unrelated press is not answered
    # with a message about a write.
    if screen._pending_write is not None:
        screen._refuse(tr("flows.manager.edit.write_in_flight"))
        return
    await launch_source(source)


def _open_document_reader_card(screen: ProfileManagerScreen, card: object | None) -> bool:
    """Handle the document-reader action card if this is the pressed card."""
    if not isinstance(card, SourceActionCard) or card.id != _DOCUMENT_READER_CARD_ID:
        return False
    if screen._open_document_reader is not None:
        screen.app.push_screen(screen._open_document_reader())
    return True


def _selected_acquisition_source(card: object | None) -> ProfileAcquisitionSourceV1 | None:
    """Resolve an acquisition source only when its launch door is wired."""
    if not isinstance(card, SourceActionCard) or card.id is None or not card.id.startswith("source-"):
        return None
    key = card.id.removeprefix("source-")
    return next((candidate for candidate in known_profile_acquisition_sources() if candidate.key.value == key), None)
