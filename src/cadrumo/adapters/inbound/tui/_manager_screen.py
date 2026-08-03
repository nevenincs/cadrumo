"""The profile manager: your profile as data you can edit, not steps to finish.

This is what the operator lands on after registering, and what
``config profile edit`` opens directly. It replaces the wizard's review
page, which enumerated the *questions of a setup flow* with a status
glyph each — a progress meter for a process, telling the operator where
they were in a walk but never what their profile actually held.

The page here is the profile itself: every schema section, every declared
field, and the value on record for it. A field the operator has not
filled in is a visible empty row, because "what is still blank" is the
question this page exists to answer. Selecting any row edits it in place
and writes immediately; there is no submit step, no final commit, and no
ordering. Completeness is shown as a count and a list of what filing will
eventually need — never as a gate on viewing or editing.

The screen owns no profile logic. The page content is
:func:`~cadrumo.application.user_profile.build_profile_overview`, and an
edit is :func:`~cadrumo.application.user_profile.set_active_field` — the
same door every other write path uses.

See Also:
    :class:`~cadrumo.application.user_profile.ProfileOverview`
        The typed projection this screen renders.
"""

from __future__ import annotations

import threading
from contextvars import copy_context
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Input, Label, LoadingIndicator, OptionList, Static
from textual.worker import Worker, WorkerState

from ....core.i18n import tr
from ._form_screen import FormScreen, presenting_forms_through
from ._theme import BASE_CSS, ContentScroll, install_cadrumo_themes, toggle_appearance

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from textual.widgets.data_table import ColumnKey

    from ....application.user_profile import ProfileFieldView, ProfileOverview, ProfileSectionView
    from ._form_screen import FormPage


@dataclass(frozen=True, slots=True)
class ManagerActionOutcome:
    """What an action did, as the page needs to know it.

    ``overview`` carries the rebuilt page when the action changed the
    record, and is ``None`` when it did not — an export writes a file and
    leaves the profile alone. The screen re-renders only when it is given
    something new, so a read-only action cannot silently redraw stale data.
    """

    message: str
    overview: ProfileOverview | None = None


@dataclass(frozen=True, slots=True)
class ManagerAction:
    """One operation offered alongside the field table.

    The screen knows a label and a callable. What "pull" or "export" mean
    is the entry point's business, which is why a censal pull and a bundle
    export can sit side by side here without this module learning what
    either of them is.
    """

    key: str
    label: str
    run: Callable[[], ManagerActionOutcome]
    label_key: str | None = None
    """Locale key for labels that must survive a mid-session language switch.

    ``label`` remains the fallback for a host-supplied action that does not
    have a catalogue key.
    """


_PRESENT_GLYPH = "●"
"""Marks a field carrying a value. A glyph, not colour alone."""

_ABSENT_GLYPH = "○"
"""Marks a declared field the operator has not filled in yet."""

_REQUIRED_MARK = "*"
"""Marks a field filing will eventually require."""

_REFUSAL_TONE = "-refusal"
"""Something the page would not do. The operator's next task."""

_RESULT_TONE = "-result"
"""What an action did. Information, not a demand."""

_PROGRESS_TONE = "-progress"
"""Work still under way, which will be replaced by its own outcome."""

_NOTICE_TONES = (_REFUSAL_TONE, _RESULT_TONE, _PROGRESS_TONE)
"""Every tone the one notice channel can take, so setting one clears the rest."""

_FORM_WAIT_POLL_SECONDS = 0.1
"""How often the action thread re-checks that the application is still up.

Only a liveness poll: the dismissal wakes the wait immediately, and this
bounds how long the thread survives an application that went away without
answering."""

_OUTPUT_LANGUAGE_PATH = "preferences.output_language"
"""The profile field deciding what language this page is written in.

Named here because the page reaches for it directly, which it does for no
other field: changing it changes every label on screen including the ones
that would lead an operator to it.
"""

_LANGUAGE_KEY = "f2"
"""The key that opens the language chooser."""

_LANGUAGE_ACTION = "choose_language"
"""The action that key runs.

Named because the footer entry for the key is written at render time
rather than declared beside it, and the two halves have to find each
other.
"""


class FieldEditScreen(ModalScreen[str | None]):
    """Edit one field's value. Dismisses with the new value, or ``None``."""

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        field: ProfileFieldView,
        *,
        prompt: str | None = None,
        choice_labels: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._field = field
        self._prompt = prompt if prompt is not None else field.label
        """What to call the field here, when the schema's own name is not
        the one the operator knows it by."""
        self._choice_labels = dict(choice_labels or {})
        """How to show each enum token, for a field whose stored tokens are
        not words.

        A language is stored as ``es`` and read as "Spanish", and an
        operator picking their own language cannot be asked to recognise
        the token — least of all in a language they do not read. The token
        is still what gets dismissed and written; only its presentation
        changes."""

    def _label_for(self, value: str) -> str:
        """Show one enum token the way the operator should read it."""
        return self._choice_labels.get(value, value)

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(self._prompt, id="edit-label")
            yield Static(tr("flows.manager.edit.path", path=self._field.path), id="edit-path")
            # A masked field starts EMPTY rather than pre-filled with the
            # placeholder: pre-filling would submit the dots back as the
            # literal new value the moment the operator pressed enter.
            if self._field.enum_values:
                yield OptionList(*[self._label_for(value) for value in self._field.enum_values], id="edit-options")
            else:
                yield Input(value="" if self._field.masked else (self._field.value or ""), id="edit-input")
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        if not self._field.enum_values:
            self.query_one("#edit-input", Input).focus()
            return
        options = self.query_one("#edit-options", OptionList)
        current = next(
            (index for index, value in enumerate(self._field.enum_values) if value == self._field.value),
            None,
        )
        if current is not None:
            options.highlighted = current
        options.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-edit-save":
            if self._field.enum_values:
                self._dismiss_highlighted_option()
            else:
                self.dismiss(self.query_one("#edit-input", Input).value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._dismiss_highlighted_option()

    def _dismiss_highlighted_option(self) -> None:
        highlighted = self.query_one("#edit-options", OptionList).highlighted
        if highlighted is None:
            self.dismiss(None)
            return
        self.dismiss(self._field.enum_values[highlighted])

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProfileManagerApp(App[None]):
    """Full-screen profile overview with in-place editing."""

    CSS = (
        BASE_CSS
        + """
    #manager-progress {
        dock: top;
        height: 1;
        width: 100%;
        padding: 0 2;
        background: $surface;
        color: $text-muted;
    }
    #manager-notice {
        dock: top;
        height: auto;
        width: 100%;
        padding: 0 2;
        color: $text;
    }
    #manager-notice.-refusal { color: $error; text-style: bold; }
    #manager-notice.-result { color: $text; }
    #manager-notice.-progress { color: $text-muted; }
    .manager-section DataTable { height: auto; width: 100%; background: $surface; }
    #manager-actions { height: auto; width: 100%; }
    #manager-actions Button { margin: 0 2 0 0; }
    #manager-busy { display: none; height: 1; margin: 1 0 0 0; }
    #manager-busy.busy { display: block; }
    #edit-dialog {
        border: thick $accent;
        background: $surface;
        padding: 1 3;
        width: 60%;
        height: auto;
    }
    #edit-label { text-style: bold; }
    #edit-path { color: $text-muted; margin: 0 0 1 0; }
    #edit-dialog Input { margin: 0 0 1 0; }
    #edit-actions { height: auto; align-horizontal: right; margin: 1 0 0 0; }
    #edit-actions Button { margin: 0 0 0 2; }
    """
    )

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
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
        Binding("q", "quit", "", show=False),
        Binding("escape", "quit", "", show=False),
    ]

    def __init__(
        self,
        overview: ProfileOverview,
        *,
        persist: Callable[[str, str], ProfileOverview],
        actions: Sequence[ManagerAction] = (),
    ) -> None:
        super().__init__()
        self.overview = overview
        self._actions = tuple(actions)
        """Operations offered above the field table.

        Empty is a valid page: the manager is useful with nothing but its
        fields, and a host that cannot offer an action should show none
        rather than a button that refuses."""
        self._persist_field = persist
        """Writes one field and hands back the page as storage now holds it.

        Injected, not imported: the adapter tier renders a view-model and
        reports intents, exactly as the status page does. Returning the
        reloaded overview rather than ``None`` is what keeps the screen
        from ever displaying its own optimistic guess — whatever the store
        made of the value is what appears."""
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
        self._pending_action: Worker[ManagerActionOutcome] | None = None
        """The one in-flight action, or ``None`` when no button is working.

        Separate from the write worker because the two mean different
        things to the operator and are reported differently, but serialised
        against each other for the same reason writes are serialised among
        themselves: an action reloads and rewrites the whole profile, so
        letting one overlap a field write would let either land on a
        snapshot the other had already moved."""

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="manager-banner", classes="cadrumo-banner")
        yield Static(id="manager-progress")
        yield Static(id="manager-notice")
        with ContentScroll(id="manager-body", classes="cadrumo-scroll"), Vertical(classes="cadrumo-column"):
            if self._actions:
                with Vertical(id="manager-actions-panel", classes="cadrumo-panel"):
                    with Horizontal(id="manager-actions"):
                        for action in self._actions:
                            yield Button(self._action_label(action), id=f"action-{action.key}")
                    yield LoadingIndicator(id="manager-busy")
            for section in self.overview.sections:
                yield Static(id=f"section-{section.key}", classes="manager-section cadrumo-panel")
        yield Footer()

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self._render()

    # ── rendering ───────────────────────────────────────────────────────

    def _render(self) -> None:
        """Rebuild the progress line and every section table from the overview.

        This is the wholesale redraw: it destroys and remounts every table.
        It is what ``on_mount`` needs, and what an action returning a fresh
        overview needs, because either can hand the page a structurally
        different profile. A single-field edit goes through
        :meth:`_apply_overview` instead, which repaints only the cells whose
        content actually moved — the same page, at a fraction of the work.
        """
        self._render_chrome()
        self._clear_notice()
        self._render_progress()
        self._field_by_key.clear()
        self._table_by_section.clear()
        self._columns_by_section.clear()
        for section in self.overview.sections:
            panel = self.query_one(f"#section-{section.key}", Static)
            panel.border_title = self._section_title(section)
            panel.remove_children()
            table: DataTable[str] = DataTable(cursor_type="row", zebra_stripes=True)
            panel.mount(table)
            self._table_by_section[section.key] = table
            self._columns_by_section[section.key] = table.add_columns(
                tr("flows.manager.column.state"),
                tr("flows.manager.column.field"),
                tr("flows.manager.column.value"),
            )
            for field in section.fields:
                key = field.path
                self._field_by_key[key] = field
                table.add_row(*self._rendered_row(field), key=key)

    def _apply_overview(self, updated: ProfileOverview) -> None:
        """Show ``updated`` by repainting only what differs from the page on screen.

        The row SET cannot change under an edit: the overview is projected
        by walking the profile SCHEMA, not the record's facts, so every
        declared field yields a row whether or not it holds a value. What an
        edit CAN change is a row's rendered content — and not only the edited
        row's, since the write door normalises values and re-derives presence
        and completeness. So rather than assume the edited path is the only
        thing that moved, this diffs the old page against the new one and
        writes exactly the cells that differ: usually one row, occasionally a
        few, never all of them.

        The structural comparison is the safety valve. Should the projection
        ever become record-dependent — a conditional section, a repeatable
        row set — the shapes stop matching and this falls back to the full
        rebuild rather than writing into stale coordinates.
        """
        previous = self.overview
        self.overview = updated
        if self._shape_of(previous) != self._shape_of(updated):
            self._render()
            return

        self._render_chrome()
        self._clear_notice()
        self._render_progress()
        for was, now in zip(previous.sections, updated.sections, strict=True):
            table = self._table_by_section.get(now.key)
            columns = self._columns_by_section.get(now.key)
            if table is None or columns is None:
                # The page was never fully rendered, so there are no cells to
                # address. Build it rather than silently dropping the update.
                self._render()
                return
            if (was.present_count, was.total_count) != (now.present_count, now.total_count):
                self.query_one(f"#section-{now.key}", Static).border_title = self._section_title(now)
            for before, after in zip(was.fields, now.fields, strict=True):
                self._field_by_key[after.path] = after
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

    def _render_progress(self) -> None:
        """Restate the present/total/missing counts under the current overview."""
        self.query_one("#manager-progress", Static).update(
            tr(
                "flows.manager.progress",
                present=self.overview.present_count,
                total=self.overview.total_count,
                missing=len(self.overview.missing_required),
            ),
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
        """
        return (
            _PRESENT_GLYPH if field.present else _ABSENT_GLYPH,
            f"{field.label}{_REQUIRED_MARK}" if field.required else field.label,
            field.value or "",
        )

    @staticmethod
    def _shape_of(overview: ProfileOverview) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """The page's row layout: section keys, each with its field paths in order.

        Two overviews sharing a shape address the same cells, which is the
        precondition for updating one in place from the other.
        """
        return tuple((section.key, tuple(field.path for field in section.fields)) for section in overview.sections)

    def _render_chrome(self) -> None:
        """Resolve all manager-owned chrome under the active output language."""
        title = tr("flows.manager.title", profile=self.overview.label)
        self.title = title
        self.sub_title = ""
        self.query_one("#manager-banner", Static).update(title)
        self._offer_language_in_footer()
        if not self._actions:
            return
        self.query_one("#manager-actions-panel", Vertical).border_title = tr("flows.manager.actions.section")
        for action in self._actions:
            self.query_one(f"#action-{action.key}", Button).label = self._action_label(action)

    def _language_field(self) -> ProfileFieldView | None:
        """The field holding the page's language, if the schema declares one.

        Read from the overview rather than the rendered row index because
        the chrome is written before the tables are rebuilt, and because
        the footer and the chooser must agree on whether there is anywhere
        to put an answer.
        """
        for section in self.overview.sections:
            for field in section.fields:
                if field.path == _OUTPUT_LANGUAGE_PATH:
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
        label = field.label if field is not None else ""
        bindings = self._bindings.key_to_bindings.get(_LANGUAGE_KEY)
        if bindings is None:
            return
        self._bindings.key_to_bindings[_LANGUAGE_KEY] = [
            replace(binding, description=label, show=bool(label)) if binding.action == _LANGUAGE_ACTION else binding
            for binding in bindings
        ]
        self.refresh_bindings()

    @staticmethod
    def _action_label(action: ManagerAction) -> str:
        """Render a supplied action label without freezing its locale at construction."""
        if action.label_key is None:
            return action.label
        return tr(action.label_key, default=action.label)

    # ── editing ─────────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the edit dialog for the selected field.

        Refused while a write is in flight: the door merges into the record
        as it loads it, so a second edit started before the first landed
        would merge into the pre-edit facts and drop the first field.

        Refused while an action runs for the same reason, one step larger:
        an action rewrites the whole profile, so a field edited against the
        page as it looks now would be merged into a record the action is
        about to replace.
        """
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        if self._pending_action is not None:
            self._refuse(tr("flows.manager.action.busy"))
            return
        key = event.row_key.value
        if key is None:
            return
        field = self._field_by_key.get(str(key))
        if field is None:
            return
        self.push_screen(FieldEditScreen(field), self._apply_edit_for(field))

    def _apply_edit_for(self, field: ProfileFieldView):
        """Build the dismissal callback that persists one field's new value."""

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
            self._persist(field.path, value)

        return _apply

    def _persist(self, path: str, value: str) -> None:
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
            written = write_context.run(self._persist_field, path, value)
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

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Land one finished worker back on Textual's UI task.

        Widgets are only safe to touch from this task, so every repaint
        waits until here rather than happening in the worker. Both kinds of
        background work arrive through this one handler because Textual
        reports them all here; which one finished is decided by identity,
        so a worker this screen did not start is left alone.
        """
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}:
            return
        if self._pending_write is not None and event.worker is self._pending_write:
            self._settle_write(self._pending_write)
            return
        if self._pending_action is not None and event.worker is self._pending_action:
            self._settle_action(self._pending_action)

    def _settle_write(self, worker: Worker[ProfileOverview]) -> None:
        """Show what storage made of one finished field write."""
        self._pending_write = None
        written_path = self._pending_write_path
        self._pending_write_path = None
        if worker.state is WorkerState.SUCCESS and worker.result is not None:
            if written_path == _OUTPUT_LANGUAGE_PATH:
                # The page is now written in a different language, and the
                # incremental path cannot express that: it repaints the
                # cells whose content moved, while a language switch also
                # moves the column headers and section titles, which are
                # chrome rather than cells. Rebuilding is the only redraw
                # that reaches all of it.
                self.overview = worker.result
                self._render()
                return
            self._apply_overview(worker.result)
            return
        # A refusal reaches the operator as itself. A cancelled or
        # result-less worker would otherwise leave the page looking as
        # though nothing had been asked of it.
        self._refuse(str(worker.error) if worker.error is not None else tr("flows.manager.edit.write_failed"))

    def _settle_action(self, worker: Worker[ManagerActionOutcome]) -> None:
        """Report one finished action and adopt any profile it handed back.

        A failure is reported rather than raised for the reason the old
        inline call caught: the operator is mid-page, and an exception
        would take the whole screen down over, say, a missing certificate.
        The difference is that the failure now arrives as a refusal the
        action chose, not as the seam's own crash.
        """
        self._pending_action = None
        self._set_busy(False)
        if worker.state is not WorkerState.SUCCESS or worker.result is None:
            self._refuse(
                str(worker.error) if worker.error is not None else tr("flows.manager.action.failed"),
            )
            return
        outcome = worker.result
        if outcome.overview is not None:
            # A full redraw, not a cell diff: an action can change the
            # profile's shape, which is exactly what the diff cannot do.
            self.overview = outcome.overview
            self._render()
        # After the redraw, which clears the channel: reporting first would
        # write the outcome and then immediately wipe it.
        self._report(outcome.message)

    def _clear_notice(self) -> None:
        """Empty the channel and drop its tone.

        The tone goes with the text: leaving it behind would colour the
        next message as whatever the last one was, and an empty line still
        carrying the refusal style is a stripe of error colour explaining
        nothing.
        """
        self._announce("", "")

    def _refuse(self, message: str) -> None:
        """Show something the page would not do, and why."""
        self._announce(message, _REFUSAL_TONE)

    def _report(self, message: str) -> None:
        """Show what an action did."""
        self._announce(message, _RESULT_TONE)

    def _progress(self, message: str) -> None:
        """Show what is happening while it is still happening."""
        self._announce(message, _PROGRESS_TONE)

    def _announce(self, message: str, tone: str) -> None:
        """Put one line in the page's single diagnostic channel.

        There is one channel because the operator has one place to look.
        Refusals and results were previously split across two widgets of
        different prominence — a bold docked line for a rejected field, a
        muted line under the buttons for everything an action had to say —
        so an action refusing for want of a certificate whispered while a
        mistyped date shouted, though both are the page answering back.

        What differs between them is emphasis, not location: a refusal is
        the operator's next task and is coloured as such, a result is
        information, and progress is neither and recedes.
        """
        notice = self.query_one("#manager-notice", Static)
        notice.update(message)
        for candidate in _NOTICE_TONES:
            notice.set_class(candidate == tone, candidate)

    def _set_busy(self, busy: bool) -> None:
        """Show that background work is running, and refuse to start more.

        Without this the page looks idle while an action is mid-flight —
        the censal pull waits on a live browser session, which is long
        enough that a still screen reads as a frozen one. Disabling the
        buttons states the same thing the guard already enforces, rather
        than letting a press be silently refused.
        """
        self.query_one("#manager-busy", LoadingIndicator).set_class(busy, "busy")
        for action in self._actions:
            self.query_one(f"#action-{action.key}", Button).disabled = busy

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Start the pressed action off the event loop.

        An action cannot run on this task. Every one of them owns a loop
        for the length of its work — the censal pull drives a browser
        session through ``asyncio.run``, and the certificate and export
        doors open a page — and a loop cannot be started from a task that
        is already running one. Pressing a button therefore used to report
        ``asyncio.run() cannot be called from a running event loop`` into
        the result line and do nothing at all.

        On a worker thread there is no running loop, so an action that
        starts one is legal again, and one that wants to show a page gets a
        presenter that opens it here instead of starting a second
        application. Blocking is fine there and would not be here: the
        censal pull waits on a live browser, which on this task would
        freeze the page.

        The context is copied for the same reason the field write copies
        it: the doors these actions call resolve the active profile bucket
        from a context variable, which a bare thread would not carry.
        """
        button_id = event.button.id or ""
        action = next((item for item in self._actions if f"action-{item.key}" == button_id), None)
        if action is None:
            return
        if self._pending_action is not None or self._pending_write is not None:
            self._refuse(tr("flows.manager.action.busy"))
            return
        action_context = copy_context()

        def _run() -> ManagerActionOutcome:
            with presenting_forms_through(self._present_form_here):
                return action.run()

        self._pending_action = self.run_worker(
            lambda: action_context.run(_run),
            name=f"profile-action-{action.key}",
            group="profile-action",
            exit_on_error=False,
            thread=True,
        )
        self._set_busy(True)
        self._progress(tr("flows.manager.action.working", action=self._action_label(action)))

    def _present_form_here(
        self,
        page: FormPage,
        rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
    ) -> Mapping[str, str] | None:
        """Open one form page on this application, from the action's thread.

        Called on the worker thread, where touching a widget directly is
        not safe, so the push is handed to the UI task and this thread
        waits for what the operator committed. That wait is the point: the
        action is written as a straight line — show the page, use the
        answer — and it stays that way, with only where it runs changed.

        The wait is an explicit event rather than ``push_screen_wait``.
        That call resolves the running worker from a context variable, and
        this thread cannot satisfy it: the action runs inside a context
        copied on the UI task before the worker existed, so the worker is
        absent from it however the call is marshalled. Reaching for
        ``push_screen_wait`` here raised ``NoActiveWorker`` — but only
        AFTER the screen was already on the stack, so the operator was
        given a working form to fill in whose every value was then thrown
        away with the dead action. Waiting on an event the dismissal sets
        depends on nothing ambient.

        The wait ends if the application stops, so quitting with a form
        open cannot strand this thread. It returns ``None`` in that case,
        which every caller already treats as "the operator walked away".
        """
        collected: Mapping[str, str] | None = None
        answered = threading.Event()

        def _accept(result: Mapping[str, str] | None) -> None:
            nonlocal collected
            collected = result
            answered.set()

        self.call_from_thread(self.push_screen, FormScreen(page, rebuild=rebuild), _accept)
        while not answered.wait(timeout=_FORM_WAIT_POLL_SECONDS):
            if not self.is_running:
                return None
        return collected

    @override
    async def action_quit(self) -> None:
        """Leave the manager, unless a field write is still landing.

        A thread-backed write cannot be cancelled safely: quitting would only
        detach its result while encrypted storage may still complete the
        save, so the operator would leave believing an edit was lost that in
        fact landed. Waiting for the one in-flight write is the honest
        behaviour, and it is bounded by a single storage round trip.

        A running action is held for the same reason and is the stronger
        case: it may be mid-way through reconciling a censal read into the
        profile, so leaving now would abandon a write already under way.
        """
        if self._pending_write is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        if self._pending_action is not None:
            self._refuse(tr("flows.manager.action.busy"))
            return
        self.exit(None)

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
        cannot be asked to recognise ``hu``.
        """
        field = self._language_field()
        if field is None:
            # A profile schema that declares no language field is not a
            # failure; the page simply has nothing to offer here. The
            # footer does not name the key in that case, so this answers
            # only an operator who pressed it unprompted.
            self._refuse(tr("flows.manager.language.unavailable"))
            return
        if self._pending_write is not None or self._pending_action is not None:
            self._refuse(tr("flows.manager.action.busy"))
            return
        self.push_screen(
            FieldEditScreen(
                field,
                prompt=tr("wizard.setup.profile.output-language.prompt"),
                choice_labels={
                    value: tr(f"wizard.setup.profile.output-language.choices.{value}.label")
                    for value in field.enum_values
                },
            ),
            self._apply_edit_for(field),
        )

    def action_toggle_appearance(self) -> None:
        toggle_appearance(self)


def run_profile_manager_tui(
    overview: ProfileOverview,
    *,
    persist: Callable[[str, str], ProfileOverview],
    actions: Sequence[ManagerAction] = (),
) -> None:
    """Run the manager to completion against an already-built overview."""
    ProfileManagerApp(overview, persist=persist, actions=actions).run()


__all__ = [
    "FieldEditScreen",
    "ManagerAction",
    "ManagerActionOutcome",
    "ProfileManagerApp",
    "run_profile_manager_tui",
]
