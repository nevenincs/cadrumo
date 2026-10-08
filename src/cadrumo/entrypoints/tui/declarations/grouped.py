"""The grouped filing portfolio and its admitted next actions."""

from __future__ import annotations

import asyncio
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import DescendantFocus
from textual.widgets import Button, DataTable, Input, Static

from ....application.modelo.declaration_targets import DeclarationTarget
from ....application.modelo.declarations_list import DeclarationListGroup, DeclarationListRow, declaration_list_rows
from ....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ....core.time.clock import today_madrid
from ..components.dialogs import ConfirmScreen
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    DeclarationsRouteRequested,
    DeclarationsWorkspaceController,
    DeclarationsWorkspaceScreen,
    natural_address,
    work_create_refusal_message,
)
from .external_details import ExternalFilingDetailsScreen
from .picker import NewDeclarationPicker
from .portfolio_interactions import creation_notice, reveal_portfolio_row
from .portfolio_rendering import (
    configure_portfolio_columns,
    populate_portfolio_groups,
    portfolio_key_guidance,
    portfolio_row_refusal,
    portfolio_source_lines,
)
from .portfolio_rows import creation_targets, existing_declaration, preferred_creation_target, visible_portfolio_rows

_FILTERS = ("all", "attention", "this_year", "recorded", "not_started")
_SORTS = ("deadline", "modelo", "result", "state")


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
    /* Reset the table's inherited default cap in the default CSS layer. */
    #declarations-list { max-height: initial; }
    #declarations-keys { height: auto; padding-left: $cadrumo-cell-padding; }
    #declarations-technical { height: auto; display: none; }
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
        """Say which authorities were observed, including retained evidence."""
        self.query_one("#declarations-sources", Static).update("\n".join(portfolio_source_lines(self.controller)))

    def _visible_rows(self) -> list[DeclarationListRow]:
        calendar = self.controller.calendar_projection
        year = today_madrid().year if calendar is None else calendar.as_of.year
        return visible_portfolio_rows(
            self.rows,
            self.query_one("#declarations-search", Input).value,
            _FILTERS[self.filter_index],
            _SORTS[self.sort_index],
            year,
            OutputLanguage(output_language()),
        )

    def _populate(self) -> None:
        table = self.query_one("#declarations-list", ContentDataTable)
        width = max(20, (self.size.width - 14) // 2)
        selected = configure_portfolio_columns(table, width)
        visible = self._visible_rows()
        language = OutputLanguage(output_language())
        populate_portfolio_groups(table, visible, self.folded, width, language, self.controller)
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
        """Keep supported shortcuts and the selected Enter action visible."""
        table = self.query_one("#declarations-list", ContentDataTable)
        self.query_one("#declarations-keys", Static).update(portfolio_key_guidance(table, self.rows, self.controller))

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
        reveal_portfolio_row(table, self.query_one("#declarations-page", ContentScroll))

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

    def _activate_row(self, row: DeclarationListRow) -> None:
        """Open exactly the selected row or confirm its supported creation."""
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
            self.query_one("#declarations-refusal", Static).update(portfolio_row_refusal(row))

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
        self._activate_row(row)

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
        targets = creation_targets(self.rows, self.controller.creation_targets)
        preferred = preferred_creation_target(self.rows)
        self.app.push_screen(NewDeclarationPicker(targets, applicable, preferred=preferred), self._create_selected)

    def _create_selected(self, target: DeclarationTarget | None) -> None:
        if target is not None and not self._creating:
            existing = existing_declaration(self.rows, target)
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
            # Obligations the new declaration brings with it are said whether or not it opens.
            advisories = tuple(tr(key) for key in result.advisory_keys)
            if result.declaration is not None:
                if advisories:
                    notice.update("\n".join(advisories))
                self._open(result.declaration)
            else:
                notice.update(creation_notice(result, target, advisories))
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
        if self.controller.refresh_from_capture():
            self.rows = declaration_list_rows(self.controller.projection, self.controller.calendar_projection)
            self._populate()
        table = self.query_one("#declarations-list", DataTable)
        index = next(
            (index for index, row in enumerate(table.ordered_rows) if row.key.value == self.selected_work_unit_id), None
        )
        if index is not None:
            table.move_cursor(row=index)
        table.focus()
