"""The profile manager: your profile as data you can edit, not steps to finish.

This is what the operator lands on after registering, and what
``config profile edit`` opens directly. It replaces the wizard's review
page, which enumerated the *questions of a setup flow* with a status
glyph each — a progress meter for a process, telling the operator where
they were in a walk but never what their profile actually held.

The page here is the profile itself: every schema section, every declared
field, and the value on record for it — including one row per instance of
a fact the taxpayer holds several of, so three socios read as three rows
rather than one. A field the operator has not filled in is a visible empty
row, because "what is still blank" is the
question this page exists to answer. Selecting any row edits it in place
and writes immediately; there is no submit step, no final commit, and no
ordering. Completeness names the schema-required information still missing
— never arithmetic and never a gate on viewing or editing.

The screen owns no profile logic. The page content is
:func:`~cadrumo.application.user_profile.overview.build_profile_overview`, and an
edit is an authenticated revision-bound fact command.

See Also:
    :class:`~cadrumo.application.user_profile.overview.ProfileOverview`
        The typed projection this screen renders.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextvars import copy_context
from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Label, OptionList, ProgressBar, Static
from textual.worker import Worker, WorkerState

from ....application.user_profile.acquisition_sources import (
    AcquisitionSourceCredentialPostureV1,
    ProfileAcquisitionSourceKey,
    ProfileAcquisitionSourceV1,
    known_profile_acquisition_sources,
)
from ....application.user_profile.presentation import notice_presentation, profile_field_shape_hint
from ....core.i18n.render import tr
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ....domain.user_profile.plantilla_media import PLANTILLA_MEDIA_PATH
from ....domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....domain.user_profile.values import ProfileSetupState
from ..components.account_chrome import AccountChromeScreen
from ..components.status import PinnedStatusBar
from ..components.theme import (
    BASE_CSS,
    NOTICE_BAND_CSS,
    install_cadrumo_themes,
    toggle_appearance,
    tokenised,
)
from ..components.widgets import (
    ContentDataTable,
    ContentScroll,
    CredentialRequirement,
    DisclosureGroup,
    NoticeBand,
    RequirementStatus,
    SourceActionCard,
    SourceActionDescriptor,
)
from .plantilla_media import (
    PlantillaMediaRequest,
    PlantillaMediaScreen,
    PlantillaMediaSetRequest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

    from textual.timer import Timer
    from textual.widgets.data_table import ColumnKey

    from ....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
    from ....domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear


type ProfileFieldPersist = Callable[[str, str, int, str], ProfileOverview]
"""The one-field write door: path, value, and the revision and digest the edit was made against."""

_PRESENT_GLYPH = "●"
"""Marks a field carrying a value. A glyph, not colour alone."""

_ABSENT_GLYPH = "○"
"""Marks a declared field the operator has not filled in yet."""

_REQUIRED_MARK = "*"
"""Marks a field filing will eventually require."""

_FIELD_COLUMN_WIDTH = 24
"""Cap, in cells, on the field-name column of every section table.

``DataTable`` sums its columns' natural content width with no clamp against
the container: an unbounded field-name column on a long-label section (the
declared AEAT field names run long) grows wide enough on its own to push the
value column past the right edge of an eighty-column terminal, with the
table's own horizontal scroll left at its default leftmost position and no
visible affordance hinting a value sits further right. The operator sees a
table that looks like it has no value column at all.

A fixed cap paired with the row's auto height (see the ``add_row`` calls
below) wraps a long label onto more lines instead, which is what keeps the
state and value columns inside the viewport at every terminal width this
screen supports — not merely at whatever width the widest declared label
happens to fit. The value column is deliberately left uncapped: it is the
column the operator opened the page to see, and it is a real fact from the
profile rather than a fixed schema label, so letting it use whatever room
the field-name column no longer claims is the point of the cap.
"""

_ROW_INDEX_SEPARATOR = " · "
"""Sits between a repeated row's instance number and its field label.

Punctuation rather than copy, which is why it is written here and not in
the locale catalogues: the label beside it is already translated, and the
number is a stored identity. A taxpayer with three socios would otherwise
read three identical ``NIF`` rows, since the path telling them apart is
shown only once the row is opened.
"""

_EDIT_DIALOG_CSS = tokenised("""
#edit-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
}
#edit-context { color: $text-muted; margin-bottom: $cadrumo-space-1; }
#edit-label { text-style: bold; }
#edit-hint { color: $text-muted; }
#edit-refusal { color: $error; text-style: bold; }
#edit-masked-note { color: $text-muted; }
#edit-dialog Input { margin: $cadrumo-space-0; }
#edit-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#edit-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")


class FieldEditScreen(ModalScreen[str | None]):
    """Edit one projected profile field without owning profile policy."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        field: ProfileFieldView,
        *,
        prompt: str | None = None,
        choice_labels: Mapping[str, str] | None = None,
        validate: Callable[[str], str | None] | None = None,
        context: str | None = None,
    ) -> None:
        """Initialize the modal from one already-projected profile field.

        ``context`` is shown above the question: where the operator is in
        the setup walk and what the section being asked about is for.
        """
        super().__init__()
        self._field = field
        self._question_context = context
        self._prompt = prompt if prompt is not None else field.label
        self._choice_labels: dict[str, str] = dict(choice_labels) if choice_labels is not None else {}
        self._validate = validate

    def _label_for(self, value: str) -> str:
        """Return the operator label for one stored choice token."""
        override = self._choice_labels.get(value)
        if override is not None:
            return override
        return next(
            (choice.label for choice in self._field.choices if choice.value == value),
            tr("flows.manager.choice_unavailable"),
        )

    @property
    def _box_hides_a_value(self) -> bool:
        """Whether an empty box conceals an existing masked value."""
        return self._field.masked and self._field.present and not self._field.choices

    @property
    def _offers_clear(self) -> bool:
        """Whether the masked optional value can be explicitly cleared."""
        return self._field.masked and self._field.present and not self._field.required

    @override
    def compose(self) -> ComposeResult:
        """Lay out the choice or typed editor without exposing masked values."""
        with Vertical(id="edit-dialog"):
            if self._question_context:
                yield Static(self._question_context, id="edit-context", markup=False)
            yield Label(self._prompt, id="edit-label")
            if self._field.choices:
                yield OptionList(
                    *[self._label_for(choice.value) for choice in self._field.choices],
                    id="edit-options",
                )
            else:
                yield Input(value="" if self._field.masked else (self._field.value or ""), id="edit-input")
                hint = profile_field_shape_hint(self._field.field_type)
                if hint:
                    yield Static(hint, id="edit-hint")
                yield Static(id="edit-refusal")
            if self._box_hides_a_value:
                yield Static(tr("flows.manager.edit.masked_kept"), id="edit-masked-note")
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
                if self._offers_clear:
                    yield Button(tr("flows.manager.edit.clear"), id="btn-edit-clear")
                yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        """Focus the editor and restore an exact current choice only."""
        if not self._field.choices:
            self.query_one("#edit-input", Input).focus()
            return
        options = self.query_one("#edit-options", OptionList)
        current = next(
            (index for index, choice in enumerate(self._field.choices) if choice.value == self._field.value),
            None,
        )
        options.focus()
        options.highlighted = current

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Translate one editor button into a value, clear, or cancellation."""
        if event.button.id == "btn-edit-save":
            if self._field.choices:
                self._dismiss_highlighted_option()
            else:
                self._submit_typed(self.query_one("#edit-input", Input).value)
        elif event.button.id == "btn-edit-clear":
            self.dismiss("")
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Validate and submit the typed value."""
        self._submit_typed(event.value)

    def _submit_typed(self, value: str) -> None:
        """Dismiss with a valid value while preserving an untouched mask."""
        if self._box_hides_a_value and not value.strip():
            self.dismiss(None)
            return
        refusal = self._validate(value) if (self._validate is not None and value.strip()) else None
        if refusal is not None:
            self.query_one("#edit-refusal", Static).update(refusal)
            return
        self.dismiss(value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Submit the option explicitly selected by the operator."""
        self._dismiss_highlighted_option()

    def _dismiss_highlighted_option(self) -> None:
        highlighted = self.query_one("#edit-options", OptionList).highlighted
        if highlighted is None:
            self.dismiss(None)
            return
        self.dismiss(self._field.choices[highlighted].value)

    def action_cancel(self) -> None:
        """Dismiss without requesting a profile change."""
        self.dismiss(None)


class RepeatableRowAddScreen(ModalScreen[dict[str, str] | None]):
    """Collect one new repeatable row without deciding what may be stored.

    Blank boxes are omitted rather than interpreted as clears: a new row has
    no prior value to clear.  The application row door remains the authority
    for required fields, value shape, and relationship rules.
    """

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, section: ProfileSectionView) -> None:
        super().__init__()
        self._section = section
        # The blank projection for an empty section and every extant row both
        # carry the declaration in display order.  Keep one field per key for
        # the new row; repeated extant rows must not duplicate form controls.
        self._fields = tuple(
            field
            for index, field in enumerate(section.fields)
            if field.path.rsplit(".", 1)[-1]
            not in {earlier.path.rsplit(".", 1)[-1] for earlier in section.fields[:index]}
        )

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(tr("flows.manager.rows.add"), id="edit-label")
            for index, field in enumerate(self._fields):
                yield Label(f"{field.label}{_REQUIRED_MARK if field.required else ''}")
                if field.choices:
                    yield OptionList(*(choice.label for choice in field.choices), id=f"row-option-{index}")
                else:
                    yield Input(
                        placeholder=profile_field_shape_hint(field.field_type) or "",
                        id=f"row-input-{index}",
                    )
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-row-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-row-save", classes="-primary")

    def on_mount(self) -> None:
        if self._fields:
            first = self._fields[0]
            self.query_one("#row-option-0", OptionList).focus() if first.choices else self.query_one(
                "#row-input-0", Input
            ).focus()

    def _submitted_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for index, field in enumerate(self._fields):
            field_key = field.path.rsplit(".", 1)[-1]
            if field.choices:
                highlighted = self.query_one(f"#row-option-{index}", OptionList).highlighted
                if highlighted is not None:
                    values[field_key] = field.choices[highlighted].value
                continue
            value = self.query_one(f"#row-input-{index}", Input).value
            if value.strip():
                values[field_key] = value
        return values

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-row-save":
            self.dismiss(self._submitted_values())
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class RepeatableRowRemoveScreen(ModalScreen[bool]):
    """Require an explicit confirmation before clearing an identified row."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, section_key: str, row_key: str) -> None:
        super().__init__()
        self._section_key = section_key
        self._row_key = row_key or "base"

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(
                tr("flows.manager.rows.remove_confirm", section=self._section_key, row=self._row_key),
                id="edit-label",
            )
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-row-cancel")
                yield Button(tr("flows.confirm.yes"), id="btn-row-remove", classes="-error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-row-remove")

    def action_cancel(self) -> None:
        self.dismiss(False)


"""The profile field deciding what language this page is written in.

Named here because the page reaches for it directly, which it does for no
other field: changing it changes every label on screen including the ones
that would lead an operator to it.
"""

_LANGUAGE_KEY = "f2"
"""The key that opens the language chooser."""

_COMPLETE_SETUP_KEY = "f8"
"""The key that declares the profile's setup complete, while it is not."""

_COMPLETE_SETUP_ACTION = "complete_setup"

_LANGUAGE_ACTION = "choose_language"
"""The action that key runs.

Named because the footer entry for the key is written at render time
rather than declared beside it, and the two halves have to find each
other.
"""


_SOURCE_TITLE_LOCALE_KEYS: dict[ProfileAcquisitionSourceKey, str] = {
    ProfileAcquisitionSourceKey.CENSAL_REVIEW: "profile.journey.source.censal_review.title",
    ProfileAcquisitionSourceKey.FILED_HISTORY: "profile.journey.source.filed_history.title",
}
_SOURCE_DESCRIPTION_LOCALE_KEYS: dict[ProfileAcquisitionSourceKey, str] = {
    ProfileAcquisitionSourceKey.CENSAL_REVIEW: "profile.journey.source.censal_review.description",
    ProfileAcquisitionSourceKey.FILED_HISTORY: "profile.journey.source.filed_history.description",
}
_SOURCE_ACTION_LOCALE_KEYS: dict[ProfileAcquisitionSourceKey, str] = {
    ProfileAcquisitionSourceKey.CENSAL_REVIEW: "profile.journey.source.censal_review.action",
    ProfileAcquisitionSourceKey.FILED_HISTORY: "profile.journey.source.filed_history.action",
}


_DOCUMENT_READER_CARD_ID = "manager-document-reader"

_PLANTILLA_MEDIA_SECTION = PLANTILLA_MEDIA_PATH.split(".", 1)[0]
"""The non-repeatable section whose panel carries the average-workforce years."""

_PLANTILLA_MEDIA_BUTTON_ID = "manager-plantilla-media"

_CONTINUE_BUTTON_ID = "onboarding-continue"

_SEARCH_ID = "manager-search"

_REQUIRED_ONLY_ID = "manager-required-only"

_SEARCH_SETTLE_SECONDS = 0.15
"""How long typing pauses before the sections are filtered again.

Filtering rebuilds every section table, so doing it on each keystroke would
make the box lag behind the operator's typing on a full profile."""


class ProfileManagerScreen(AccountChromeScreen):
    """Full-screen profile overview with in-place editing."""

    SCOPED_CSS = False
    DEFAULT_CSS = (
        BASE_CSS
        + NOTICE_BAND_CSS
        + """
    #manager-context { width: 100%; height: auto; }
    #manager-requirements { width: 100%; height: auto; }
    .manager-section DataTable { height: auto; width: 100%; background: $surface; }
    """
        + tokenised("""
    #manager-onboarding { height: auto; padding: $cadrumo-space-0 $cadrumo-gutter; }
    #onboarding-heading { text-style: bold; }
    #onboarding-intro { color: $text-muted; }
    #onboarding-progress { width: 100%; }
    #onboarding-progress Bar { width: 1fr; }
    #manager-tools { height: auto; padding: $cadrumo-space-0 $cadrumo-gutter; }
    #manager-search { width: 1fr; }
    #manager-required-only { width: auto; }
    #manager-search-empty { height: auto; }
    .manager-section-summary { color: $text-muted; }
    """)
    )

    BINDINGS: ClassVar = [
        # Shown in the footer, unlike the others. The language of the page
        # is the one setting an operator may need to change before they can
        # read the page well enough to find it, so it cannot be one more
        # row in a table they are struggling with.
        #
        # Neither half of that showing is settled here, though: Textual
        # hides a binding carrying no description, and a description
        # written in a class body would be resolved once at import in
        # whichever language the process started in. Both are written by
        # :meth:`_offer_language_in_footer` on every render instead.
        Binding(_LANGUAGE_KEY, _LANGUAGE_ACTION, "", show=True),
        # After the language key, so the footer reads in key order here as it
        # does on every other destination; described by the account chrome.
        Binding("f3", "toggle_appearance", "", show=False),
        # Named on its own button rather than in the footer, which has no
        # room left for it on an eighty-column terminal.
        Binding(_COMPLETE_SETUP_KEY, _COMPLETE_SETUP_ACTION, "", show=False),
        Binding("slash", "focus_search", "", show=False),
        Binding("q", "quit", "", show=False),
        Binding("escape", "quit", "", show=False),
    ]

    def __init__(
        self,
        overview: ProfileOverview,
        *,
        persist: ProfileFieldPersist,
        add_row: Callable[[str, Mapping[str, str], int, str], ProfileOverview] | None = None,
        update_row: Callable[[str, str, Mapping[str, str], Sequence[str], int, str], ProfileOverview] | None = None,
        remove_row: Callable[[str, str, int, str], ProfileOverview] | None = None,
        complete_setup: Callable[[], ProfileOverview] | None = None,
        validate: Callable[[str, str], str | None] | None = None,
        launch_source: Callable[[ProfileAcquisitionSourceV1], Awaitable[None]] | None = None,
        credential_postures: Sequence[AcquisitionSourceCredentialPostureV1] | None = None,
        open_document_reader: Callable[[], Screen[None]] | None = None,
        list_plantilla_media: Callable[[], Sequence[PlantillaMediaYear]] | None = None,
        set_plantilla_media: Callable[[int, Decimal, PlantillaMediaState], ProfileOverview] | None = None,
        remove_plantilla_media: Callable[[int], ProfileOverview] | None = None,
    ) -> None:
        """Initialize the overview with injected projection and write doors."""
        super().__init__()
        self.overview = overview
        self._open_document_reader = open_document_reader
        """Builds the document reader page, or ``None`` when this host offers none."""
        self._complete_setup = complete_setup
        """Declares setup complete and hands back the page as storage now holds it.

        Injected like ``persist``. The store judges the record at its
        strictest setting and refuses a record still missing a required
        answer, so the page never decides completeness itself. A host that
        supplies none offers no such action at all."""
        self._launch_source = launch_source
        """Starts one declared acquisition source's operation, or ``None``.

        Injected exactly like ``persist``: this page names which source the
        operator picked and reports the intent, it does not compose an
        ``OperationController`` or know how a source actually runs. A host
        that supplies none renders every source action as present but
        disabled, never as a silent no-op button."""
        self._credential_postures: dict[ProfileAcquisitionSourceKey, AcquisitionSourceCredentialPostureV1] = {
            posture.source: posture for posture in (credential_postures or ())
        }
        """Whether each source's declared AEAT-authentication requirement is
        currently met, keyed by source. Injected from
        ``resolve_acquisition_source_credential_postures`` against the
        real :class:`AuthState`, never guessed here. A host that supplies
        none renders every source without a credential badge -- an unknown
        posture is not the same claim as "credential missing"."""
        self._validate_field = validate
        """Why the write door would refuse one path's value, or ``None``.

        Injected beside the write door and from the same authority, so the
        dialog refuses exactly what storage would refuse. A host that
        supplies none leaves every box unchecked until the write — which is
        where the refusal used to arrive, unhelpfully."""
        self._persist_field = persist
        """Writes one field and hands back the page as storage now holds it.

        Injected, not imported: the adapter tier renders a view-model and
        reports intents, exactly as the status page does. Returning the
        reloaded overview rather than ``None`` is what keeps the screen
        from ever displaying its own optimistic guess — whatever the store
        made of the value is what appears."""
        self._add_row = add_row
        self._update_row = update_row
        self._remove_row = remove_row
        """Shared repeatable-row doors, bound by composition to one profile.

        Calls carry the overview baseline captured when the dialog opened;
        completion never substitutes whichever profile happens to be visible.
        """
        self._list_plantilla_media = list_plantilla_media
        self._set_plantilla_media = set_plantilla_media
        self._remove_plantilla_media = remove_plantilla_media
        """Average-workforce doors, bound by composition to one profile.

        A year is its own identity, so these take the year rather than a
        row key or an overview baseline: the application service reads the
        record once and compare-and-swaps against that read. The writes hand
        back the page as storage now holds it, like every other door here,
        so the page and its revision never go stale behind a declared year.
        """
        self._pending_listing: Worker[tuple[PlantillaMediaYear, ...]] | None = None
        """The in-flight read of the declared years, or ``None``.

        Read off the event loop for the reason writes are: it decrypts the
        record. At most one runs, so a double press opens one dialog."""
        self._field_by_key: dict[str, ProfileFieldView] = {}
        self._table_by_section: dict[str, DataTable[str]] = {}
        """The live table per section, so a single-field edit can address a
        cell instead of rebuilding the widget tree.

        Repopulated by every full render, which is the only thing that
        replaces these widgets; an entry here is therefore always the table
        currently mounted for that section."""
        self._columns_by_section: dict[str, list[ColumnKey]] = {}
        """Column keys as ``add_columns`` handed them back, per section.

        ``update_cell`` addresses a cell by (row key, column key), and the
        row key is already the field path. Retaining the column keys is the
        only missing half of that coordinate."""
        self._pending_write: Worker[ProfileOverview] | None = None
        """The one in-flight field write, or ``None`` when storage is idle.

        Writes are serialised rather than overlapped because the door is a
        read-modify-write of the WHOLE fact set: it loads the record, merges
        the new fact into the existing set, and saves the result. Two writes
        in flight together would each merge into the same pre-edit snapshot,
        so the second save would drop the first operator's field. Serialising
        is a correctness requirement here, not a tidiness preference."""
        self._pending_write_path: str | None = None
        """Which field the in-flight write is for, or ``None`` when idle.

        Kept because one field decides how the whole page is worded, so
        settling its write needs a different redraw from every other."""
        self._pending_completion: Worker[ProfileOverview] | None = None
        """The in-flight setup completion, or ``None``.

        Serialised against field writes for the reason those are serialised
        against each other: both replace the whole record."""
        self._onboarding = complete_setup is not None and overview.setup_state is ProfileSetupState.INCOMPLETE
        """Whether this page opened as the setup walk of an unfinished profile.

        Fixed at construction so the walk's header stays in place after the
        last step, where it hands the operator on to the workbench."""
        self._required_only = self._onboarding
        """Whether sections show only the answers setup requires right now."""
        self._query = ""
        """The operator's search text; empty shows every field the filter allows."""
        self._search_timer: Timer | None = None
        self._walking = False
        """Whether Continue is leading the operator from one required answer to the next.

        Set when Continue opens a question and cleared as soon as the
        operator cancels, a save is refused, or nothing required is left, so
        a later unrelated edit never reopens the walk by surprise."""
        self._render_lock = asyncio.Lock()
        """Serialises every rebuild of the section tables.

        A search, a settled write and a language change each rebuild tables
        across several loop turns; two interleaved would mount rows into
        tables the other has already replaced."""

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="manager-banner", classes="cadrumo-banner")
        yield PinnedStatusBar(id="manager-status")
        if self._onboarding:
            with Vertical(id="manager-onboarding"):
                yield Static(id="onboarding-heading", markup=False)
                yield Static(id="onboarding-intro", markup=False)
                yield ProgressBar(id="onboarding-progress", show_eta=False)
                yield Static(id="onboarding-step", markup=False)
                yield Button("", id=_CONTINUE_BUTTON_ID, classes="-primary", compact=True)
        with Horizontal(id="manager-tools"):
            yield Input(id=_SEARCH_ID, compact=True)
            yield Checkbox("", value=self._required_only, id=_REQUIRED_ONLY_ID, compact=True)
        with ContentScroll(id="manager-body", classes="cadrumo-scroll"), Vertical(classes="cadrumo-column"):
            yield Vertical(id="manager-context")
            yield Static(id="manager-search-empty", classes="cadrumo-note", markup=False)
            # Filled by :meth:`_redraw`, not here: a card's text is fixed when
            # it is built, so cards composed once would keep the language the
            # page opened in after the operator changes it.
            with DisclosureGroup(title="", collapsed=self._onboarding, id="manager-sources-fold"):
                yield Static(id="manager-sources-summary", classes="manager-section-summary", markup=False)
                yield Vertical(id="manager-sources", classes="cadrumo-panel")
            missing = frozenset(self.overview.missing_required)
            for section in self.overview.sections:
                # Only a section still owing a required answer starts open.
                # Decided here rather than on render: a fold that opens scrolls
                # itself into view, which would open the page mid-way down.
                owing = any(field.path in missing for field in section.fields)
                with DisclosureGroup(title="", collapsed=not owing, id=f"fold-{section.key}"):
                    yield Static(id=f"summary-{section.key}", classes="manager-section-summary", markup=False)
                    yield Static(id=f"section-{section.key}", classes="manager-section cadrumo-panel")
        yield Footer()

    async def on_mount(self) -> None:
        """Install the presentation theme and render the supplied overview."""
        install_cadrumo_themes(self.app)
        # The shared theme sizes every Input to the full row, which would push
        # the required-only switch beside the search box off the screen.
        self.query_one(f"#{_SEARCH_ID}", Input).styles.width = "1fr"
        await self._redraw()
        if self._onboarding:
            self.query_one(f"#{_CONTINUE_BUTTON_ID}", Button).focus()
        # Whatever took focus while the page was building may have scrolled
        # the body; the page opens at its top.
        body = self.query_one("#manager-body", ContentScroll)
        self.call_after_refresh(body.scroll_home, animate=False, immediate=True)

    def _source_cards(self) -> list[SourceActionCard]:
        """Build one card per known source, worded in the page's current language."""
        return [
            SourceActionCard(
                SourceActionDescriptor(
                    title=tr(_SOURCE_TITLE_LOCALE_KEYS[source.key]),
                    description=tr(_SOURCE_DESCRIPTION_LOCALE_KEYS[source.key]),
                    action_label=tr(_SOURCE_ACTION_LOCALE_KEYS[source.key]),
                    credential_requirement=self._credential_requirement_badge(source.key),
                ),
                id=f"source-{source.key.value}",
            )
            for source in known_profile_acquisition_sources()
        ]

    def _credential_requirement_badge(self, key: ProfileAcquisitionSourceKey) -> CredentialRequirement | None:
        """Resolve one source's credential badge from its real posture, if supplied.

        Returns the label and status as ONE record so a caller cannot pass
        half of a requirement: the absence of a fact and a fact are the only
        two outcomes this can have.
        """
        posture = self._credential_postures.get(key)
        if posture is None or not posture.requires_aeat_authentication:
            return None
        if posture.credential_held:
            return CredentialRequirement(
                tr("profile.journey.source.credential_requirement.held"), RequirementStatus.REQUIRED_PRESENT
            )
        return CredentialRequirement(
            tr("profile.journey.source.credential_requirement.missing"), RequirementStatus.REQUIRED_MISSING
        )

    def _sync_source_actions(self) -> None:
        """Hide a launch button with no door, and disable one whose credential is missing.

        With no door the button could only ever refuse, so it is not shown;
        the card stays, so the source is still named and described. A missing
        credential disables a wired button instead of hiding it: that is
        something the operator can fix, and the card's badge says what.
        """
        door_ready = self._launch_source is not None
        for source in known_profile_acquisition_sources():
            posture = self._credential_postures.get(source.key)
            credential_ready = posture is None or not posture.requires_aeat_authentication or posture.credential_held
            button = self.query_one(f"#source-{source.key.value}", SourceActionCard).query_one(Button)
            button.display = door_ready
            button.disabled = not (door_ready and credential_ready)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Launch the pressed source's operation through the injected door only.

        Refused while a field write is in flight, for the reason the edit
        entry points give: an acquisition source rewrites profile facts by
        merging into the record as it loads it, so one started before the
        operator's edit had landed would merge into the pre-edit facts and
        drop that field. This was the one mutation entry point without the
        guard, and the omission is currently masked rather than harmless --
        the installed launcher supplies no ``launch_source``, so the button is
        disabled and the handler returns above. It becomes reachable the moment
        that door is wired.
        """
        if event.button.id == "manager-complete-setup":
            self.action_complete_setup()
            return
        if event.button.id == _CONTINUE_BUTTON_ID:
            await self.action_continue_setup()
            return
        button_id = event.button.id or ""
        if button_id.startswith("manager-add-row-"):
            self._open_add_row(button_id.removeprefix("manager-add-row-"))
            return
        if button_id.startswith("manager-remove-row-"):
            self._open_remove_selected_row(button_id.removeprefix("manager-remove-row-"))
            return
        if button_id == _PLANTILLA_MEDIA_BUTTON_ID:
            self._open_plantilla_media()
            return
        card = event.button.parent
        if isinstance(card, SourceActionCard) and card.id == _DOCUMENT_READER_CARD_ID:
            if self._open_document_reader is not None:
                self.app.push_screen(self._open_document_reader())
            return
        if self._launch_source is None:
            return
        if not isinstance(card, SourceActionCard) or card.id is None or not card.id.startswith("source-"):
            return
        key = card.id.removeprefix("source-")
        source = next(
            (candidate for candidate in known_profile_acquisition_sources() if candidate.key.value == key), None
        )
        if source is None:
            return
        # Checked here rather than on entry so a press that resolves to no
        # source at all is not answered with a message about a write.
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        await self._launch_source(source)

    def _section(self, key: str) -> ProfileSectionView | None:
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

    def _existing_row_key(self, section: ProfileSectionView, table: DataTable[str] | None = None) -> str | None:
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

    def _open_add_row(self, section_key: str) -> None:
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

    def _open_remove_selected_row(self, section_key: str) -> None:
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
    def _plantilla_media_offered(self) -> bool:
        """Whether this host wired the doors the average-workforce dialog needs."""
        return self._list_plantilla_media is not None and (
            self._set_plantilla_media is not None or self._remove_plantilla_media is not None
        )

    def _open_plantilla_media(self) -> None:
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

    def _settle_listing(self, worker: Worker[tuple[PlantillaMediaYear, ...]]) -> None:
        """Open the dialog on the years storage holds, or say why they could not be read."""
        self._pending_listing = None
        if worker.state is WorkerState.SUCCESS and worker.result is not None:
            self.app.push_screen(PlantillaMediaScreen(worker.result), self._apply_plantilla_media)
            return
        self._refuse_worker(worker.error, message_key="flows.manager.plantilla_media.list_failed")

    def _apply_plantilla_media(self, request: PlantillaMediaRequest | None) -> None:
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

    # ── rendering ───────────────────────────────────────────────────────

    async def _redraw(self) -> None:
        """Rebuild the profile context and every schema section table.

        This is the wholesale redraw: it destroys and remounts every table.
        It is what ``on_mount`` needs, and what an action returning a fresh
        overview needs, because either can hand the page a structurally
        different profile. A single-field edit goes through
        :meth:`_apply_overview` instead, which repaints only the cells whose
        content actually moved — the same page, at a fraction of the work.
        """
        async with self._render_lock:
            await self._redraw_now()

    async def _redraw_now(self) -> None:
        """The wholesale redraw, for a caller already holding the render lock."""
        self._render_chrome()
        self.refresh_account_chrome()
        self._clear_notice()
        await self._render_profile_context()
        sources = self.query_one("#manager-sources", Vertical)
        await sources.remove_children()
        await sources.mount_all(self._source_cards())
        if self._open_document_reader is not None:
            await sources.mount(
                SourceActionCard(
                    SourceActionDescriptor(
                        title=tr("tui.local_reader.card.title"),
                        description=tr("tui.local_reader.card.description"),
                        action_label=tr("tui.local_reader.card.action"),
                    ),
                    id=_DOCUMENT_READER_CARD_ID,
                )
            )
        self._sync_source_actions()
        await self._render_sections()
        self._render_onboarding()

    async def _render_sections(self, *, disclose_matches: bool = False) -> None:
        """Rebuild every section table from the rows the filters leave visible.

        A section with no visible row folds away entirely rather than showing
        an empty table, so "only required" and a search both reduce the page
        to what the operator is looking for. ``disclose_matches`` opens every
        section still showing rows, which is what a search is for; otherwise
        a section keeps whatever fold state the operator left it in.
        """
        self._field_by_key.clear()
        self._table_by_section.clear()
        self._columns_by_section.clear()
        any_visible = False
        for section in self.overview.sections:
            # One section per loop turn: building every table in one pass held
            # the loop for over half a second on a complete profile.
            await asyncio.sleep(0)
            visible = self._visible_fields(self.overview, section)
            fold = self.query_one(f"#fold-{section.key}", DisclosureGroup)
            fold.title = self._fold_title(self.overview, section)
            fold.display = bool(visible)
            any_visible = any_visible or bool(visible)
            if disclose_matches and visible:
                fold.collapsed = False
            self.query_one(f"#summary-{section.key}", Static).update(section.summary)
            panel = self.query_one(f"#section-{section.key}", Static)
            await panel.remove_children()
            table: DataTable[str] = ContentDataTable[str](cursor_type="row", zebra_stripes=True)
            await panel.mount(table)
            self._table_by_section[section.key] = table
            self._columns_by_section[section.key] = [
                table.add_column(tr("flows.manager.column.state")),
                table.add_column(tr("flows.manager.column.field"), width=_FIELD_COLUMN_WIDTH),
                table.add_column(tr("flows.manager.column.value")),
            ]
            for field in section.fields:
                self._field_by_key[field.path] = field
            for field in visible:
                # ``height=None`` is what lets a field name past the capped
                # column width wrap onto more lines instead of being clipped
                # or pushing the value column off-screen — see
                # ``_FIELD_COLUMN_WIDTH``.
                table.add_row(*self._rendered_row(field), key=field.path, height=None)
            if section.repeatable:
                # These use the same established CLI wording, rather than
                # introducing a second vocabulary before the locale pass.
                await panel.mount(
                    Button(
                        tr("flows.manager.rows.add"),
                        id=f"manager-add-row-{section.key}",
                        compact=True,
                    )
                )
                if self._has_existing_row(section):
                    await panel.mount(
                        Button(
                            tr("flows.manager.rows.remove"),
                            id=f"manager-remove-row-{section.key}",
                            compact=True,
                        )
                    )
            if section.key == _PLANTILLA_MEDIA_SECTION and self._plantilla_media_offered:
                # The years are indexed instances of one field, so the section
                # itself is not repeatable and offers no row buttons. A year is
                # declared, replaced or withdrawn as a whole through its dialog.
                await panel.mount(
                    Button(
                        tr("profile.schema.field.irpf.plantilla_media.label"),
                        id=_PLANTILLA_MEDIA_BUTTON_ID,
                        compact=True,
                    )
                )
        searching = bool(self._query.strip())
        # Importing is an alternative to typing, not a match for a search.
        self.query_one("#manager-sources-fold", DisclosureGroup).display = not searching
        empty = self.query_one("#manager-search-empty", Static)
        empty.display = searching and not any_visible
        if empty.display:
            empty.update(tr("flows.manager.onboarding.search_empty", query=self._query.strip()))

    def _required_now(self, overview: ProfileOverview, field: ProfileFieldView) -> bool:
        """Whether setup requires this row now: missing, or answered and required.

        A repeatable section's template row is marked required but demands
        nothing until the operator adds a row, so it is not counted here;
        the overview's own missing list is the authority on what is owed.
        """
        return field.path in overview.missing_required or (field.required and field.present)

    def _visible_fields(self, overview: ProfileOverview, section: ProfileSectionView) -> tuple[ProfileFieldView, ...]:
        """The section's rows that the required-only switch and the search leave in view.

        A search that names the section itself keeps all of its rows, so an
        operator who types "IVA" sees the whole IVA section rather than only
        the rows whose own label happens to contain the word.
        """
        fields = section.fields
        if self._required_only:
            fields = tuple(field for field in fields if self._required_now(overview, field))
        query = self._query.strip().casefold()
        if not query or query in section.title.casefold() or query in section.summary.casefold():
            return fields
        return tuple(
            field for field in fields if query in " ".join((field.path, *self._rendered_row(field)[1:])).casefold()
        )

    def _fold_title(self, overview: ProfileOverview, section: ProfileSectionView) -> str:
        """Title a section's fold with how much setup still needs from it.

        A glyph as well as words, so the state reads without colour.
        """
        missing = sum(1 for field in section.fields if field.path in overview.missing_required)
        if missing:
            return tr("flows.manager.onboarding.section_pending", title=section.title, missing=missing)
        if any(self._required_now(overview, field) for field in section.fields):
            return tr(
                "flows.manager.onboarding.section_done",
                title=section.title,
                present=section.present_count,
                total=section.total_count,
            )
        return self._section_title(section)

    def _render_onboarding(self) -> None:
        """Word the setup walk's header: progress, the current step, and what Continue does."""
        self.query_one("#manager-sources-summary", Static).update(tr("flows.manager.onboarding.sources_summary"))
        self.query_one("#manager-sources-fold", DisclosureGroup).title = tr("flows.manager.onboarding.sources_title")
        self.query_one(f"#{_SEARCH_ID}", Input).placeholder = tr("flows.manager.onboarding.search_placeholder")
        self.query_one(f"#{_REQUIRED_ONLY_ID}", Checkbox).label = tr("flows.manager.onboarding.required_only")
        if not self._onboarding:
            return
        overview = self.overview
        required = [
            (section, field)
            for section in overview.sections
            for field in section.fields
            if self._required_now(overview, field)
        ]
        missing = frozenset(overview.missing_required)
        # A requirement with no row to show still counts, so the bar never
        # reads as finished while the store would refuse completion.
        total = len(required) + sum(1 for path in missing if path not in self._field_by_key)
        answered = sum(1 for _section, field in required if field.path not in missing)
        done = overview.setup_state is not ProfileSetupState.INCOMPLETE
        steps: list[ProfileSectionView] = []
        for section, _field in required:
            if section not in steps:
                steps.append(section)
        current = next((section for section, field in required if field.path in missing), None)
        bar = self.query_one("#onboarding-progress", ProgressBar)
        bar.update(total=total + 1, progress=answered + (1 if done else 0))
        progress = tr("flows.manager.onboarding.progress", answered=answered, total=total)
        if done:
            step = tr("flows.manager.onboarding.done")
            action = tr("flows.manager.onboarding.to_workbench")
        elif current is not None:
            step = tr(
                "flows.manager.onboarding.step",
                step=steps.index(current) + 1,
                steps=len(steps) + 1,
                section=current.title,
            )
            action = tr("flows.manager.onboarding.continue")
        else:
            step = "\n".join(
                (
                    tr("flows.manager.onboarding.step_finish", step=len(steps) + 1, steps=len(steps) + 1),
                    tr("flows.manager.onboarding.ready"),
                )
            )
            action = tr("flows.manager.onboarding.finish")
        self.query_one("#onboarding-heading", Static).update(tr("flows.manager.onboarding.heading"))
        self.query_one("#onboarding-intro", Static).update(tr("flows.manager.onboarding.intro"))
        self.query_one("#onboarding-step", Static).update(f"{progress} · {step}")
        self.query_one(f"#{_CONTINUE_BUTTON_ID}", Button).label = action

    async def _apply_overview(self, updated: ProfileOverview) -> None:
        """Show ``updated`` by repainting only what differs from the page on screen.

        Most edits leave the row SET alone: the overview is projected by
        walking the profile SCHEMA, so every declared field yields a row
        whether or not it holds a value. What such an edit CAN change is a
        row's rendered content — and not only the edited row's, since the
        write door normalises values and re-derives presence and
        completeness. So rather than assume the edited path is the only thing
        that moved, this diffs the old page against the new one and writes
        exactly the cells that differ: usually one row, occasionally a few,
        never all of them.

        Some edits DO move the row set, because how many rows a repeated
        fact stands for is the record's to say, not the schema's: clearing
        the last leaf of a censal divergence retires its rows, and filling a
        row of a repeatable section can add a group. The same holds for the
        rows the filters leave visible, since an answer can change what is
        required or what a search matches. The structural comparison is what
        makes that safe — the shapes stop matching and this falls back to the
        full rebuild rather than writing into coordinates the new page no
        longer has.
        """
        async with self._render_lock:
            previous = self.overview
            self.overview = updated
            if self._shape_of(previous) != self._shape_of(updated):
                await self._redraw_now()
                return

            self._render_chrome()
            self._clear_notice()
            await self._render_profile_context()
            for was, now in zip(previous.sections, updated.sections, strict=True):
                table = self._table_by_section.get(now.key)
                columns = self._columns_by_section.get(now.key)
                if table is None or columns is None:
                    # The page was never fully rendered, so there are no cells to
                    # address. Build it rather than silently dropping the update.
                    await self._redraw_now()
                    return
                self.query_one(f"#fold-{now.key}", DisclosureGroup).title = self._fold_title(updated, now)
                for after in now.fields:
                    self._field_by_key[after.path] = after
                for before, after in zip(
                    self._visible_fields(previous, was), self._visible_fields(updated, now), strict=True
                ):
                    old_cells = self._rendered_row(before)
                    new_cells = self._rendered_row(after)
                    if old_cells == new_cells:
                        continue
                    for column, old_cell, new_cell in zip(columns, old_cells, new_cells, strict=True):
                        if old_cell != new_cell:
                            # ``update_width`` defaults off, which would clip a value
                            # that grew past the column's current width — the full
                            # rebuild sizes columns as it adds rows, and this is the
                            # equivalent for a cell written in place.
                            table.update_cell(after.path, column, new_cell, update_width=True)
            self._render_onboarding()

    async def _render_profile_context(self) -> None:
        """Render actionable profile context in the scrollable page body.

        An idle operation bar has nothing to report. Schema gaps and profile
        advisories describe the profile rather than a running operation, so
        they live with the profile content and disappear entirely when there
        is no gap or advisory to show.
        """
        missing_fields = self.overview.missing_required_fields
        resolved_paths = {field.path for field in missing_fields}
        missing_labels = [field.label for field in missing_fields]
        missing_labels.extend(
            tr("flows.manager.required_field_unavailable")
            for path in self.overview.missing_required
            if path not in resolved_paths
        )
        # The setup walk's header already says what is missing and leads to
        # it, so the page does not repeat the list beneath it.
        requirements = (
            tr(
                "flows.manager.profile_missing_fields",
                count=len(self.overview.missing_required),
                fields=", ".join(missing_labels),
            )
            if self.overview.missing_required and not self._onboarding
            else ""
        )
        context = self.query_one("#manager-context", Vertical)
        await context.remove_children()
        if requirements:
            await context.mount(
                Static(requirements, id="manager-requirements", classes="cadrumo-note", markup=False),
            )
        if self._completion_offered and not self._onboarding:
            # The setup walk's Continue finishes setup itself, so a second
            # button for the same step would only compete with it.
            await context.mount(
                Button(
                    tr("flows.manager.complete_setup.button", key=_COMPLETE_SETUP_KEY.upper()),
                    id="manager-complete-setup",
                    compact=True,
                )
            )
        if self.overview.notices:
            await context.mount(
                NoticeBand(
                    tuple(notice_presentation(notice) for notice in self.overview.notices),
                    id="manager-notice-band",
                )
            )

    @staticmethod
    def _section_title(section: ProfileSectionView) -> str:
        """Render one section's border title with its filled-in count."""
        return tr(
            "flows.manager.section_title",
            title=section.title,
            present=section.present_count,
            total=section.total_count,
        )

    @staticmethod
    def _rendered_row(field: ProfileFieldView) -> tuple[str, str, str]:
        """The three cells a field occupies, as the single authority on both paths.

        The full rebuild and the incremental update must agree on what a row
        looks like, or an edited row would drift from its unedited siblings.
        Deriving both from here is what makes the diff comparison meaningful:
        it compares exactly the strings that get written.

        A row belonging to one instance of a repeated fact is named by that
        instance. The projection states which instance as data and leaves
        the presentation here, so the schema's translated label is never
        edited to carry it.
        """
        label = f"{field.label}{_REQUIRED_MARK}" if field.required else field.label
        if field.row_index is not None:
            label = f"{field.row_index}{_ROW_INDEX_SEPARATOR}{label}"
        value = field.value or ""
        if value and field.choices:
            value = next(
                (choice.label for choice in field.choices if choice.value == value),
                tr("flows.manager.choice_unavailable"),
            )
        return (
            _PRESENT_GLYPH if field.present else _ABSENT_GLYPH,
            label,
            value,
        )

    def _shape_of(self, overview: ProfileOverview) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """The page's row layout: section keys, each with its visible field paths in order.

        Two overviews sharing a shape address the same cells, which is the
        precondition for updating one in place from the other.
        """
        return tuple(
            (section.key, tuple(field.path for field in self._visible_fields(overview, section)))
            for section in overview.sections
        )

    def _render_chrome(self) -> None:
        """Resolve all manager-owned chrome under the active output language."""
        title = tr("flows.manager.title", profile=self.overview.label)
        self.title = title
        self.sub_title = ""
        self.query_one("#manager-banner", Static).update(title)
        self._offer_language_in_footer()

    def _language_field(self) -> ProfileFieldView | None:
        """The field holding the page's language, if the schema declares one.

        Read from the overview rather than the rendered row index because
        the chrome is written before the tables are rebuilt, and because
        the footer and the chooser must agree on whether there is anywhere
        to put an answer.
        """
        for section in self.overview.sections:
            for field in section.fields:
                if field.path == PROFILE_OUTPUT_LANGUAGE_PATH:
                    return field
        return None

    def _offer_language_in_footer(self) -> None:
        """Name the language key in the footer, in the language now on screen.

        The binding declares itself shown, but Textual forces ``show`` off
        for a binding carrying no description, so the one key meant to be
        visible was bound and invisible — and an invisible key is exactly
        the reachability it exists to provide. The description cannot be
        declared beside the binding either: a class body runs once at
        import, so the footer would name the setting in whichever language
        the process started in, on a page the operator has just switched
        away from it.

        So the entry is composed here, from the field's own label, and
        recomposed by every render. The key is offered only while the
        schema declares somewhere to put the answer; advertising it
        otherwise would promise a chooser that could only refuse.

        The key's entry is replaced rather than added to, and replaced by
        assignment rather than edited in place. Textual's own ``bind`` and
        ``BindingsMap.merge`` both append, and this runs on every redraw,
        so either would show the key once more each time the page was
        rebuilt. The instance's binding table is a shallow copy of the
        class's, sharing the very lists it holds, so editing one in place
        would re-describe the key for every manager the process opens;
        putting a new list in this instance's table cannot.
        """
        field = self._language_field()
        # The short account name rather than the field's own label, so the
        # footer keeps every key on an eighty-column terminal.
        label = tr("tui.root.account_key.language") if field is not None else ""
        bindings = self._bindings.key_to_bindings.get(_LANGUAGE_KEY)
        if bindings is None:
            return
        self._bindings.key_to_bindings[_LANGUAGE_KEY] = [
            replace(binding, description=label, show=bool(label)) if binding.action == _LANGUAGE_ACTION else binding
            for binding in bindings
        ]
        self.refresh_bindings()

    # ── editing ─────────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
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

    def _open_field_editor(self, field: ProfileFieldView, *, context: str | None = None) -> None:
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

    # ── setup walk ──────────────────────────────────────────────────────

    async def action_continue_setup(self) -> None:
        """Take the one next step of setup: the next required question, finishing, or leaving.

        Only what setup requires is asked, in page order, one question at a
        time; everything optional stays in its folded section. With nothing
        left to answer, Continue asks the store to declare setup complete,
        and once it is, Continue leaves for the workbench.
        """
        if self._pending_write is not None or self._pending_completion is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        if self.overview.setup_state is not ProfileSetupState.INCOMPLETE:
            self._walking = False
            await self.action_quit()
            return
        field = next(iter(self.overview.missing_required_fields), None)
        if field is None:
            self._walking = False
            if self.overview.missing_required:
                self._refuse(tr("flows.manager.complete_setup.incomplete_unnamed"))
                return
            self.action_complete_setup()
            return
        section = self._section(field.path.split(".", 1)[0])
        if section is None:
            return
        fold = self.query_one(f"#fold-{section.key}", DisclosureGroup)
        fold.collapsed = False
        fold.scroll_visible()
        required = [
            candidate
            for candidate_section in self.overview.sections
            for candidate in candidate_section.fields
            if self._required_now(self.overview, candidate)
        ]
        number = 1 + sum(1 for candidate in required if candidate.present)
        context = "\n".join(
            (
                tr(
                    "flows.manager.onboarding.question",
                    number=number,
                    total=len(required),
                    section=section.title,
                ),
                section.summary,
            )
        )
        self._walking = True
        self._open_field_editor(field, context=context)

    def _carry_walk_on(self) -> None:
        """After an answer lands, open the next required question, or hand back to Continue."""
        if not self._walking:
            return
        if self.overview.missing_required_fields:
            self.run_worker(self.action_continue_setup(), group="profile-setup-walk", exclusive=True)
            return
        self._walking = False
        if self._onboarding:
            self.query_one(f"#{_CONTINUE_BUTTON_ID}", Button).focus()

    # ── search and filters ──────────────────────────────────────────────

    def action_focus_search(self) -> None:
        """Move the cursor to the search box."""
        self.query_one(f"#{_SEARCH_ID}", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the sections once typing in the search box pauses."""
        if event.input.id != _SEARCH_ID:
            return
        self._query = event.value
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(_SEARCH_SETTLE_SECONDS, self._apply_filters)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Show every field, or only the answers setup requires."""
        if event.checkbox.id != _REQUIRED_ONLY_ID:
            return
        self._required_only = event.value
        self.run_worker(self._apply_filters(), group="profile-filter")

    async def _apply_filters(self) -> None:
        """Rebuild the sections under the current search and required-only switch."""
        self._search_timer = None
        async with self._render_lock:
            await self._render_sections(disclose_matches=bool(self._query.strip()))
            self._render_onboarding()
        # Each fold a search opens scrolls itself into view; the results read
        # from the top.
        body = self.query_one("#manager-body", ContentScroll)
        self.call_after_refresh(body.scroll_home, animate=False, immediate=True)

    def _validator_for(self, field: ProfileFieldView) -> Callable[[str], str | None] | None:
        """Bind the injected judge to one field, or ``None`` when there is none.

        The dialog asks about a value; the door asks about a value AT A
        PATH, because what is acceptable is a property of the declaration
        rather than of the string. Binding the path here is what lets the
        dialog stay ignorant of which field it is showing.
        """
        if self._validate_field is None:
            return None
        path = field.path
        return lambda value: self._validate_field(path, value) if self._validate_field is not None else None

    def _apply_edit_for(self, field: ProfileFieldView):
        """Build the dismissal callback that persists one field's new value."""
        baseline_revision = self.overview.record_revision
        baseline_digest = self.overview.content_digest

        def _apply(value: str | None) -> None:
            if value is None:
                return
            # A blank submission is a CLEAR downstream, so on a required
            # field it asks to remove something the schema says must be
            # there. Refuse at the box rather than letting the write door
            # raise: dismissing the dialog is how "leave this alone" is
            # expressed, and an empty box is not that.
            if field.required and not value.strip():
                self._refuse(tr("flows.manager.edit.required_blank", field=field.label))
                return
            section = self._section(field.path.split(".", 1)[0])
            if section is not None and section.repeatable:
                row_key = self._row_key_for_field(section, field)
                self._update_repeatable_row(
                    section.key,
                    row_key,
                    {field.path.rsplit(".", 1)[-1]: value.strip()} if value.strip() else {},
                    () if value.strip() else (field.path.rsplit(".", 1)[-1],),
                    baseline_revision,
                    baseline_digest,
                )
                return
            self._persist(field.path, value, baseline_revision, baseline_digest)

        return _apply

    def _persist(self, path: str, value: str, expected_revision: int, expected_content_digest: str) -> None:
        """Write one field through the injected door, off the event loop.

        The write reaches encrypted storage and takes long enough to be felt.
        Run inline it would block Textual's loop for its whole duration, so
        the page would stop repainting and stop answering keys — the operator
        reads that as a frozen application rather than a slow save. It
        therefore runs on a worker thread, and the page is updated from
        :meth:`on_worker_state_changed` once storage has spoken.

        The context is copied into the thread because the write door resolves
        the active profile bucket from a context variable; a bare thread would
        not see it and every write would fail to find a profile.

        A refusal is reported in the notice line rather than raised, for the
        same reason the action buttons catch: the operator is mid-page and an
        exception would take the whole screen down over one rejected value.
        Because the door now raises on a worker thread, ``exit_on_error`` is
        off so the failure is held on the worker for the UI task to read,
        rather than escaping into the thread and leaving the page silently
        unchanged.
        """
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        write_context = copy_context()

        def _write() -> ProfileOverview:
            written = cast(
                "ProfileOverview | None",
                write_context.run(self._persist_field, path, value, expected_revision, expected_content_digest),
            )
            if written is None:
                # The door declares it hands back the reloaded page, so this
                # is a broken contract rather than a refused value. Raised
                # here it lands on the worker's error and reaches the
                # operator as itself; returned, it would be reported as
                # "could not be saved" — which would be a lie about a write
                # that may well have landed.
                message = "the profile write door returned no overview to render"
                raise TypeError(message)
            return written

        self._pending_write_path = path
        self._pending_write = self.run_worker(
            _write,
            name="profile-field-write",
            group="profile-field-write",
            exit_on_error=False,
            thread=True,
        )

    def _add_repeatable_row(
        self,
        section_key: str,
        values: Mapping[str, str] | None,
        expected_revision: int,
        expected_content_digest: str,
    ) -> None:
        """Publish one explicitly requested row against the opened baseline."""
        door = self._add_row
        if values is None or door is None:
            return
        self._run_row_write(
            f"{section_key}:add",
            lambda: door(section_key, values, expected_revision, expected_content_digest),
        )

    def _update_repeatable_row(
        self,
        section_key: str,
        row_key: str,
        values: Mapping[str, str],
        clear_fields: Sequence[str],
        expected_revision: int,
        expected_content_digest: str,
    ) -> None:
        """Modify or explicitly clear the row that supplied the selected field."""
        door = self._update_row
        if door is None:
            return
        self._run_row_write(
            f"{section_key}:{row_key or 'base'}",
            lambda: door(section_key, row_key, values, clear_fields, expected_revision, expected_content_digest),
        )

    def _remove_repeatable_row(
        self,
        section_key: str,
        row_key: str,
        expected_revision: int,
        expected_content_digest: str,
        confirmed: bool,
    ) -> None:
        """Clear an identified row only after the confirmation modal affirmed it."""
        door = self._remove_row
        if not confirmed or door is None:
            return
        self._run_row_write(
            f"{section_key}:{row_key or 'base'}",
            lambda: door(section_key, row_key, expected_revision, expected_content_digest),
        )

    def _run_row_write(self, identity: str, write: Callable[[], ProfileOverview]) -> None:
        """Run a shared row door once; a duplicate activation cannot start another CAS write."""
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        write_context = copy_context()

        def _write() -> ProfileOverview:
            written = cast("ProfileOverview | None", write_context.run(write))
            if written is None:
                raise TypeError("the profile row write door returned no overview to render")
            return written

        self._pending_write_path = identity
        self._pending_write = self.run_worker(
            _write,
            name="profile-row-write",
            group="profile-field-write",
            exit_on_error=False,
            thread=True,
        )

    # ── setup completion ────────────────────────────────────────────────

    @property
    def _completion_offered(self) -> bool:
        """Whether the page offers to declare setup complete right now."""
        return self._complete_setup is not None and self.overview.setup_state is ProfileSetupState.INCOMPLETE

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Hide the completion key once there is nothing to complete."""
        if action == _COMPLETE_SETUP_ACTION:
            return self._completion_offered
        return super().check_action(action, parameters)

    def action_complete_setup(self) -> None:
        """Ask the store to declare this profile's setup complete, off the event loop."""
        door = self._complete_setup
        if door is None or not self._completion_offered:
            return
        if self._pending_write is not None or self._pending_completion is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        completion_context = copy_context()
        self.query_one("#manager-status", PinnedStatusBar).show_progress(tr("flows.manager.complete_setup.running"))
        self._pending_completion = self.run_worker(
            lambda: completion_context.run(door),
            name="profile-complete-setup",
            group="profile-complete-setup",
            exit_on_error=False,
            thread=True,
        )

    async def _settle_completion(self, worker: Worker[ProfileOverview]) -> None:
        """Show the completed page, or why the store would not complete it."""
        self._pending_completion = None
        if worker.state is WorkerState.SUCCESS and worker.result is not None:
            self.overview = worker.result
            await self._redraw()
            self.refresh_bindings()
            self.query_one("#manager-status", PinnedStatusBar).show_success(
                tr("flows.manager.complete_setup.completed")
            )
            if self._onboarding:
                self.query_one(f"#{_CONTINUE_BUTTON_ID}", Button).focus()
            return
        if isinstance(worker.error, ProfileSchemaValidationError):
            missing = [field.label for field in self.overview.missing_required_fields]
            self._refuse(
                tr("flows.manager.complete_setup.incomplete", fields=", ".join(missing))
                if missing
                else tr("flows.manager.complete_setup.incomplete_unnamed")
            )
            return
        self._refuse_worker(worker.error, message_key="flows.manager.complete_setup.failed")

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Land one finished worker back on Textual's UI task.

        Widgets are only safe to touch from this task, so every repaint
        waits until here rather than happening in the worker.
        """
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}:
            return
        event_worker = cast("object", event.worker)
        pending_write = self._pending_write
        if pending_write is not None and event_worker is pending_write:
            await self._settle_write(pending_write)
            return
        pending_completion = self._pending_completion
        if pending_completion is not None and event_worker is pending_completion:
            await self._settle_completion(pending_completion)
            return
        pending_listing = self._pending_listing
        if pending_listing is not None and event_worker is pending_listing:
            self._settle_listing(pending_listing)
            return

    async def _settle_write(self, worker: Worker[ProfileOverview]) -> None:
        """Show what storage made of one finished field write."""
        self._pending_write = None
        written_path = self._pending_write_path
        self._pending_write_path = None
        if worker.state is WorkerState.SUCCESS and worker.result is not None:
            if worker.result.profile_id != self.overview.profile_id:
                # A completion for another profile must never repaint this
                # screen. Installed composition captures profile_id, and this
                # guard makes a broken host a refusal rather than a redirect.
                self._refuse(tr("flows.manager.edit.write_failed"))
                return
            if worker.result.record_revision < self.overview.record_revision or (
                worker.result.record_revision == self.overview.record_revision
                and worker.result.content_digest != self.overview.content_digest
            ):
                self._refuse(tr("flows.manager.edit.stale_result"))
                return
            changed = worker.result.record_revision > self.overview.record_revision
            if written_path == PROFILE_OUTPUT_LANGUAGE_PATH:
                # The page is now written in a different language, and the
                # incremental path cannot express that: it repaints the
                # cells whose content moved, while a language switch also
                # moves the column headers and section titles, which are
                # chrome rather than cells. Rebuilding is the only redraw
                # that reaches all of it.
                self.overview = worker.result
                await self._redraw()
                self.query_one("#manager-status", PinnedStatusBar).show_success(
                    tr("flows.manager.edit.saved" if changed else "flows.manager.edit.no_change")
                )
                return
            await self._apply_overview(worker.result)
            self.query_one("#manager-status", PinnedStatusBar).show_success(
                tr("flows.manager.edit.saved" if changed else "flows.manager.edit.no_change")
            )
            self._carry_walk_on()
            return
        self._walking = False
        # A refusal reaches the operator as itself. A cancelled or
        # result-less worker would otherwise leave the page looking as
        # though nothing had been asked of it.
        self._refuse_worker(worker.error, message_key="flows.manager.edit.write_failed")

    def _clear_notice(self) -> None:
        """Reset the diagnostic line while preserving its pinned space."""
        self.query_one("#manager-status", PinnedStatusBar).clear_message()

    def _refuse(self, message: str) -> None:
        """Show something the page would not do, and why."""
        self.query_one("#manager-status", PinnedStatusBar).show_error(message)

    def _refuse_worker(self, error: BaseException | None, *, message_key: str) -> None:
        """Show what a finished worker failed with, never as a blank line.

        ``str(exc)`` is the empty string for any exception constructed
        without arguments, and Textual hands the settling handlers exactly
        that when a worker is cancelled: ``Worker._run`` stores the
        ``asyncio.CancelledError`` it caught, whose text is empty. Rendered
        as itself it reaches the operator as an error-styled line with
        nothing written on it, which says less than saying nothing.

        The fallback therefore turns on the rendered text being empty
        rather than on the exception's type, because no type owns that
        emptiness — a door that raises bare renders just as blank.
        """
        if error is None:
            rendered = ""
        else:
            from ....application.user_profile.capsule_record import ProfileRecordConflictError
            from ....core.errors.error_codes import resolve_error_message
            from ....core.errors.hierarchy import CadrumoError

            if isinstance(error, ProfileRecordConflictError):
                rendered = tr("errors.fail.fail_storage_secure_object_revision_conflict")
            else:
                rendered = resolve_error_message(error) if isinstance(error, CadrumoError) else ""
        self._refuse(rendered or tr(message_key))

    async def action_quit(self) -> None:
        """Leave the manager, unless a field write is still landing.

        A thread-backed write cannot be cancelled safely: quitting would only
        detach its result while encrypted storage may still complete the
        save, so the operator would leave believing an edit was lost that in
        fact landed. Waiting for the one in-flight write is the honest
        behaviour, and it is bounded by a single storage round trip.

        """
        if self._pending_write is not None or self._pending_completion is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        self.dismiss(None)

    def action_choose_language(self) -> None:
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

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self.app)


__all__ = [
    "ProfileFieldPersist",
    "ProfileManagerScreen",
]
