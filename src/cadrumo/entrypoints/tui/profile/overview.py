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
:func:`~cadrumo.application.user_profile.build_profile_overview`, and an
edit is an authenticated revision-bound fact command.

See Also:
    :class:`~cadrumo.application.user_profile.ProfileOverview`
        The typed projection this screen renders.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import nullcontext
from contextvars import copy_context
from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar, cast, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, DataTable, Footer, LoadingIndicator, Static
from textual.worker import Worker, WorkerState

from ....adapters.inbound.tui import FormScreen, presenting_forms_through
from ....core import OperatorProgress
from ....core.i18n import tr
from ....entrypoints.tui.components.status import PinnedStatusBar
from ....entrypoints.tui.components.theme import (
    BASE_CSS,
    NOTICE_BAND_CSS,
    install_cadrumo_themes,
    toggle_appearance,
)
from ....entrypoints.tui.components.widgets import ContentDataTable, ContentScroll, NoticeBand
from .editor import FieldEditScreen
from .tasks import ManagerAction, ManagerActionDisposition, ManagerActionOutcome

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from textual.widgets.data_table import ColumnKey

    from ....application.user_profile import ProfileFieldView, ProfileOverview, ProfileSectionView
    from ....entrypoints.tui.components.forms import FormPage


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


class ProfileManagerApp(App[None]):
    """Full-screen profile overview with in-place editing."""

    CSS = (
        BASE_CSS
        + NOTICE_BAND_CSS
        + """
    #manager-context { width: 100%; height: auto; }
    #manager-requirements { width: 100%; height: auto; }
    .manager-section DataTable { height: auto; width: 100%; background: $surface; }
    #manager-actions { height: auto; width: 100%; }
    #manager-actions Button { width: 100%; margin: 0; }
    #manager-busy { display: none; height: 1; margin: 0; }
    #manager-busy.busy { display: block; }
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
        validate: Callable[[str, str], str | None] | None = None,
    ) -> None:
        """Initialize the overview with injected projection and write doors."""
        super().__init__()
        self.overview = overview
        self._validate_field = validate
        """Why the write door would refuse one path's value, or ``None``.

        Injected beside the write door and from the same authority, so the
        dialog refuses exactly what storage would refuse. A host that
        supplies none leaves every box unchecked until the write — which is
        where the refusal used to arrive, unhelpfully."""
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
        yield PinnedStatusBar(id="manager-status")
        with ContentScroll(id="manager-body", classes="cadrumo-scroll"), Vertical(classes="cadrumo-column"):
            yield Vertical(id="manager-context")
            if self._actions:
                with Vertical(id="manager-actions-panel", classes="cadrumo-panel"):
                    with Vertical(id="manager-actions"):
                        for action in self._actions:
                            yield Button(self._action_label(action), id=f"action-{action.key}")
                    yield LoadingIndicator(id="manager-busy")
            for section in self.overview.sections:
                yield Static(id=f"section-{section.key}", classes="manager-section cadrumo-panel")
        yield Footer()

    async def on_mount(self) -> None:
        """Install the presentation theme and render the supplied overview."""
        install_cadrumo_themes(self)
        await self._render()

    # ── rendering ───────────────────────────────────────────────────────

    async def _render(self) -> None:
        """Rebuild the profile context and every schema section table.

        This is the wholesale redraw: it destroys and remounts every table.
        It is what ``on_mount`` needs, and what an action returning a fresh
        overview needs, because either can hand the page a structurally
        different profile. A single-field edit goes through
        :meth:`_apply_overview` instead, which repaints only the cells whose
        content actually moved — the same page, at a fraction of the work.
        """
        self._render_chrome()
        self._clear_notice()
        await self._render_profile_context()
        self._field_by_key.clear()
        self._table_by_section.clear()
        self._columns_by_section.clear()
        for section in self.overview.sections:
            panel = self.query_one(f"#section-{section.key}", Static)
            panel.border_title = self._section_title(section)
            await panel.remove_children()
            table: DataTable[str] = ContentDataTable(cursor_type="row", zebra_stripes=True)
            await panel.mount(table)
            self._table_by_section[section.key] = table
            self._columns_by_section[section.key] = [
                table.add_column(tr("flows.manager.column.state")),
                table.add_column(tr("flows.manager.column.field"), width=_FIELD_COLUMN_WIDTH),
                table.add_column(tr("flows.manager.column.value")),
            ]
            for field in section.fields:
                key = field.path
                self._field_by_key[key] = field
                # ``height=None`` is what lets a field name past the capped
                # column width wrap onto more lines instead of being clipped
                # or pushing the value column off-screen — see
                # ``_FIELD_COLUMN_WIDTH``.
                table.add_row(*self._rendered_row(field), key=key, height=None)

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
        row of a repeatable section can add a group. The structural
        comparison is what makes that safe — the shapes stop matching and
        this falls back to the full rebuild rather than writing into
        coordinates the new page no longer has.
        """
        previous = self.overview
        self.overview = updated
        if self._shape_of(previous) != self._shape_of(updated):
            await self._render()
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
                await self._render()
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
        requirements = (
            tr(
                "cli.diagnostics.summary.profile_missing_fields",
                count=len(self.overview.missing_required),
                fields=", ".join(missing_labels),
            )
            if self.overview.missing_required
            else ""
        )
        context = self.query_one("#manager-context", Vertical)
        await context.remove_children()
        if requirements:
            await context.mount(
                Static(requirements, id="manager-requirements", classes="cadrumo-note", markup=False),
            )
        if self.overview.notices:
            await context.mount(NoticeBand(self.overview.notices, id="manager-notice-band"))

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
        """Open the edit dialog for the selected field, or its owning action.

        Refused while a write is in flight: the door merges into the record
        as it loads it, so a second edit started before the first landed
        would merge into the pre-edit facts and drop the first field.

        Refused while an action runs for the same reason, one step larger:
        an action rewrites the whole profile, so a field edited against the
        page as it looks now would be merged into a record the action is
        about to replace.

        A field an action declares itself the sole writer of opens that
        action instead of the edit box. The box writes exactly one fact and
        does nothing else, which is right for almost every row and wrong
        for a field that cannot be correct on its own — so rather than
        teach the generic door about particular fields, the row is handed
        to the writer that already knows.
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
        owner = self._action_owning(field.path)
        if owner is not None:
            self._start_action(owner)
            return
        self.push_screen(
            FieldEditScreen(field, validate=self._validator_for(field)),
            self._apply_edit_for(field),
        )

    def _action_owning(self, path: str) -> ManagerAction | None:
        """Return the action that is the sole writer of ``path``, or ``None``.

        Only the declaring action decides this. The screen holds no list of
        special paths of its own, so an action that stops owning a field
        takes the routing with it and cannot leave a row pointing at a
        writer that no longer wants it.
        """
        return next((action for action in self._actions if path in action.owns_paths), None)

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
            written = cast("ProfileOverview | None", write_context.run(self._persist_field, path, value))
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

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Land one finished worker back on Textual's UI task.

        Widgets are only safe to touch from this task, so every repaint
        waits until here rather than happening in the worker. Both kinds of
        background work arrive through this one handler because Textual
        reports them all here; which one finished is decided by identity,
        so a worker this screen did not start is left alone.
        """
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}:
            return
        event_worker = cast("Worker[object]", event.worker)
        if self._pending_write is not None and event_worker is self._pending_write:
            await self._settle_write(self._pending_write)
            return
        if self._pending_action is not None and event_worker is self._pending_action:
            await self._settle_action(self._pending_action)

    async def _settle_write(self, worker: Worker[ProfileOverview]) -> None:
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
                await self._render()
                return
            await self._apply_overview(worker.result)
            return
        # A refusal reaches the operator as itself. A cancelled or
        # result-less worker would otherwise leave the page looking as
        # though nothing had been asked of it.
        self._refuse_worker(worker.error, message_key="flows.manager.edit.write_failed")

    async def _settle_action(self, worker: Worker[ManagerActionOutcome]) -> None:
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
            self._refuse_worker(worker.error, message_key="flows.manager.action.failed")
            return
        outcome = worker.result
        if outcome.close_session:
            # The surface itself must go, not merely repaint: re-rendering
            # here would show the just-logged-out profile's table as if it
            # were still live. Exiting is what actually closes the operator
            # back to their shell, the same coherent landing the quit
            # binding already gives them -- there is nowhere else to route
            # a session that just ended.
            self.exit(None)
            return
        if outcome.overview is not None:
            # A full redraw, not a cell diff: an action can change the
            # profile's shape, which is exactly what the diff cannot do.
            self.overview = outcome.overview
            await self._render()
        # After the redraw, which clears the channel: reporting first would
        # write the outcome and then immediately wipe it.
        match outcome.disposition:
            case ManagerActionDisposition.SUCCESS:
                self._report(outcome.message)
            case ManagerActionDisposition.WARNING:
                self._warn(outcome.message)
            case ManagerActionDisposition.REFUSED:
                self._refuse(outcome.message)

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
            from ....core.errors import CadrumoError, resolve_error_message

            rendered = resolve_error_message(error) if isinstance(error, CadrumoError) else ""
        self._refuse(rendered or tr(message_key))

    def _report(self, message: str) -> None:
        """Show what an action did."""
        self.query_one("#manager-status", PinnedStatusBar).show_success(message)

    def _warn(self, message: str) -> None:
        """Show a completed action whose partial failures need attention."""
        self.query_one("#manager-status", PinnedStatusBar).show_warning(message)

    def _progress(self, progress: OperatorProgress) -> None:
        """Show what is happening while it is still happening."""
        self.query_one("#manager-status", PinnedStatusBar).show_progress(progress.render())

    def _progress_from_worker(self, progress: OperatorProgress) -> None:
        """Move a worker-thread progress emission onto Textual's UI task."""
        if not self.is_running:
            return
        try:
            self.call_from_thread(self._progress, progress)
        except RuntimeError:
            # A thread-backed action may outlive a closing application. At
            # that point there is no screen left to update.
            return

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
        self._start_action(action)

    def _start_action(self, action: ManagerAction) -> None:
        """Run one action on a worker thread, from a button or an owned row.

        Extracted so a row that routes to its owning action reaches it by
        the same path a button press does. A second launcher would be a
        second place for the busy check, the context copy, the presenter
        binding and the progress line to drift out of agreement, over an
        operation whose whole purpose here is having one writer.
        """
        if self._pending_action is not None or self._pending_write is not None:
            self._refuse(tr("flows.manager.action.busy"))
            return
        action_context = copy_context()

        def _run() -> ManagerActionOutcome:
            progress_scope = (
                action.progress_sink(self._progress_from_worker) if action.progress_sink is not None else nullcontext()
            )
            with presenting_forms_through(self._present_form_here), progress_scope:
                return action.run()

        self._pending_action = self.run_worker(
            lambda: action_context.run(_run),
            name=f"profile-action-{action.key}",
            group="profile-action",
            exit_on_error=False,
            thread=True,
        )
        self._set_busy(True)
        self._progress(OperatorProgress(message=tr("flows.manager.action.working", action=self._action_label(action))))

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

        An application that stops takes both halves of this with it, and
        both have to say so. The wait ends when it stops; the push refuses
        outright once the loop is gone, because ``call_from_thread`` raises
        there rather than blocking. So neither half can strand this thread,
        and both answer ``None``, which every caller already treats as "the
        operator walked away".

        A refusal while the application is still up means something else
        entirely — that this was called on the UI task — and is raised, not
        dressed up as an abandonment. Telling those two apart by liveness
        is exact rather than approximate: the application stops running
        before it lets go of its loop, so a refusal that coincides with a
        stopped application can only be the one the missing loop caused.
        """
        collected: Mapping[str, str] | None = None
        answered = threading.Event()

        def _accept(result: Mapping[str, str] | None) -> None:
            nonlocal collected
            collected = result
            answered.set()

        try:
            self.call_from_thread(self.push_screen, FormScreen(page, rebuild=rebuild), _accept)
        except RuntimeError:
            # Guarded for the same reason the wait below is: the
            # application can stop between this action starting and its
            # page reaching the screen. Left to propagate, that refusal
            # would surface as the settling handler rendering an untranslated
            # Textual internal into the notice line.
            if self.is_running:
                raise
            return None
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
                    choice.value: tr(f"wizard.setup.profile.output-language.choices.{choice.value}.label")
                    for choice in field.choices
                },
                validate=self._validator_for(field),
            ),
            self._apply_edit_for(field),
        )

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self)


def run_profile_manager_tui(
    overview: ProfileOverview,
    *,
    persist: Callable[[str, str], ProfileOverview],
    actions: Sequence[ManagerAction] = (),
    validate: Callable[[str, str], str | None] | None = None,
) -> None:
    """Run the manager to completion against an already-built overview."""
    ProfileManagerApp(overview, persist=persist, actions=actions, validate=validate).run()


__all__ = [
    "ProfileManagerApp",
    "run_profile_manager_tui",
]
