"""The grouped filing portfolio and its admitted next actions."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import ClassVar, Final, override

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import DescendantFocus
from textual.geometry import Region
from textual.widgets import Button, DataTable, Input, Static

from ....application.modelo.declaration_targets import DeclarationTarget
from ....application.modelo.declarations_calendar import DeclarationsCalendarSource
from ....application.modelo.declarations_list import DeclarationListGroup, DeclarationListRow, declaration_list_rows
from ....application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ....core.text_fold import fold_diacritics
from ....core.time.clock import today_madrid
from ..components.dialogs import ConfirmScreen
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..modelo.workbench.wording import modelo_title, period_words, wrap_words
from .controller import (
    DeclarationsRouteRequested,
    DeclarationsWorkspaceController,
    DeclarationsWorkspaceScreen,
    natural_address,
    work_create_refusal_message,
)
from .external_details import ExternalFilingDetailsScreen
from .picker import NewDeclarationPicker
from .row_words import is_unlinked_local_draft, row_lines

_FILTERS = ("all", "attention", "this_year", "recorded", "not_started")
_SORTS = ("deadline", "modelo", "result", "state")

DECLARATION_GROUP_LOCALE_KEYS: Final[Mapping[DeclarationListGroup, str]] = MappingProxyType(
    {
        DeclarationListGroup.ATTENTION: "tui.declarations.list.group.attention",
        DeclarationListGroup.IN_PROGRESS: "tui.declarations.list.group.in_progress",
        DeclarationListGroup.READY: "tui.declarations.list.group.ready",
        DeclarationListGroup.NOT_STARTED: "tui.declarations.list.group.not_started",
        DeclarationListGroup.RECORDED: "tui.declarations.list.group.recorded",
        DeclarationListGroup.AEAT_UNLINKED: "tui.declarations.list.state.aeat_unlinked",
        DeclarationListGroup.MAYBE: "tui.declarations.list.group.maybe",
    }
)


class GroupedDeclarationsScreen(DeclarationsWorkspaceScreen):
    """Foldable filing groups with accent-insensitive search and supported choices."""

    IS_WORKSPACE_OVERVIEW: ClassVar[bool] = True
    BINDINGS: ClassVar = [
        Binding("escape", "back", show=False),
        Binding("plus", "new", show=False),
        Binding("/", "search", show=False),
        Binding("f", "filter", show=False),
        Binding("s", "sort", show=False),
        Binding("t", "technical", show=False),
    ]
    DEFAULT_CSS = tokenised("""
    #declarations-links { height: auto; }
    #declarations-links Button { width: 1fr; min-width: $cadrumo-control-min-width; }
    #declarations-search { height: auto; }
    #declarations-list-context { margin: 0; }
    /* Reset the table's inherited default cap in the default CSS layer. */
    #declarations-list { max-height: initial; }
    #declarations-keys { height: auto; padding-left: $cadrumo-cell-padding; }
    #declarations-technical { height: auto; display: none; }
    """)
    CSS = DeclarationsWorkspaceScreen.CSS + tokenised("""
    #declarations-list-context { margin: 0; }
    """)

    def __init__(
        self, controller: DeclarationsWorkspaceController, *, id: str = "declarations-overview-screen"
    ) -> None:
        """Keep selection and presentation state beside immutable application facts."""
        super().__init__(controller, id=id)
        self.selected_work_unit_id: str | None = None
        self.filter_index = 0
        self.sort_index = 0
        self.folded: set[DeclarationListGroup] = set()
        self.rows: tuple[DeclarationListRow, ...] = ()
        self._creating = False

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.declarations.list.title"), classes="cadrumo-banner", markup=False)
        yield Input(placeholder=tr("tui.declarations.list.search.hint"), id="declarations-search")
        yield Static(id="declarations-list-context", classes="cadrumo-heading", markup=False)
        yield Static(id="declarations-keys", markup=False)
        with ContentScroll(id="declarations-page", classes="cadrumo-scroll declarations-page"):
            yield ContentDataTable(id="declarations-list", cursor_type="row")
            yield Static(id="declarations-empty", markup=False)
            yield Static(id="declarations-refusal", classes="declarations-refusal", markup=False)
            yield Static(id="declarations-work-create-notice", markup=False)
            yield Static(id="declarations-technical", markup=False)
            yield Static(id="declarations-sources", markup=False)
            with Horizontal(id="declarations-links"):
                yield Button(tr("tui.declarations.list.key.new"), id="declarations-new")
                yield Button(tr("tui.declarations.destination.revisions"), id="declarations-revisions")
                yield Button(tr("tui.declarations.destination.filing_history"), id="declarations-filings")
                yield Button(tr("tui.declarations.destination.calendar"), id="declarations-calendar")

    def on_mount(self) -> None:
        """Populate the joined portfolio and restore its semantic selection."""
        self.rows = declaration_list_rows(self.controller.projection, self.controller.calendar_projection)
        self.selected_work_unit_id = self.controller.restored_id("declarations.work")
        self._populate()
        self.query_one("#declarations-new", Button).disabled = self.controller.work_create_handoff is None
        for button, destination in (
            ("revisions", "declarations.revisions"),
            ("filings", "declarations.filing_history"),
            ("calendar", "declarations.calendar"),
        ):
            self.query_one("#declarations-" + button, Button).disabled = self.controller.destination_availability(
                destination
            ).value not in {"available", "stale"}
        self._render_sources()
        self._restore_declaration_focus(None)

    def _render_sources(self) -> None:
        """Say which authorities were observed, including incomplete and retained evidence."""
        lines = []
        projection = self.controller.calendar_projection
        if projection is not None:
            for source in projection.sources:
                if source.source is not DeclarationsCalendarSource.AEAT_EVIDENCE:
                    continue
                from .controller import timestamp_label

                observed = (
                    timestamp_label(source.observed_at)
                    if source.observed_at is not None
                    else tr("tui.declarations.calendar.never_observed")
                )
                lines.append(
                    tr(
                        "tui.declarations.calendar.detail.source",
                        source=tr("tui.declarations.calendar.source." + source.source.value),
                        availability=tr("tui.declarations.availability." + source.availability.value),
                        observed=observed,
                    )
                )
        if any(zone.availability.value == "stale" for zone in self.controller.projection.zones):
            lines.append(tr("tui.declarations.refusal.source"))
        self.query_one("#declarations-sources", Static).update("\n".join(lines))

    def _visible_rows(self) -> list[DeclarationListRow]:
        language = OutputLanguage(output_language())
        terms = fold_diacritics(self.query_one("#declarations-search", Input).value.casefold()).split()
        selected_filter = _FILTERS[self.filter_index]
        calendar = self.controller.calendar_projection
        year = today_madrid().year if calendar is None else calendar.as_of.year
        rows = []
        for row in self.rows:
            if selected_filter == "attention" and row.group is not DeclarationListGroup.ATTENTION:
                continue
            if selected_filter == "this_year" and (row.period is None or row.period.filing_year != year):
                continue
            if selected_filter == "recorded" and row.group is not DeclarationListGroup.RECORDED:
                continue
            if selected_filter == "not_started" and row.state != "not_started":
                continue
            text = modelo_title(row.modelo, language) + " " + (period_words(row.period) if row.period else "")
            if all(term in fold_diacritics(text.casefold()) for term in terms):
                rows.append(row)
        sort = _SORTS[self.sort_index]
        if sort == "result":
            rows.sort(key=_result_sort_key)
        elif sort == "state":
            rows.sort(key=lambda row: (row.state, row.modelo, row.deadline or date.max))
        elif sort == "modelo":
            rows.sort(key=lambda row: (row.modelo, row.deadline or date.max))
        else:
            rows.sort(key=lambda row: (row.deadline or date.max, row.modelo))
        return rows

    def _populate(self) -> None:
        table = self.query_one("#declarations-list", ContentDataTable)
        # Both columns already wrap to the same declared cell budget.
        table.fill_column = None
        selected = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value if table.row_count else None
        table.clear(columns=True)
        width = max(20, (self.size.width - 14) // 2)
        table.add_column(tr("tui.declarations.list.column.declaration"), width=width)
        table.add_column(tr("tui.declarations.list.column.state"), width=width)
        visible = self._visible_rows()
        language = OutputLanguage(output_language())
        for group in DeclarationListGroup:
            members = [row for row in visible if row.group is group]
            folded = not members or group in self.folded
            mark = "▹" if folded else "▿"
            group_key = DECLARATION_GROUP_LOCALE_KEYS[group]
            title = "\n".join(wrap_words(f"{mark} {tr(group_key)} ({len(members)})", width))
            table.add_row(
                Text(title, style="bold"),
                "",
                key="group:" + group.value,
                height=title.count("\n") + 1,
            )
            if folded:
                continue
            for row in members:
                left, right = row_lines(
                    row,
                    language,
                    can_open=self.controller.modelo_workspace_factory is not None,
                    can_create=self.controller.work_create_handoff is not None,
                )
                left_text = "\n".join(line for part in left for line in wrap_words(part, width))
                right_text = "\n".join(line for part in right if part for line in wrap_words(part, width))
                table.add_row(
                    Text(left_text),
                    Text(right_text),
                    height=max(left_text.count("\n"), right_text.count("\n")) + 1,
                    key=row.key,
                )
        table.absorb_surplus_width()
        self.query_one("#declarations-list-context", Static).update(
            tr("tui.declarations.list.filter." + _FILTERS[self.filter_index])
            + " · "
            + tr("tui.declarations.list.sort." + _SORTS[self.sort_index])
        )
        self.query_one("#declarations-empty", Static).update("" if visible else tr("tui.declarations.list.empty"))
        index = next((i for i, row in enumerate(table.ordered_rows) if row.key.value == selected), None)
        if index is not None:
            table.move_cursor(row=index)
        self._render_keys()

    def _render_keys(self) -> None:
        """Keep supported list shortcuts and the selected Enter action visible."""
        table = self.query_one("#declarations-list", ContentDataTable)
        shortcuts = []
        if self.controller.work_create_handoff is not None:
            shortcuts.append("+ " + tr("tui.declarations.list.key.new"))
        shortcuts.extend(
            (
                "/ " + tr("tui.modelo.workbench.key.search"),
                "f " + tr("tui.modelo.workbench.key.filter"),
                "s " + tr("tui.modelo.workbench.key.sort"),
                "t " + tr("tui.modelo.workbench.issues.technical"),
            )
        )
        enter = ""
        if table.has_focus and table.row_count:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            if key is not None and key.startswith("group:"):
                enter = "Enter " + tr("tui.declarations.list.key.toggle_group")
            else:
                row = next((item for item in self.rows if item.key == key), None)
                if row is not None:
                    if row.declaration is not None and row.state != "unreadable":
                        if self.controller.modelo_workspace_factory is not None:
                            enter = "Enter " + tr(
                                "tui.declarations.list.next.open_local_draft"
                                if is_unlinked_local_draft(row)
                                else "tui.declarations.calendar.action.open"
                            )
                    elif (
                        row.state == "not_started"
                        and row.period is not None
                        and self.controller.work_create_handoff is not None
                    ):
                        enter = "Enter " + tr("tui.declarations.list.next.start")
                    elif row.state == "aeat_unlinked":
                        enter = "Enter " + tr("tui.declarations.calendar.action.open")
        self.query_one("#declarations-keys", Static).update((enter + "\n" if enter else "") + " · ".join(shortcuts))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Follow semantic row selection without promising an unavailable route."""
        if event.data_table.id == "declarations-list":
            self._render_keys()
            self.call_after_refresh(self._reveal_selected_row)

    def _reveal_selected_row(self) -> None:
        """Let the outer content scroll reveal the actual highlighted row."""
        table = self.query_one("#declarations-list", ContentDataTable)
        if not table.has_focus or not table.row_count:
            return
        index = table.cursor_row
        rows = table.ordered_rows
        header = table.header_height if table.show_header else 0
        top = table.virtual_region.y + header + sum(row.height for row in rows[:index])
        page = self.query_one("#declarations-page", ContentScroll)
        page.scroll_to_region(
            Region(table.virtual_region.x, top, table.size.width, rows[index].height),
            animate=False,
            x_axis=False,
        )

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        """Show Enter guidance only while the declaration table owns focus."""
        if self.query("#declarations-keys"):
            self._render_keys()
            self.call_after_refresh(self._reveal_selected_row)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the immutable rows without reading storage."""
        if event.input.id == "declarations-search" and self.is_mounted:
            self._populate()

    def on_resize(self) -> None:
        """Wrap names, states and help at the current terminal width."""
        if self.is_mounted and self.query("#declarations-list"):
            self._populate()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Fold a group, open admitted local work, or confirm starting a due return."""
        if self.handle_navigation(event) or event.data_table.id != "declarations-list":
            return
        key = event.row_key.value
        if key is None:
            return
        if key.startswith("group:"):
            group = DeclarationListGroup(key.removeprefix("group:"))
            self.folded.symmetric_difference_update({group})
            self._populate()
            return
        row = next(item for item in self.rows if item.key == key)
        if row.declaration is not None and row.state != "unreadable":
            self._open(row.declaration)
        elif row.state == "not_started" and row.period is not None and self.controller.work_create_handoff is not None:
            target = DeclarationTarget(row.modelo, row.period)
            self.app.push_screen(
                NewDeclarationPicker((target,), frozenset({row.modelo}), preferred=target, confirmation=True),
                self._create_selected,
            )
        elif row.state == "aeat_unlinked":
            self.app.push_screen(ExternalFilingDetailsScreen(row))
        else:
            key = (
                "tui.declarations.list.aeat_unlinked.help.confirmed"
                if row.state == "aeat_unlinked"
                else "tui.declarations.list.unreadable.help"
                if row.state == "unreadable"
                else "tui.declarations.list.maybe.help"
                if row.state == "maybe"
                else "tui.declarations.list.aeat_needs_check.help"
            )
            self.query_one("#declarations-refusal", Static).update(tr(key))

    def _open(self, declaration: DeclarationsWorkspaceDeclarationRefV1) -> None:
        factory = self.controller.modelo_workspace_factory
        if factory is None:
            self.refuse_handoff()
            return
        self.selected_work_unit_id = str(declaration.work_unit_id)
        try:
            self.app.push_screen(factory(declaration), self._restore_declaration_focus)
        except CadrumoError as refusal:
            self.query_one("#declarations-refusal", Static).update(work_create_refusal_message(refusal))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the new picker or the admitted history/calendar routes."""
        if event.button.id == "declarations-new":
            self.action_new()
        elif event.button.id == "declarations-revisions":
            self.post_message(DeclarationsRouteRequested(self.controller.target("declarations.revisions")))
        elif event.button.id == "declarations-filings":
            self.post_message(DeclarationsRouteRequested(self.controller.target("declarations.filing_history")))
        elif event.button.id == "declarations-calendar":
            self.post_message(DeclarationsRouteRequested(self.controller.target("declarations.calendar")))

    def action_new(self) -> None:
        """Offer only registry-backed Modelo/period coordinates."""
        if self._creating or self.controller.work_create_handoff is None:
            return
        applicable = frozenset(row.modelo for row in self.rows if row.state != "maybe")
        targets = self.controller.creation_targets or tuple(
            DeclarationTarget(row.modelo, row.period)
            for row in self.rows
            if row.period is not None and row.state == "not_started"
        )
        due = sorted((row for row in self.rows if row.state == "not_started"), key=lambda row: row.deadline or date.max)
        preferred = DeclarationTarget(due[0].modelo, due[0].period) if due and due[0].period is not None else None
        self.app.push_screen(NewDeclarationPicker(targets, applicable, preferred=preferred), self._create_selected)

    def _create_selected(self, target: DeclarationTarget | None) -> None:
        if target is not None and not self._creating:
            existing = next(
                (
                    row.declaration
                    for row in self.rows
                    if row.declaration is not None and row.modelo == target.modelo and row.period == target.period
                ),
                None,
            )
            if existing is not None:
                self.app.push_screen(
                    ConfirmScreen(
                        title=tr("tui.declarations.list.new.exists"),
                        message=natural_address(target.modelo, target.period.filing_year, target.period),
                        confirm_label=tr("tui.declarations.calendar.action.open"),
                        cancel_label=tr("tui.modelo.workbench.editor.cancel"),
                    ),
                    lambda confirmed: self._open(existing) if confirmed is True else None,
                )
                return
            self._creating = True
            self.run_worker(self._create(target), group="declarations-create")

    async def _create(self, target: DeclarationTarget) -> None:
        handoff = self.controller.work_create_handoff
        if handoff is None:
            self._creating = False
            return
        notice = self.query_one("#declarations-work-create-notice", Static)
        notice.update(tr("tui.declarations.work_create.progress"))
        try:
            result = await asyncio.to_thread(handoff, target.modelo, target.period.filing_year, target.period)
            if result.declaration is not None:
                self._open(result.declaration)
            else:
                notice.update(
                    tr(
                        "tui.declarations.work_create.reused"
                        if result.reused
                        else "tui.declarations.work_create.created",
                        address=natural_address(target.modelo, target.period.filing_year, target.period),
                    )
                )
        except CadrumoError as refusal:
            notice.update(work_create_refusal_message(refusal))
        finally:
            self._creating = False

    def action_search(self) -> None:
        """Focus worded-period and name search."""
        self.query_one("#declarations-search", Input).focus()

    def action_filter(self) -> None:
        """Cycle filing filters."""
        self.filter_index = (self.filter_index + 1) % len(_FILTERS)
        self._populate()

    def action_sort(self) -> None:
        """Cycle sort orders."""
        self.sort_index = (self.sort_index + 1) % len(_SORTS)
        self._populate()

    def action_technical(self) -> None:
        """Show technical identifiers only after an explicit request."""
        table = self.query_one("#declarations-list", DataTable)
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value if table.row_count else None
        row = next((item for item in self.rows if item.key == key), None)
        details = self.query_one("#declarations-technical", Static)
        details.display = not details.display
        if row is not None:
            summary = None if row.declaration is None else row.declaration.summary
            details.update(
                row.key + ("\n" + summary.technical_reason if summary is not None and summary.technical_reason else "")
            )

    def _restore_declaration_focus(self, _: None) -> None:
        if self.controller.refresh_data is not None:
            self.controller.projection, self.controller.calendar_projection = self.controller.refresh_data()
            self.rows = declaration_list_rows(self.controller.projection, self.controller.calendar_projection)
            self._populate()
        table = self.query_one("#declarations-list", DataTable)
        index = next(
            (index for index, row in enumerate(table.ordered_rows) if row.key.value == self.selected_work_unit_id), None
        )
        if index is not None:
            table.move_cursor(row=index)
        table.focus()


def _result_sort_key(row: DeclarationListRow) -> tuple[bool, Decimal, str]:
    summary = None if row.declaration is None else row.declaration.summary
    value = None if summary is None or summary.result is None else summary.result.value
    return (value is None, value if value is not None else Decimal(0), row.modelo)
